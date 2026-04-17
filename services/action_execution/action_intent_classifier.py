"""
Action Intent Classifier Service for WebVox.
Refines 'action' category intents into specific database operations (insert, update, delete)
and enforces safety/security rules like disallowing deletes or cross-user modifications.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from utilities.config_loader import get_config
from utilities.llm_configure import generate_content
from utilities.prompt_loader import load_prompt
from services.graphql.schema_introspector import get_schema_introspector
from services.graphql.schema_analyzer import get_schema_analyzer


@dataclass
class ActionIntent:
    """Refined intent for performing a database action."""
    operation: str  # insert, update, delete
    primary_table: str
    secondary_tables: List[str]
    tables_data: Dict[str, Dict[str, Any]]  # data for primary and secondary tables
    missing_info: Dict[str, Any]  # is_complete, clarification_questions
    confidence: float
    reasoning: str
    error: Optional[str] = None


class ActionIntentClassifier:
    """
    LLM-based agent that classifies natural language action requests into
    structured database operations while enforcing safety rules.
    """
    
    def __init__(self):
        self.config = get_config()
        self.introspector = get_schema_introspector()
        self.analyzer = get_schema_analyzer()
    
    def classify_action(
        self,
        user_query: str,
        detected_entities: Optional[Dict[str, Any]] = None,
        previous_action_data: Optional[Dict[str, Any]] = None
    ) -> ActionIntent:
        """
        Refine an 'action' request into a specific operation and table.
        Incorporates previous state to handle iterative form filling.
        """
        detected_entities = detected_entities or {}
        previous_action_data = previous_action_data or {}
        
        # Get schema context with mutability hints
        schema_context = self.analyzer.build_schema_context()
        
        # Format the previous state for the LLM context
        previous_state_str = json.dumps(previous_action_data, indent=2) if previous_action_data else "None"
        
        # Prepare prompt
        prompt = load_prompt("action_intent_classifier", "classify_action.prompt.txt", {
            "schema_context": schema_context,
            "user_query": user_query,
            "detected_entities": json.dumps(detected_entities, indent=2),
            "previous_state": previous_state_str
        })
        
        try:
            response = generate_content(prompt)
            
            # Extract response text
            if hasattr(response, "candidates"):
                raw_text = response.candidates[0].content.parts[0].text
            elif hasattr(response, "content"):
                raw_text = response.content
            else:
                raw_text = str(response)
            
            # Parse JSON response
            new_action_data = self._parse_llm_response(raw_text)
            
            # MERGE LOGIC: If we have previous data, ensure we don't lose filled fields
            if previous_action_data:
                self._merge_previous_state(new_action_data, previous_action_data)
            
            # Validation Step
            self._validate_action(new_action_data)
            
            return new_action_data
            
        except Exception as e:
            print(f"  ⚠️ Action Intent Classifier error: {e}")
            return ActionIntent(
                operation="unknown",
                primary_table="unknown",
                secondary_tables=[],
                tables_data={},
                missing_info={"is_complete": False, "clarification_questions": ["I'm sorry, I'm having trouble processing your request. Could you rephrase it?"]},
                confidence=0.0,
                reasoning=f"Error in classification: {e}",
                error="Internal error processing action request."
            )
    
    def _merge_previous_state(self, new_action: ActionIntent, previous_data: Dict[str, Any]):
        """Ensure that previously filled data is preserved across turns."""
        prev_tables_data = previous_data.get("tables_data", {})
        
        # If the LLM successfully identified the same operation/table, merge the field values
        for table, prev_data in prev_tables_data.items():
            if table in new_action.tables_data:
                # Merge 'filled' fields
                merged_filled = prev_data.get("filled", {}).copy()
                merged_filled.update(new_action.tables_data[table].get("filled", {}))
                new_action.tables_data[table]["filled"] = merged_filled
                
                # Update 'missing' list by removing items that are now in merged_filled
                new_action.tables_data[table]["missing"] = [
                    f for f in new_action.tables_data[table].get("missing", [])
                    if f not in merged_filled
                ]
            else:
                # If the table was in the previous state but NOT in the new one, 
                # keep it as a secondary table unless the LLM explicitly changed the primary intent.
                new_action.tables_data[table] = prev_data
                if table not in new_action.secondary_tables and table != new_action.primary_table:
                    new_action.secondary_tables.append(table)

    def _parse_llm_response(self, raw_text: str) -> ActionIntent:
        """Extract and parse JSON from LLM response."""
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if not json_match:
            raise ValueError("Could not find JSON in LLM response")
            
        result = json.loads(json_match.group())
        
        return ActionIntent(
            operation=result.get("operation", "unknown"),
            primary_table=result.get("primary_table", "unknown"),
            secondary_tables=result.get("secondary_tables", []),
            tables_data=result.get("tables_data", {}),
            missing_info=result.get("missing_info", {"is_complete": False, "clarification_questions": []}),
            confidence=float(result.get("confidence", 0.0)),
            reasoning=result.get("reasoning", ""),
            error=result.get("error")
        )

    def _validate_action(self, action: ActionIntent):
        """Cross-reference LLM output with SchemaIntrospector for final safety check."""
        # 1. Block Deletes
        if action.operation == "delete":
            action.error = "Not possible due to high risk."
            return

        # 2. Check table existence and permissions
        all_tables = [action.primary_table] + action.secondary_tables
        schema_tables = self.introspector.get_all_table_names()
        
        for table in all_tables:
            if table == "unknown": continue
            if table not in schema_tables:
                action.error = f"Disallowed (invalid table: {table})"
                return
            
            table_info = self.introspector.get_table_info(table)
            if action.operation == "insert" and not table_info.can_insert:
                action.error = f"Disallowed (no permission to insert into {table})"
            elif action.operation == "update" and not table_info.can_update:
                action.error = f"Disallowed (no permission to update {table})"

        # 3. Clean table fields (only keep actual columns)
        for table, data in action.tables_data.items():
            if table not in schema_tables: continue
            valid_targets = self.introspector.get_mutable_fields(table)
            
            # Filter auto_fill, filled, and missing
            data["auto_fill"] = [f for f in data.get("auto_fill", []) if f in valid_targets]
            data["filled"] = {f: v for f, v in data.get("filled", {}).items() if f in valid_targets}
            data["missing"] = [f for f in data.get("missing", []) if f in valid_targets]


# Global instance
_classifier = None

def get_action_intent_classifier() -> ActionIntentClassifier:
    """Get the global action intent classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = ActionIntentClassifier()
    return _classifier
