import re
import sqlparse
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# ---------------------------------------------------------
# 1. Define Structured Output (API Ready)
# ---------------------------------------------------------
@dataclass
class DebuggerResponse:
    """Standardized response object for frontend/API consumption."""
    status: str          # 'success', 'warning', 'error'
    query_type: str      # 'SELECT', 'UPDATE', etc.
    message: str
    original_query: str
    suggested_query: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ---------------------------------------------------------
# 2. The Production Service Class
# ---------------------------------------------------------
class SQLAnalyzerService:
    def __init__(self):
        # We define behavior definitions here. No more regex patterns for query validation!
        self.join_behaviors = {
            'INNER JOIN': {
                'description': 'Returns only rows with a match in BOTH tables.',
                'keywords': ['both', 'match', 'common', 'intersection', 'matched', 'matching']
            },
            'LEFT JOIN': {
                'description': 'Returns ALL rows from the left table, and matched rows from the right.',
                'keywords': ['all left', 'left table', 'left all', 'unmatched right', 'null right', 'keep left']
            },
            'RIGHT JOIN': {
                'description': 'Returns ALL rows from the right table, and matched rows from the left.',
                'keywords': ['all right', 'right table', 'right all', 'unmatched left', 'null left', 'keep right']
            },
            'FULL OUTER JOIN': {
                'description': 'Returns ALL rows from BOTH tables.',
                'keywords': ['all rows', 'both tables', 'full', 'everything', 'all records', 'null both']
            },
            'CROSS JOIN': {
                'description': 'Returns the Cartesian product — every combination of rows.',
                'keywords': ['every combination', 'cartesian', 'all combinations', 'paired', 'cross', 'product']
            }
        }

    def validate_syntax(self, query: str) -> DebuggerResponse:
        """Parses the SQL using an AST to determine type and basic validity."""
        clean_query = query.strip()
        if not clean_query:
            return DebuggerResponse("error", "UNKNOWN", "Empty query provided.", clean_query)

        # Let the AST parse the query. It handles nested queries, strings, and comments safely.
        parsed_statements = sqlparse.parse(clean_query)
        if not parsed_statements:
            return DebuggerResponse("error", "UNKNOWN", "Unable to parse the SQL structure.", clean_query)

        statement = parsed_statements[0]
        query_type = statement.get_type()  # Automatically extracts 'SELECT', 'INSERT', 'DDL', etc.

        if query_type == "UNKNOWN":
            return DebuggerResponse("error", query_type, "Command not recognized.", clean_query)

        if not clean_query.endswith(';'):
            return DebuggerResponse("warning", query_type, "Missing terminator (;). Query might still execute depending on the engine.", clean_query)

        return DebuggerResponse(
            status="success",
            query_type=query_type,
            message=f"{query_type} query parsed successfully.",
            original_query=clean_query
        )

    def optimize_join(self, query: str, expected_output: str) -> DebuggerResponse:
        """Analyzes intended output and safely replaces the incorrect JOIN."""
        clean_query = query.strip()
        
        # AST helps us verify it's a SELECT statement first
        parsed = sqlparse.parse(clean_query)
        if not parsed or parsed[0].get_type() != "SELECT":
            return DebuggerResponse("error", "UNKNOWN", "JOIN optimization requires a valid SELECT query.", clean_query)

        # 1. Safely extract the FIRST join to prevent multi-join destruction
        join_pattern = r'\b(FULL OUTER JOIN|LEFT OUTER JOIN|RIGHT OUTER JOIN|INNER JOIN|LEFT JOIN|RIGHT JOIN|CROSS JOIN)\b'
        match = re.search(join_pattern, clean_query, re.IGNORECASE)

        if not match:
            return DebuggerResponse("error", "SELECT", "No recognizable JOIN clause detected.", clean_query)

        current_join = match.group(1).upper()

        # Normalize outer joins for matching
        if current_join == 'LEFT OUTER JOIN': current_join = 'LEFT JOIN'
        if current_join == 'RIGHT OUTER JOIN': current_join = 'RIGHT JOIN'

        # 2. Score behaviors based on user input
        expected_lower = expected_output.lower()
        scores = {
            join: sum(1 for kw in info['keywords'] if kw in expected_lower)
            for join, info in self.join_behaviors.items()
        }

        best_match = max(scores, key=scores.get)
        best_score = scores[best_match]

        if best_score == 0:
            return DebuggerResponse(
                status="warning",
                query_type="SELECT",
                message="Could not determine the correct JOIN from the description.",
                original_query=clean_query
            )

        if current_join == best_match:
            return DebuggerResponse(
                status="success",
                query_type="SELECT",
                message=f"Your JOIN is correct! {self.join_behaviors[current_join]['description']}",
                original_query=clean_query
            )

        # 3. Safely replace ONLY the first occurrence (count=1)
        fixed_query = re.sub(join_pattern, best_match, clean_query, count=1, flags=re.IGNORECASE)

        return DebuggerResponse(
            status="warning", # Warning indicates a fix was applied
            query_type="SELECT",
            message=f"Replaced {current_join} with {best_match}: {self.join_behaviors[best_match]['description']}",
            original_query=clean_query,
            suggested_query=fixed_query
        )

# ---------------------------------------------------------
# 3. Usage Example (How a backend would call this)
# ---------------------------------------------------------

if __name__ == "__main__":
    import json
    analyzer = SQLAnalyzerService()

    # Test 1: Syntax Validation
    print("\n--- Test 1: Syntax Validation ---")
    raw_query = input("Enter a SQL query to validate: ")
    
    validation = analyzer.validate_syntax(raw_query)
    print("\n--- Validation API Response ---")
    print(json.dumps(validation.to_dict(), indent=2))

    # Test 2: Join Optimization
    print("\n--- Test 2: Join Optimization ---")
    bad_join_query = input("Enter a query with a JOIN to optimize: ")
    user_intent = input("Describe your expected output: ")
    
    optimization = analyzer.optimize_join(bad_join_query, user_intent)
    print("\n--- Join Fixer API Response ---")
    print(json.dumps(optimization.to_dict(), indent=2))