import sqlite3
from langsmith import traceable, get_current_run_tree

QUERY_DATABASE_TOOL = {
    "type": "function",
    "function": {
        "name": "query_database",
        "description": "SQL query to get information about our inventory for customers like products, quantities and prices.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": """SQL query to execute against the inventory database.

YOU DO NOT KNOW THE SCHEMA. ALWAYS discover it first:
1. Query 'SELECT name FROM sqlite_master WHERE type="table"' to see available tables
2. Use 'PRAGMA table_info(table_name)' to inspect columns for each table
3. Only after understanding the schema, construct your search queries

The database contains product inventory, customer records, and order history. Use it to look up products, check stock and pricing, find customers by name or ID, and retrieve past orders.""",
                }
            },
            "required": ["query"],
        },
    },
}


@traceable(name="query_database", run_type="tool")
def query_database(query: str, db_path: str, langsmith_extra: dict | None = None) -> str:
    """Execute SQL query against the inventory database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        run = get_current_run_tree()
        if run:
            run.set(usage_metadata={"total_cost": 0.0007})
        return str(results)
    except Exception as e:
        return f"Error: {str(e)}"
