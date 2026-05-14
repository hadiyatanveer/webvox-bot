#!/usr/bin/env python3
"""
WebVox NLU Accuracy Evaluator
================================
Directly calls detect_intent() to measure the Natural Language Understanding
accuracy of the intent classifier across three dimensions:

  1. Intent Category Accuracy  — did the model pick the right category?
                                 (action / information / unknown / greeting)
  2. Entity Extraction F1      — how well did it extract the right entities?
  3. Coreference Resolution    — does conversation history fix pronoun references?

Usage (from the webvox-bot/ directory):
    python scripts/evaluate_accuracy.py
    python scripts/evaluate_accuracy.py --verbose
    python scripts/evaluate_accuracy.py --filter action
    python scripts/evaluate_accuracy.py --json-out results/accuracy.json

The script imports detect_intent directly — no running server required.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Make sure the webvox-bot root is importable when run from scripts/ ────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env before importing anything that reads env vars
from dotenv import load_dotenv
load_dotenv()

# ── Colour helpers ────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    _C = {
        "green":  Fore.GREEN,
        "red":    Fore.RED,
        "yellow": Fore.YELLOW,
        "cyan":   Fore.CYAN,
        "magenta": Fore.MAGENTA,
        "bold":   Style.BRIGHT,
        "reset":  Style.RESET_ALL,
    }
except ImportError:
    _C = {k: "" for k in ("green", "red", "yellow", "cyan", "magenta", "bold", "reset")}


# =============================================================================
# TEST DATASET
# =============================================================================
# Each entry is a dict with:
#   query             : str   — the raw user utterance
#   expected_category : str   — "action" | "information" | "unknown" | "greeting"
#   expected_intent   : str   — specific intent label (used for display only)
#   expected_entities : dict  — key/value pairs that MUST appear in the output
#                               (partial match — extra entities are fine)
#   chat_history      : list  — optional prior turns for coreference tests
#   group             : str   — logical group label for the summary table
#   notes             : str   — human-readable description
# =============================================================================

DATASET: List[Dict[str, Any]] = [

    # ─────────────────────────────────────────────────────────────────────────
    # GROUP 1 — ACTION  (place orders, reservations, reviews, cancellations)
    # Expected: category == "action"
    # ─────────────────────────────────────────────────────────────────────────
    {
        "group": "Action",
        "query": "Place an order for 2 Margherita pizzas.",
        "expected_category": "action",
        "expected_intent": "place_order",
        "expected_entities": {"quantity": 2, "product_name": "Margherita"},
        "notes": "Complete order — quantity + product name both present",
    },
    {
        "group": "Action",
        "query": "I want to cancel my last order.",
        "expected_category": "action",
        "expected_intent": "cancel_order",
        "expected_entities": {},
        "notes": "Cancellation intent with no specific order ID",
    },
    {
        "group": "Action",
        "query": "Book a table for 4 people this Saturday at 8 PM.",
        "expected_category": "action",
        "expected_intent": "make_reservation",
        "expected_entities": {"quantity": 4},
        "notes": "Reservation with guest count entity",
    },
    {
        "group": "Action",
        "query": "Order 1 Chicken Burger and 2 Cokes please.",
        "expected_category": "action",
        "expected_intent": "place_order",
        "expected_entities": {"quantity": 1},
        "notes": "Multi-item order — at least one quantity extracted",
    },
    {
        "group": "Action",
        "query": "Leave a 5-star review for the Seafood Platter.",
        "expected_category": "action",
        "expected_intent": "leave_review",
        "expected_entities": {"product_name": "Seafood Platter"},
        "notes": "Review action with product entity",
    },
    {
        "group": "Action",
        "query": "Update my delivery address to 42 Baker Street.",
        "expected_category": "action",
        "expected_intent": "update_profile",
        "expected_entities": {},
        "notes": "Profile update action",
    },
    {
        "group": "Action",
        "query": "Add extra cheese to my pizza order.",
        "expected_category": "action",
        "expected_intent": "modify_order",
        "expected_entities": {},
        "notes": "Order modification action",
    },

    # ─────────────────────────────────────────────────────────────────────────
    # GROUP 2 — INFORMATION  (menu, prices, policies, order status)
    # Expected: category == "information"
    # ─────────────────────────────────────────────────────────────────────────
    {
        "group": "Information",
        "query": "What is your refund policy?",
        "expected_category": "information",
        "expected_intent": "get_policies",
        "expected_entities": {},
        "notes": "Policy query — should hit vector store",
    },
    {
        "group": "Information",
        "query": "How much does the Margherita pizza cost?",
        "expected_category": "information",
        "expected_intent": "get_price",
        "expected_entities": {"product_name": "Margherita"},
        "notes": "Price query with product entity",
    },
    {
        "group": "Information",
        "query": "Show me all vegetarian options on the menu.",
        "expected_category": "information",
        "expected_intent": "get_menu_items",
        "expected_entities": {},
        "notes": "Filtered menu query",
    },
    {
        "group": "Information",
        "query": "What is the status of my order?",
        "expected_category": "information",
        "expected_intent": "get_order_status",
        "expected_entities": {},
        "notes": "Order status lookup",
    },
    {
        "group": "Information",
        "query": "How many calories does the Caesar Salad have?",
        "expected_category": "information",
        "expected_intent": "get_nutrition",
        "expected_entities": {"product_name": "Caesar Salad"},
        "notes": "Nutrition info with product entity",
    },
    {
        "group": "Information",
        "query": "What are your opening hours?",
        "expected_category": "information",
        "expected_intent": "get_hours",
        "expected_entities": {},
        "notes": "Business hours query",
    },
    {
        "group": "Information",
        "query": "Do you offer gluten-free pizza?",
        "expected_category": "information",
        "expected_intent": "get_menu_items",
        "expected_entities": {},
        "notes": "Dietary restriction query",
    },

    # ─────────────────────────────────────────────────────────────────────────
    # GROUP 3 — GREETING / UNKNOWN  (off-topic, vague, greetings)
    # Expected: category == "greeting" or "unknown"
    # ─────────────────────────────────────────────────────────────────────────
    {
        "group": "Greeting/Unknown",
        "query": "Hello! What can you do?",
        "expected_category": "greeting",
        "expected_intent": "greeting",
        "expected_entities": {},
        "notes": "Standard greeting — should NOT be classified as unknown",
    },
    {
        "group": "Greeting/Unknown",
        "query": "Hi there!",
        "expected_category": "greeting",
        "expected_intent": "greeting",
        "expected_entities": {},
        "notes": "Minimal greeting",
    },
    {
        "group": "Greeting/Unknown",
        "query": "What is the weather like today?",
        "expected_category": "unknown",
        "expected_intent": "unknown",
        "expected_entities": {},
        "notes": "Completely off-topic — should be unknown",
    },
    {
        "group": "Greeting/Unknown",
        "query": "Tell me a joke.",
        "expected_category": "unknown",
        "expected_intent": "unknown",
        "expected_entities": {},
        "notes": "Off-topic entertainment request",
    },
    {
        "group": "Greeting/Unknown",
        "query": "asdfghjkl",
        "expected_category": "unknown",
        "expected_intent": "unknown",
        "expected_entities": {},
        "notes": "Gibberish input — robustness test",
    },

    # ─────────────────────────────────────────────────────────────────────────
    # GROUP 4 — COREFERENCE RESOLUTION  (multi-turn, requires chat_history)
    # These tests verify that the conversation history feature works correctly.
    # Each entry has a chat_history that simulates prior turns.
    # ─────────────────────────────────────────────────────────────────────────
    {
        "group": "Coreference",
        "query": "Order two of those.",
        "expected_category": "action",
        "expected_intent": "place_order",
        "expected_entities": {"quantity": 2, "product_name": "Margherita"},
        "chat_history": [
            {"role": "user",      "content": "What is the price of the Margherita pizza?"},
            {"role": "assistant", "content": "The Margherita pizza costs Rs. 850."},
            {"role": "user",      "content": "Order two of those."},
        ],
        "notes": "Pronoun 'those' must resolve to 'Margherita' from prior turn",
    },
    {
        "group": "Coreference",
        "query": "How many calories does it have?",
        "expected_category": "information",
        "expected_intent": "get_nutrition",
        "expected_entities": {"product_name": "Caesar Salad"},
        "chat_history": [
            {"role": "user",      "content": "Tell me about the Caesar Salad."},
            {"role": "assistant", "content": "The Caesar Salad is a fresh mix of romaine lettuce, croutons, and parmesan."},
            {"role": "user",      "content": "How many calories does it have?"},
        ],
        "notes": "Pronoun 'it' must resolve to 'Caesar Salad' from prior turn",
    },
    {
        "group": "Coreference",
        "query": "Can I get the large size?",
        "expected_category": "action",
        "expected_intent": "place_order",
        "expected_entities": {"product_name": "Pepperoni"},
        "chat_history": [
            {"role": "user",      "content": "I'd like to order a Pepperoni pizza."},
            {"role": "assistant", "content": "Sure! What size would you like — small, medium, or large?"},
            {"role": "user",      "content": "Can I get the large size?"},
        ],
        "notes": "Follow-up size selection — product must carry over from prior turn",
    },
    {
        "group": "Coreference",
        "query": "What about the vegetarian one?",
        "expected_category": "information",
        "expected_intent": "get_menu_items",
        "expected_entities": {},
        "chat_history": [
            {"role": "user",      "content": "Show me your burger options."},
            {"role": "assistant", "content": "We have the Classic Burger, Spicy Burger, and Veggie Burger."},
            {"role": "user",      "content": "What about the vegetarian one?"},
        ],
        "notes": "Implicit reference to 'Veggie Burger' from prior assistant turn",
    },
    {
        "group": "Coreference",
        "query": "Cancel it.",
        "expected_category": "action",
        "expected_intent": "cancel_order",
        "expected_entities": {},
        "chat_history": [
            {"role": "user",      "content": "I placed an order for a Chicken Burger."},
            {"role": "assistant", "content": "Your order for a Chicken Burger has been placed. Order ID is 42."},
            {"role": "user",      "content": "Cancel it."},
        ],
        "notes": "Pronoun 'it' refers to the recently placed order",
    },
]


# =============================================================================
# RESULT CONTAINERS
# =============================================================================

@dataclass
class CaseResult:
    """Outcome of running detect_intent on one test case."""
    # ── Input ─────────────────────────────────────────────────────────────────
    group: str
    query: str
    expected_category: str
    expected_intent: str
    expected_entities: Dict[str, Any]
    has_history: bool
    notes: str

    # ── Output ────────────────────────────────────────────────────────────────
    actual_category: str
    actual_intent: str
    actual_entities: Dict[str, Any]
    actual_confidence: float
    latency: float                  # seconds

    # ── Scores ────────────────────────────────────────────────────────────────
    category_correct: bool
    entity_precision: float         # TP / (TP + FP)
    entity_recall: float            # TP / (TP + FN)
    entity_f1: float                # harmonic mean of P and R

    error: Optional[str] = None


@dataclass
class GroupStats:
    name: str
    results: List[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def category_correct(self) -> int:
        return sum(1 for r in self.results if r.category_correct)

    @property
    def category_accuracy(self) -> float:
        return self.category_correct / self.total * 100 if self.total else 0.0

    @property
    def avg_entity_f1(self) -> float:
        vals = [r.entity_f1 for r in self.results]
        return sum(vals) / len(vals) * 100 if vals else 0.0

    @property
    def avg_confidence(self) -> float:
        vals = [r.actual_confidence for r in self.results if not r.error]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_latency(self) -> float:
        vals = [r.latency for r in self.results if not r.error]
        return sum(vals) / len(vals) if vals else 0.0


# =============================================================================
# EVALUATION LOGIC
# =============================================================================

def _normalise(value: Any) -> str:
    """Lowercase string representation for fuzzy entity comparison."""
    return str(value).lower().strip()


def _entity_scores(
    expected: Dict[str, Any],
    actual: Dict[str, Any],
) -> Tuple[float, float, float]:
    """
    Compute precision, recall, and F1 for entity extraction.

    Matching rules:
      - Keys must match exactly.
      - Values are compared case-insensitively as strings.
      - Numeric quantities: actual value must be within ±1 of expected
        (handles "2" vs 2 and minor off-by-one LLM errors).
      - String values: expected string must appear as a substring of the
        actual value (handles "Margherita" matching "Margherita Pizza").

    Returns (precision, recall, f1) each in [0.0, 1.0].
    """
    if not expected:
        # No entities required — perfect score by definition
        return 1.0, 1.0, 1.0

    tp = 0
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        if act_val is None:
            continue

        # Numeric comparison with tolerance
        try:
            if abs(float(act_val) - float(exp_val)) <= 1:
                tp += 1
                continue
        except (TypeError, ValueError):
            pass

        # String substring match (case-insensitive)
        if _normalise(exp_val) in _normalise(act_val):
            tp += 1

    fn = len(expected) - tp                        # expected but not found
    fp = max(0, len(actual) - tp - fn)             # found but not expected

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return round(precision, 3), round(recall, 3), round(f1, 3)


def evaluate_case(tc: Dict[str, Any]) -> CaseResult:
    """Run detect_intent on one test case and score the result."""
    from services.intent_detection.intent_detector import detect_intent

    query            = tc["query"]
    exp_category     = tc["expected_category"]
    exp_intent       = tc["expected_intent"]
    exp_entities     = tc.get("expected_entities", {})
    chat_history     = tc.get("chat_history")
    has_history      = bool(chat_history)

    t0 = time.perf_counter()
    try:
        result = detect_intent(
            user_text=query,
            chat_history=chat_history,
        )
        latency = round(time.perf_counter() - t0, 3)
    except Exception as exc:
        latency = round(time.perf_counter() - t0, 3)
        return CaseResult(
            group=tc.get("group", "?"),
            query=query,
            expected_category=exp_category,
            expected_intent=exp_intent,
            expected_entities=exp_entities,
            has_history=has_history,
            notes=tc.get("notes", ""),
            actual_category="error",
            actual_intent="error",
            actual_entities={},
            actual_confidence=0.0,
            latency=latency,
            category_correct=False,
            entity_precision=0.0,
            entity_recall=0.0,
            entity_f1=0.0,
            error=str(exc),
        )

    act_category   = result.get("category", "unknown")
    act_intent     = result.get("intent", "unknown")
    act_confidence = float(result.get("confidence", 0.0))

    # Filter None values from actual entities before scoring
    act_entities = {
        k: v for k, v in result.get("entities", {}).items()
        if v is not None
    }

    cat_correct = (act_category == exp_category)
    precision, recall, f1 = _entity_scores(exp_entities, act_entities)

    return CaseResult(
        group=tc.get("group", "?"),
        query=query,
        expected_category=exp_category,
        expected_intent=exp_intent,
        expected_entities=exp_entities,
        has_history=has_history,
        notes=tc.get("notes", ""),
        actual_category=act_category,
        actual_intent=act_intent,
        actual_entities=act_entities,
        actual_confidence=act_confidence,
        latency=latency,
        category_correct=cat_correct,
        entity_precision=precision,
        entity_recall=recall,
        entity_f1=f1,
    )


# =============================================================================
# OUTPUT / DISPLAY
# =============================================================================

def _col(text: str, width: int, align: str = "<") -> str:
    text = str(text)
    if len(text) > width:
        text = text[: width - 1] + "…"
    return f"{text:{align}{width}}"


def _pct(val: float, decimals: int = 1) -> str:
    return f"{val:.{decimals}f}%"


def _cat_colour(category: str, correct: bool) -> str:
    if not correct:
        return _C["red"]
    cat = category.lower()
    if cat == "action":
        return _C["yellow"]
    if cat == "information":
        return _C["cyan"]
    if cat in ("greeting", "unknown"):
        return _C["green"]
    return ""


def _f1_colour(f1: float) -> str:
    if f1 >= 0.9:
        return _C["green"]
    if f1 >= 0.6:
        return _C["yellow"]
    return _C["red"]


def print_detail_table(results: List[CaseResult], verbose: bool) -> None:
    """Print a per-case detail table."""
    W = {
        "idx":   3,
        "group": 14,
        "query": 38,
        "exp_c": 13,
        "act_c": 13,
        "cat":   5,
        "f1":    6,
        "conf":  6,
        "lat":   7,
        "hist":  5,
    }
    sep = "─" * (sum(W.values()) + len(W) * 3 + 1)

    header = (
        f" {'#':>{W['idx']}} │ {_col('Group', W['group'])} │ "
        f"{_col('Query', W['query'])} │ "
        f"{_col('Exp Cat', W['exp_c'])} │ "
        f"{_col('Act Cat', W['act_c'])} │ "
        f"{'Cat?':^{W['cat']}} │ "
        f"{'EntF1':^{W['f1']}} │ "
        f"{'Conf':^{W['conf']}} │ "
        f"{'Lat':^{W['lat']}} │ "
        f"{'Hist':^{W['hist']}} "
    )

    print(f"\n{_C['bold']}Per-Case Results{_C['reset']}")
    print(sep)
    print(header)
    print(sep)

    for i, r in enumerate(results, 1):
        cat_ok  = f"{_C['green']} ✓ {_C['reset']}" if r.category_correct else f"{_C['red']} ✗ {_C['reset']}"
        f1_c    = _f1_colour(r.entity_f1)
        cc      = _cat_colour(r.actual_category, r.category_correct)
        hist_ic = f"{_C['magenta']}  ⟳  {_C['reset']}" if r.has_history else "     "

        print(
            f" {i:>{W['idx']}} │ {_col(r.group, W['group'])} │ "
            f"{_col(r.query, W['query'])} │ "
            f"{_col(r.expected_category, W['exp_c'])} │ "
            f"{cc}{_col(r.actual_category, W['act_c'])}{_C['reset']} │ "
            f"{cat_ok:^{W['cat']}} │ "
            f"{f1_c}{_pct(r.entity_f1 * 100, 0):^{W['f1']}}{_C['reset']} │ "
            f"{r.actual_confidence:^{W['conf']}.2f} │ "
            f"{r.latency:^{W['lat']}.2f}s │ "
            f"{hist_ic}"
        )

        # Verbose: show entity diff on failures
        if verbose and (not r.category_correct or r.entity_f1 < 1.0):
            if r.error:
                print(f"    {_C['red']}ERROR: {r.error}{_C['reset']}")
            else:
                if not r.category_correct:
                    print(
                        f"    {_C['red']}Category mismatch: "
                        f"expected '{r.expected_category}', got '{r.actual_category}'{_C['reset']}"
                    )
                if r.entity_f1 < 1.0 and r.expected_entities:
                    print(
                        f"    {_C['yellow']}Entities — "
                        f"expected: {r.expected_entities}  |  "
                        f"actual: {r.actual_entities}{_C['reset']}"
                    )
                if r.has_history:
                    print(
                        f"    {_C['magenta']}[Coreference test — history was provided]{_C['reset']}"
                    )

    print(sep)


def print_group_summary(groups: Dict[str, GroupStats]) -> None:
    """Print per-group accuracy table."""
    W = {"group": 20, "total": 7, "cat_acc": 12, "ent_f1": 12, "conf": 10, "lat": 10}
    sep = "─" * (sum(W.values()) + len(W) * 3 + 1)

    header = (
        f" {_col('Group', W['group'])} │ "
        f"{'Cases':^{W['total']}} │ "
        f"{'Cat Accuracy':^{W['cat_acc']}} │ "
        f"{'Avg Ent F1':^{W['ent_f1']}} │ "
        f"{'Avg Conf':^{W['conf']}} │ "
        f"{'Avg Latency':^{W['lat']}} "
    )

    print(f"\n{_C['bold']}Group Summary{_C['reset']}")
    print(sep)
    print(header)
    print(sep)

    for name, gs in groups.items():
        cat_c = _C["green"] if gs.category_accuracy >= 80 else _C["yellow"] if gs.category_accuracy >= 60 else _C["red"]
        f1_c  = _f1_colour(gs.avg_entity_f1 / 100)
        print(
            f" {_col(name, W['group'])} │ "
            f"{gs.total:^{W['total']}} │ "
            f"{cat_c}{_pct(gs.category_accuracy):^{W['cat_acc']}}{_C['reset']} │ "
            f"{f1_c}{_pct(gs.avg_entity_f1):^{W['ent_f1']}}{_C['reset']} │ "
            f"{gs.avg_confidence:^{W['conf']}.2f} │ "
            f"{gs.avg_latency:^{W['lat']}.2f}s "
        )

    print(sep)


def print_scorecard(results: List[CaseResult]) -> None:
    """Print the headline accuracy scorecard — the numbers for your slides."""
    total = len(results)
    if total == 0:
        return

    # ── Category accuracy ─────────────────────────────────────────────────────
    cat_correct = sum(1 for r in results if r.category_correct)
    cat_acc     = cat_correct / total * 100

    # ── Entity F1 (macro-average over cases that have expected entities) ──────
    entity_cases = [r for r in results if r.expected_entities]
    avg_f1 = (
        sum(r.entity_f1 for r in entity_cases) / len(entity_cases) * 100
        if entity_cases else 0.0
    )

    # ── Coreference accuracy ──────────────────────────────────────────────────
    coref_cases   = [r for r in results if r.has_history]
    coref_correct = sum(1 for r in coref_cases if r.category_correct)
    coref_acc     = coref_correct / len(coref_cases) * 100 if coref_cases else 0.0

    # ── Per-category breakdown ────────────────────────────────────────────────
    categories = ["action", "information", "greeting", "unknown"]
    cat_breakdown: Dict[str, Dict[str, int]] = {
        c: {"total": 0, "correct": 0} for c in categories
    }
    for r in results:
        ec = r.expected_category
        if ec in cat_breakdown:
            cat_breakdown[ec]["total"] += 1
            if r.category_correct:
                cat_breakdown[ec]["correct"] += 1

    # ── Average latency ───────────────────────────────────────────────────────
    avg_lat = sum(r.latency for r in results) / total

    # ── Print ─────────────────────────────────────────────────────────────────
    thick = "═" * 62
    thin  = "─" * 62

    def _score_colour(val: float) -> str:
        if val >= 85:  return _C["green"]
        if val >= 65:  return _C["yellow"]
        return _C["red"]

    print(f"\n{_C['bold']}{thick}")
    print(f"  WebVox NLU Accuracy Scorecard  ({total} test cases)")
    print(f"{thick}{_C['reset']}")

    print(f"\n  {'Metric':<38} {'Score':>10}  {'Bar'}")
    print(f"  {thin}")

    def _bar(val: float, width: int = 20) -> str:
        filled = round(val / 100 * width)
        return "█" * filled + "░" * (width - filled)

    metrics = [
        ("Intent Category Accuracy",    cat_acc,   "primary"),
        ("Entity Extraction F1 (macro)", avg_f1,   "primary"),
        ("Coreference Resolution Acc.",  coref_acc, "coref"),
    ]
    for label, val, kind in metrics:
        sc = _score_colour(val)
        bar = _bar(val)
        print(f"  {label:<38} {sc}{_pct(val, 1):>10}{_C['reset']}  {sc}{bar}{_C['reset']}")

    print(f"\n  {thin}")
    print(f"  {'Per-Category Breakdown':}")
    print(f"  {thin}")
    for cat in categories:
        bd = cat_breakdown[cat]
        if bd["total"] == 0:
            continue
        acc = bd["correct"] / bd["total"] * 100
        sc  = _score_colour(acc)
        bar = _bar(acc, 12)
        print(
            f"  {cat.capitalize():<20} "
            f"{bd['correct']}/{bd['total']} correct   "
            f"{sc}{_pct(acc, 1):>7}{_C['reset']}  {sc}{bar}{_C['reset']}"
        )

    print(f"\n  {thin}")
    print(f"  {'Avg detect_intent latency':<38} {avg_lat:>9.3f}s")
    print(f"  {thin}")
    print(f"\n  {_C['bold']}Overall NLU Score  =  "
          f"(Cat Acc + Ent F1) / 2  =  "
          f"{_score_colour((cat_acc + avg_f1) / 2)}"
          f"{_pct((cat_acc + avg_f1) / 2, 1)}{_C['reset']}\n")
    print(f"{_C['bold']}{thick}{_C['reset']}\n")


def save_json_report(results: List[CaseResult], path: str) -> None:
    """Persist full results as JSON."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    report = [
        {
            "group": r.group,
            "query": r.query,
            "has_history": r.has_history,
            "notes": r.notes,
            "expected": {
                "category": r.expected_category,
                "intent":   r.expected_intent,
                "entities": r.expected_entities,
            },
            "actual": {
                "category":   r.actual_category,
                "intent":     r.actual_intent,
                "entities":   r.actual_entities,
                "confidence": r.actual_confidence,
            },
            "scores": {
                "category_correct": r.category_correct,
                "entity_precision": r.entity_precision,
                "entity_recall":    r.entity_recall,
                "entity_f1":        r.entity_f1,
            },
            "latency_s": r.latency,
            "error": r.error,
        }
        for r in results
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  JSON report saved → {path}")


# =============================================================================
# MAIN
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="WebVox NLU Accuracy Evaluator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--filter", metavar="GROUP",
        help="Run only cases whose group contains this string (case-insensitive). "
             "E.g. --filter action  or  --filter coref",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show entity diffs and mismatch details for every failing case.",
    )
    p.add_argument(
        "--delay", type=float, default=0.5,
        help="Seconds to wait between LLM calls to avoid rate-limiting (default: 0.5).",
    )
    p.add_argument(
        "--json-out", metavar="FILE", default=None,
        help="Save full results as JSON (e.g. results/accuracy.json).",
    )
    p.add_argument(
        "--no-detail", action="store_true",
        help="Skip the per-case detail table; show only the scorecard.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Filter dataset ────────────────────────────────────────────────────────
    dataset = DATASET
    if args.filter:
        f = args.filter.lower()
        dataset = [tc for tc in DATASET if f in tc.get("group", "").lower()]
        if not dataset:
            print(f"{_C['red']}No test cases matched group filter: '{args.filter}'{_C['reset']}")
            sys.exit(1)

    total = len(dataset)
    print(f"\n{_C['bold']}WebVox NLU Accuracy Evaluator{_C['reset']}")
    print(f"  {total} test cases  |  calling detect_intent() directly\n")

    # ── Run evaluation ────────────────────────────────────────────────────────
    all_results: List[CaseResult] = []

    for i, tc in enumerate(dataset, 1):
        hist_tag = f" {_C['magenta']}[history]{_C['reset']}" if tc.get("chat_history") else ""
        print(
            f"  [{i:>2}/{total}] {_C['bold']}{tc['group']}{_C['reset']} — "
            f"{tc['query'][:55]}{'…' if len(tc['query']) > 55 else ''}{hist_tag} … ",
            end="",
            flush=True,
        )

        result = evaluate_case(tc)
        all_results.append(result)

        # Live feedback
        if result.error:
            print(f"{_C['red']}ERROR: {result.error[:60]}{_C['reset']}")
        else:
            cat_icon = f"{_C['green']}✓{_C['reset']}" if result.category_correct else f"{_C['red']}✗{_C['reset']}"
            f1_c = _f1_colour(result.entity_f1)
            print(
                f"{cat_icon} cat={_C['cyan']}{result.actual_category}{_C['reset']}  "
                f"f1={f1_c}{_pct(result.entity_f1 * 100, 0)}{_C['reset']}  "
                f"conf={result.actual_confidence:.2f}  "
                f"{result.latency:.2f}s"
            )

        # Rate-limit guard
        if i < total:
            time.sleep(args.delay)

    # ── Build group stats ─────────────────────────────────────────────────────
    groups: Dict[str, GroupStats] = {}
    for r in all_results:
        if r.group not in groups:
            groups[r.group] = GroupStats(name=r.group)
        groups[r.group].results.append(r)

    # ── Output ────────────────────────────────────────────────────────────────
    if not args.no_detail:
        print_detail_table(all_results, verbose=args.verbose)

    print_group_summary(groups)
    print_scorecard(all_results)

    if args.json_out:
        save_json_report(all_results, args.json_out)

    # ── Exit code ─────────────────────────────────────────────────────────────
    failed_cat = sum(1 for r in all_results if not r.category_correct)
    if failed_cat:
        print(
            f"{_C['yellow']}  {failed_cat}/{total} category mismatches detected.{_C['reset']}\n"
        )
        sys.exit(1)
    else:
        print(f"{_C['green']}  All {total} category predictions correct.{_C['reset']}\n")


if __name__ == "__main__":
    main()
