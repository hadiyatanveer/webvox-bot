#!/usr/bin/env python3
"""
WebVox Performance Benchmark
==============================
Measures end-to-end and LangGraph-only latency across the three main
execution paths in the LangGraph architecture.

Usage (from the webvox-bot/ directory):
    python scripts/evaluate_performance.py                  # HTTP mode (default)
    python scripts/evaluate_performance.py --mode direct    # Direct VoiceBotManager mode
    python scripts/evaluate_performance.py --runs 5         # 5 runs per test case
    python scripts/evaluate_performance.py --url http://localhost:8000

Modes:
    http    — Sends real HTTP POST requests to the running FastAPI server.
              Measures both network+server latency (E2E) and the pure
              LangGraph processing time returned in the response body.

    direct  — Imports and calls VoiceBotManager directly (no HTTP overhead).
              Useful when the server is not running or for CI environments.
"""

import argparse
import json
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

# ── Colour helpers (graceful fallback if colorama not installed) ──────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    _C = {
        "green":  Fore.GREEN,
        "red":    Fore.RED,
        "yellow": Fore.YELLOW,
        "cyan":   Fore.CYAN,
        "bold":   Style.BRIGHT,
        "reset":  Style.RESET_ALL,
    }
except ImportError:
    _C = {k: "" for k in ("green", "red", "yellow", "cyan", "bold", "reset")}


# ─────────────────────────────────────────────────────────────────────────────
# Test-case definitions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    """A single benchmark query with its expected LangGraph route."""
    name: str
    query: str
    expected_route: str          # label shown in the summary table
    description: str = ""


# The three canonical paths through the LangGraph architecture.
# Each group deliberately targets a different set of nodes.
TEST_CASES: List[TestCase] = [

    # ── Path 1: Greeting / Unknown ────────────────────────────────────────────
    # Route: START → intent_detector → generate_response (END)
    # Fastest path — no RAG, no DB, no action classifier.
    TestCase(
        name="Greeting",
        query="Hello there!",
        expected_route="Greeting",
        description="START → Intent → Generate (greeting fast-path)",
    ),
    TestCase(
        name="Vague / Clarification",
        query="I want some food.",
        expected_route="Clarification",
        description="START → Intent → Generate (low-confidence clarification)",
    ),
    TestCase(
        name="Off-topic",
        query="What is the capital of France?",
        expected_route="Clarification",
        description="START → Intent → Generate (unknown category)",
    ),

    # ── Path 2: Information Retrieval / RAG ───────────────────────────────────
    # Route: START → intent_detector → vector_search → [graphql_planning] → generate_response
    # Medium path — FAISS lookup, possible GraphQL fallback.
    TestCase(
        name="Policy Query (Vector)",
        query="What is your kitchen hygiene policy?",
        expected_route="Info / Vector",
        description="START → Intent → Vector Search → Generate",
    ),
    TestCase(
        name="Menu Info (GraphQL)",
        query="Show me all available pizzas with their prices.",
        expected_route="Info / GraphQL",
        description="START → Intent → Vector → GraphQL → Generate",
    ),
    TestCase(
        name="Order History",
        query="Show me my recent orders.",
        expected_route="Info / GraphQL",
        description="START → Intent → Vector → GraphQL (user-scoped) → Generate",
    ),
    TestCase(
        name="Specific Item Info",
        query="How many calories does the Margherita pizza have?",
        expected_route="Info / GraphQL",
        description="START → Intent → Vector → GraphQL → Generate",
    ),

    # ── Path 3: Action Execution ──────────────────────────────────────────────
    # Route: START → intent_detector → action_intent_classifier →
    #        [action_enrichment → mutation_execution] → generate_response
    # Slowest path — LLM classification + entity resolution + DB write.
    TestCase(
        name="Place Order (Clarification)",
        query="I want to order a pizza.",
        expected_route="Action Clarification",
        description="START → Intent → Action Classifier → Generate (missing info)",
    ),
    TestCase(
        name="Place Order (Complete)",
        query="Place an order for 2 large Margherita pizzas.",
        expected_route="Action Execution",
        description="START → Intent → Action Classifier → Enrichment → Mutation → Generate",
    ),
    TestCase(
        name="Make Reservation",
        query="Book a table for 4 people tomorrow at 7 PM.",
        expected_route="Action Execution",
        description="START → Intent → Action Classifier → Enrichment → Mutation → Generate",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    """Timing and metadata for a single test-case run."""
    test_case: TestCase
    run_index: int
    success: bool
    e2e_latency: float          # wall-clock time measured by THIS script (seconds)
    langgraph_time: Optional[float]  # pure graph time returned by the server
    wall_time: Optional[float]       # full server-side time returned by the server
    actual_route: str
    response_preview: str
    error: Optional[str] = None


@dataclass
class AggregatedResult:
    """Statistics across all runs for one test case."""
    test_case: TestCase
    runs: List[RunResult] = field(default_factory=list)

    @property
    def successful_runs(self) -> List[RunResult]:
        return [r for r in self.runs if r.success]

    def _stat(self, values: List[float]) -> dict:
        if not values:
            return {"mean": None, "median": None, "min": None, "max": None, "stdev": None}
        return {
            "mean":   round(statistics.mean(values), 3),
            "median": round(statistics.median(values), 3),
            "min":    round(min(values), 3),
            "max":    round(max(values), 3),
            "stdev":  round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        }

    @property
    def e2e_stats(self) -> dict:
        return self._stat([r.e2e_latency for r in self.successful_runs])

    @property
    def langgraph_stats(self) -> dict:
        values = [r.langgraph_time for r in self.successful_runs if r.langgraph_time is not None]
        return self._stat(values)

    @property
    def success_rate(self) -> float:
        if not self.runs:
            return 0.0
        return len(self.successful_runs) / len(self.runs) * 100

    @property
    def actual_routes(self) -> List[str]:
        return [r.actual_route for r in self.successful_runs]


# ─────────────────────────────────────────────────────────────────────────────
# HTTP runner
# ─────────────────────────────────────────────────────────────────────────────

def run_http(
    test_case: TestCase,
    run_index: int,
    base_url: str,
    session_id: str,
    timeout: int,
) -> RunResult:
    """Send one HTTP request and capture timing."""
    import requests  # already in requirements.txt

    url = f"{base_url.rstrip('/')}/api/v1/chat"
    payload = {
        "message": test_case.query,
        "session_id": session_id,
        "input_type": "text",
    }

    t_start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        e2e = round(time.perf_counter() - t_start, 4)

        if resp.status_code != 200:
            return RunResult(
                test_case=test_case,
                run_index=run_index,
                success=False,
                e2e_latency=e2e,
                langgraph_time=None,
                wall_time=None,
                actual_route="HTTP Error",
                response_preview="",
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        data = resp.json()
        response_text = data.get("response", "")
        return RunResult(
            test_case=test_case,
            run_index=run_index,
            success=data.get("success", False),
            e2e_latency=e2e,
            langgraph_time=data.get("langgraph_time"),
            wall_time=data.get("wall_time"),
            actual_route=data.get("route", "Unknown"),
            response_preview=response_text[:120].replace("\n", " "),
        )

    except Exception as exc:
        e2e = round(time.perf_counter() - t_start, 4)
        return RunResult(
            test_case=test_case,
            run_index=run_index,
            success=False,
            e2e_latency=e2e,
            langgraph_time=None,
            wall_time=None,
            actual_route="Exception",
            response_preview="",
            error=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Direct runner (no HTTP)
# ─────────────────────────────────────────────────────────────────────────────

def run_direct(
    test_case: TestCase,
    run_index: int,
    session_id: str,
    manager,          # VoiceBotManager instance
) -> RunResult:
    """Call VoiceBotManager directly and capture timing."""
    t_start = time.perf_counter()
    try:
        result = manager.process_input(
            session_id=session_id,
            user_input=test_case.query,
        )
        e2e = round(time.perf_counter() - t_start, 4)

        return RunResult(
            test_case=test_case,
            run_index=run_index,
            success=result.get("status") == "success",
            e2e_latency=e2e,
            langgraph_time=result.get("langgraph_time"),
            wall_time=None,   # no network layer in direct mode
            actual_route=result.get("route", "Unknown"),
            response_preview=(result.get("response", "")[:120]).replace("\n", " "),
        )

    except Exception as exc:
        e2e = round(time.perf_counter() - t_start, 4)
        return RunResult(
            test_case=test_case,
            run_index=run_index,
            success=False,
            e2e_latency=e2e,
            langgraph_time=None,
            wall_time=None,
            actual_route="Exception",
            response_preview="",
            error=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────

def _col(text: str, width: int, align: str = "<") -> str:
    """Return text padded/truncated to exactly `width` characters."""
    text = str(text)
    if len(text) > width:
        text = text[: width - 1] + "…"
    return f"{text:{align}{width}}"


def _fmt_time(val: Optional[float]) -> str:
    if val is None:
        return "  N/A  "
    return f"{val:6.3f}s"


def _route_colour(route: str) -> str:
    route_l = route.lower()
    if "action" in route_l:
        return _C["yellow"]
    if "info" in route_l or "vector" in route_l or "graphql" in route_l:
        return _C["cyan"]
    if "greeting" in route_l or "clarification" in route_l:
        return _C["green"]
    if "error" in route_l or "exception" in route_l or "security" in route_l:
        return _C["red"]
    return ""


def print_run_table(results: List[RunResult]) -> None:
    """Print a per-run detail table (shown when --runs > 1)."""
    W = {"#": 3, "name": 28, "run": 4, "route": 22, "e2e": 9, "lg": 9, "ok": 7}
    sep = "─" * (sum(W.values()) + len(W) * 3 + 1)

    header = (
        f" {'#':>{W['#']}} │ {_col('Test Case', W['name'])} │ "
        f"{'Run':>{W['run']}} │ {_col('Actual Route', W['route'])} │ "
        f"{'E2E':>{W['e2e']}} │ {'LangGraph':>{W['lg']}} │ {'Status':^{W['ok']}} "
    )

    print(f"\n{_C['bold']}Per-Run Detail{_C['reset']}")
    print(sep)
    print(header)
    print(sep)

    for i, r in enumerate(results, 1):
        ok_str = f"{_C['green']}  ✓ OK {_C['reset']}" if r.success else f"{_C['red']}  ✗ FAIL{_C['reset']}"
        rc = _route_colour(r.actual_route)
        print(
            f" {i:>{W['#']}} │ {_col(r.test_case.name, W['name'])} │ "
            f"{r.run_index:>{W['run']}} │ {rc}{_col(r.actual_route, W['route'])}{_C['reset']} │ "
            f"{_fmt_time(r.e2e_latency):>{W['e2e']}} │ {_fmt_time(r.langgraph_time):>{W['lg']}} │ {ok_str}"
        )

    print(sep)


def print_summary_table(aggregated: List[AggregatedResult], mode: str) -> None:
    """Print the main summary table — one row per test case."""
    W = {
        "name":    26,
        "exp":     22,
        "actual":  22,
        "e2e_med": 10,
        "lg_med":  10,
        "lg_mean": 10,
        "lg_min":  9,
        "lg_max":  9,
        "sr":      7,
    }
    total_w = sum(W.values()) + len(W) * 3 + 1
    sep = "─" * total_w
    thick = "═" * total_w

    header = (
        f" {_col('Test Case', W['name'])} │ "
        f"{_col('Expected Route', W['exp'])} │ "
        f"{_col('Actual Route', W['actual'])} │ "
        f"{'E2E Med':>{W['e2e_med']}} │ "
        f"{'LG Med':>{W['lg_med']}} │ "
        f"{'LG Mean':>{W['lg_mean']}} │ "
        f"{'LG Min':>{W['lg_min']}} │ "
        f"{'LG Max':>{W['lg_max']}} │ "
        f"{'Success':^{W['sr']}} "
    )

    print(f"\n{_C['bold']}{'═' * total_w}")
    print(f"  WebVox Performance Benchmark  ·  mode={mode.upper()}")
    print(f"{'═' * total_w}{_C['reset']}")
    print(header)
    print(thick)

    for agg in aggregated:
        tc = agg.test_case
        e2e_s = agg.e2e_stats
        lg_s  = agg.langgraph_stats

        # Determine the most common actual route
        routes = agg.actual_routes
        actual_route = max(set(routes), key=routes.count) if routes else "N/A"

        # Route match indicator
        route_match = "✓" if actual_route == tc.expected_route else "~"

        rc = _route_colour(actual_route)
        sr_colour = _C["green"] if agg.success_rate == 100 else _C["yellow"] if agg.success_rate >= 50 else _C["red"]

        print(
            f" {_col(tc.name, W['name'])} │ "
            f"{_col(tc.expected_route, W['exp'])} │ "
            f"{rc}{route_match} {_col(actual_route, W['actual'] - 2)}{_C['reset']} │ "
            f"{_fmt_time(e2e_s['median']):>{W['e2e_med']}} │ "
            f"{_fmt_time(lg_s['median']):>{W['lg_med']}} │ "
            f"{_fmt_time(lg_s['mean']):>{W['lg_mean']}} │ "
            f"{_fmt_time(lg_s['min']):>{W['lg_min']}} │ "
            f"{_fmt_time(lg_s['max']):>{W['lg_max']}} │ "
            f"{sr_colour}{agg.success_rate:5.0f}%{_C['reset']}  "
        )
        print(sep)

    # ── Path-group averages ───────────────────────────────────────────────────
    def _group_avg(label: str, keyword: str) -> None:
        group = [
            r
            for agg in aggregated
            for r in agg.successful_runs
            if keyword.lower() in (r.actual_route or "").lower()
        ]
        if not group:
            return
        e2e_vals = [r.e2e_latency for r in group]
        lg_vals  = [r.langgraph_time for r in group if r.langgraph_time is not None]
        e2e_avg  = statistics.mean(e2e_vals) if e2e_vals else None
        lg_avg   = statistics.mean(lg_vals)  if lg_vals  else None
        print(
            f"  {_C['bold']}{label:<30}{_C['reset']}  "
            f"E2E avg: {_fmt_time(e2e_avg)}   LG avg: {_fmt_time(lg_avg)}"
        )

    print(f"\n{_C['bold']}Path-Group Averages{_C['reset']}")
    _group_avg("Action Execution / Clarification", "action")
    _group_avg("Info / RAG (Vector + GraphQL)",    "info")
    _group_avg("Greeting / Clarification",         "greeting")
    _group_avg("Clarification",                    "clarification")
    print()


def print_response_previews(aggregated: List[AggregatedResult]) -> None:
    """Print the last bot response for each test case."""
    print(f"\n{_C['bold']}Response Previews (last run){_C['reset']}")
    print("─" * 80)
    for agg in aggregated:
        last = agg.runs[-1] if agg.runs else None
        if last:
            status = f"{_C['green']}✓{_C['reset']}" if last.success else f"{_C['red']}✗{_C['reset']}"
            print(f"  {status} [{agg.test_case.name}]")
            if last.error:
                print(f"    {_C['red']}Error: {last.error}{_C['reset']}")
            else:
                print(f"    {last.response_preview}")
    print()


def save_json_report(aggregated: List[AggregatedResult], path: str) -> None:
    """Persist full results as JSON for later analysis / charting."""
    report = []
    for agg in aggregated:
        report.append({
            "test_case": {
                "name": agg.test_case.name,
                "query": agg.test_case.query,
                "expected_route": agg.test_case.expected_route,
                "description": agg.test_case.description,
            },
            "success_rate_pct": round(agg.success_rate, 1),
            "e2e_stats": agg.e2e_stats,
            "langgraph_stats": agg.langgraph_stats,
            "actual_routes": agg.actual_routes,
            "runs": [
                {
                    "run": r.run_index,
                    "success": r.success,
                    "e2e_latency": r.e2e_latency,
                    "langgraph_time": r.langgraph_time,
                    "wall_time": r.wall_time,
                    "actual_route": r.actual_route,
                    "response_preview": r.response_preview,
                    "error": r.error,
                }
                for r in agg.runs
            ],
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  JSON report saved → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="WebVox Performance Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mode", choices=["http", "direct"], default="http",
        help="'http' sends real HTTP requests; 'direct' calls VoiceBotManager in-process.",
    )
    p.add_argument(
        "--url", default="http://localhost:8000",
        help="Base URL of the FastAPI server (http mode only).",
    )
    p.add_argument(
        "--runs", type=int, default=3,
        help="Number of times to run each test case (default: 3).",
    )
    p.add_argument(
        "--timeout", type=int, default=120,
        help="HTTP request timeout in seconds (default: 120).",
    )
    p.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds to wait between requests to avoid rate-limiting (default: 1.0).",
    )
    p.add_argument(
        "--cases", nargs="+", metavar="NAME",
        help="Run only the named test cases (partial match, case-insensitive).",
    )
    p.add_argument(
        "--json-out", metavar="FILE", default=None,
        help="Save full results as a JSON file (e.g. results/benchmark.json).",
    )
    p.add_argument(
        "--no-previews", action="store_true",
        help="Skip printing response previews.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Filter test cases if --cases was specified ────────────────────────────
    cases = TEST_CASES
    if args.cases:
        filters = [f.lower() for f in args.cases]
        cases = [
            tc for tc in TEST_CASES
            if any(f in tc.name.lower() for f in filters)
        ]
        if not cases:
            print(f"{_C['red']}No test cases matched: {args.cases}{_C['reset']}")
            sys.exit(1)

    # ── Direct mode: import the manager once ─────────────────────────────────
    manager = None
    if args.mode == "direct":
        print(f"{_C['cyan']}Loading VoiceBotManager (direct mode)…{_C['reset']}")
        try:
            # Ensure the webvox-bot root is on sys.path when running from scripts/
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from dotenv import load_dotenv
            load_dotenv()
            from services.voicebot.voicebot_manager import VoiceBotManager
            manager = VoiceBotManager()
            print(f"{_C['green']}  ✓ VoiceBotManager ready{_C['reset']}\n")
        except Exception as exc:
            print(f"{_C['red']}Failed to load VoiceBotManager: {exc}{_C['reset']}")
            sys.exit(1)

    # ── HTTP mode: verify server is reachable ─────────────────────────────────
    if args.mode == "http":
        import requests
        try:
            requests.get(args.url, timeout=5)
            print(f"{_C['green']}  ✓ Server reachable at {args.url}{_C['reset']}\n")
        except Exception:
            print(
                f"{_C['red']}  ✗ Cannot reach {args.url}. "
                f"Is the FastAPI server running?{_C['reset']}"
            )
            sys.exit(1)

    # ── Run all test cases ────────────────────────────────────────────────────
    all_runs: List[RunResult] = []
    aggregated: List[AggregatedResult] = []

    total = len(cases) * args.runs
    done  = 0

    for tc in cases:
        agg = AggregatedResult(test_case=tc)
        # Each test case gets its own session so history doesn't bleed across cases
        session_id = f"bench_{tc.name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}"

        for run_idx in range(1, args.runs + 1):
            done += 1
            print(
                f"  [{done:>3}/{total}] {_C['bold']}{tc.name}{_C['reset']} "
                f"(run {run_idx}/{args.runs})… ",
                end="",
                flush=True,
            )

            if args.mode == "http":
                result = run_http(tc, run_idx, args.url, session_id, args.timeout)
            else:
                result = run_direct(tc, run_idx, session_id, manager)

            agg.runs.append(result)
            all_runs.append(result)

            # Live feedback
            if result.success:
                lg = f"LG={_fmt_time(result.langgraph_time).strip()}" if result.langgraph_time else ""
                print(
                    f"{_C['green']}✓{_C['reset']} "
                    f"E2E={result.e2e_latency:.3f}s  {lg}  "
                    f"route={_route_colour(result.actual_route)}{result.actual_route}{_C['reset']}"
                )
            else:
                print(f"{_C['red']}✗ {result.error or 'unknown error'}{_C['reset']}")

            # Polite delay between requests
            if done < total:
                time.sleep(args.delay)

        aggregated.append(agg)

    # ── Output ────────────────────────────────────────────────────────────────
    if args.runs > 1:
        print_run_table(all_runs)

    print_summary_table(aggregated, args.mode)

    if not args.no_previews:
        print_response_previews(aggregated)

    if args.json_out:
        save_json_report(aggregated, args.json_out)

    # ── Exit code: non-zero if any run failed ─────────────────────────────────
    failed = sum(1 for r in all_runs if not r.success)
    if failed:
        print(f"{_C['red']}  {failed}/{total} run(s) failed.{_C['reset']}\n")
        sys.exit(1)
    else:
        print(f"{_C['green']}  All {total} run(s) passed.{_C['reset']}\n")


if __name__ == "__main__":
    main()
