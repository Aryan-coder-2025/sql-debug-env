"""
dynamic_schema.py — Dynamic Schema & Data Generation Module

This module generates completely random SQLite schemas with realistic, 
messy data (using Faker) and configurable noise (NULLs, duplicates, bad types).
It provides `DynamicSQLEnv`, a drop-in replacement for `SQLDebugEnv` that 
injects these dynamic databases instead of static ones.
"""

import sqlite3
import random
import string
import uuid
import os
import tempfile
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, List

try:
    from faker import Faker
except ImportError:
    Faker = None

# Fallback in case we need to import models/env
try:
    from environment import SQLDebugEnv
    from models import TaskInfo, SQLObservation, SQLAction
except ImportError:
    # Placholders if run isolated
    SQLDebugEnv = object
    TaskInfo = None


def _random_hash(length=6) -> str:
    """Generate a random alphanumeric hash for table names."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_random_schema(seed: int = None, num_tables: Tuple[int, int] = (2, 5)) -> str:
    """
    Generates a realistic, messy random SQLite database.
    
    Returns:
        str: File path to the generated SQLite database.
    """
    if Faker is None:
         raise ImportError("The 'faker' package is required. Run: pip install faker")
    
    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)
    
    fake = Faker()
    table_count = random.randint(*num_tables)
    
    # Store schema definitions
    schema_ddl = []
    tables_meta = []
    
    db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="dynamic_db_")
    os.close(db_fd)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Supported types and faker generators
    types = ["INTEGER", "VARCHAR(255)", "DATE", "FLOAT", "BOOLEAN"]
    
    # 1. Generate Schema
    for _ in range(table_count):
        base_names = ["users", "orders", "products", "transactions", "logs", "metrics", "events"]
        t_name = f"{random.choice(base_names)}_{_random_hash()}"
        
        col_count = random.randint(3, 8)
        columns = []
        columns_meta = []
        
        # Primary key
        columns.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
        columns_meta.append({"name": "id", "type": "INTEGER"})
        
        for p in range(col_count - 1):
            c_type = random.choice(types)
            # Make columns sounding realistic based on type
            if c_type == "INTEGER":
                c_name = random.choice(["age", "count", "score", "quantity", "level"])
            elif "VARCHAR" in c_type:
                c_name = random.choice(["name", "email", "status", "category", "description"])
            elif c_type == "DATE":
                c_name = random.choice(["created_at", "updated_at", "shipped_date", "order_date"])
            elif c_type == "FLOAT":
                c_name = random.choice(["price", "amount", "discount", "rating"])
            else:
                c_name = random.choice(["is_active", "has_error", "verified"])
            
            c_name = f"{c_name}_{_random_hash(3)}"
            constraints = ""
            
            if random.random() < 0.2:
                constraints = " NOT NULL"
            elif random.random() < 0.1 and "VARCHAR" in c_type:
                constraints = " UNIQUE"
                
            columns.append(f"{c_name} {c_type}{constraints}")
            columns_meta.append({"name": c_name, "type": c_type})
            
        ddl = f"CREATE TABLE {t_name} (\n    " + ",\n    ".join(columns) + "\n);"
        schema_ddl.append(ddl)
        tables_meta.append({"name": t_name, "columns": columns_meta})
        
        cursor.execute(ddl)
        
    # 2. Populate Data with Noise
    for table in tables_meta:
        t_name = table["name"]
        cols = table["columns"][1:] # skip 'id'
        col_names = [c["name"] for c in cols]
        
        placeholders = ",".join(["?" for _ in cols])
        insert_sql = f"INSERT OR IGNORE INTO {t_name} ({','.join(col_names)}) VALUES ({placeholders})"
        
        rows_to_generate = random.randint(50, 500)
        generated_rows = []
        
        for _ in range(rows_to_generate):
            row = []
            for c in cols:
                # 5-15% chance of NULL if allowed
                if random.random() < random.uniform(0.05, 0.15):
                    row.append(None)
                    continue
                    
                val = None
                if c["type"] == "INTEGER":
                    val = random.randint(1, 1000)
                elif "VARCHAR" in c["type"]:
                    if "email" in c["name"]:
                        val = fake.email()
                    elif "name" in c["name"]:
                        val = fake.name()
                    else:
                        val = fake.word()
                elif c["type"] == "DATE":
                    val = fake.date_between(start_date='-2y', end_date='today').isoformat()
                elif c["type"] == "FLOAT":
                    val = round(random.uniform(10.0, 5000.0), 2)
                    # Inject dirty data: "N/A" string in a numeric field (SQLite allows this)
                    if random.random() < 0.05:
                        val = "N/A"
                elif c["type"] == "BOOLEAN":
                    val = random.choice([True, False])
                    
                row.append(val)
            
            generated_rows.append(tuple(row))
            
            # 2-5% chance of duplicate row
            if random.random() < random.uniform(0.02, 0.05):
                generated_rows.append(tuple(row))
                
        cursor.executemany(insert_sql, generated_rows)
        
    conn.commit()
    conn.close()
    
    return db_path, "\n".join(schema_ddl), tables_meta


class DynamicSQLEnv(SQLDebugEnv):
    """
    A drop-in replacement for SQLDebugEnv that generates a random, messy schema
    for every new episode, instead of using static databases.
    """
    def __init__(self, seed: int = None):
        super().__init__()
        self.seed = seed

    
    def _load_task(self, task_id: str, scenario: str = None) -> TaskInfo:
        """
        Overrides the static task loader to generate a dynamic schema and
        a synthetic broken query with varied difficulty mutations.
        
        Difficulty is randomly selected to produce a mix of easy (1-2 step), 
        medium (3-5 step), and hard (5-10 step) debugging sessions.
        """
        # Set python's built-in random seed for reproducibility in mutation choices
        if self.seed is not None:
            random.seed(self.seed)

        # Generate new DB with at least 2 tables for JOIN-based bugs
        db_path, schema_str, tables = generate_random_schema(seed=self.seed, num_tables=(2, 4))
        
        # Pick primary and secondary tables
        target_table = tables[0]
        t_name = target_table["name"]
        all_cols = target_table["columns"]
        non_id_cols = [c for c in all_cols if c["name"] != "id"]
        
        # Pick query column(s)
        if len(non_id_cols) >= 2:
            col1 = non_id_cols[0]["name"]
            col2 = non_id_cols[1]["name"]
        elif len(non_id_cols) == 1:
            col1 = non_id_cols[0]["name"]
            col2 = "id"
        else:
            col1 = "id"
            col2 = "id"
        
        # Randomly pick difficulty tier with weighted distribution
        # 30% easy, 40% medium, 30% hard
        difficulty = random.choices(
            ["easy", "medium", "hard"],
            weights=[30, 40, 30],
            k=1
        )[0]
        
        # =====================================================================
        # EASY MUTATIONS: Syntax errors the agent can spot immediately
        # Agent needs 1-2 steps, mostly just reading the query carefully
        # =====================================================================
        if difficulty == "easy":
            correct_query = f"SELECT {col1} FROM {t_name} ORDER BY id LIMIT 10"
            mutation = random.choice([
                # 1. Missing FROM keyword
                f"SELECT {col1} RETRIEVE_FROM {t_name} LIMIT 10",
                # 2. Typo in SELECT
                f"SELCT {col1} FROM {t_name} ORDER BY id LIMIT 10",
                # 3. Wrong keyword ORDER
                f"SELECT {col1} FROM {t_name} ORDERD BY id LIMIT 10",
                # 4. Missing closing quote in string literal
                f"SELECT {col1} FROM {t_name} WHERE {col1} = 'test ORDER BY id LIMIT 10",
                # 5. Double comma in column list
                f"SELECT {col1},, {col2} FROM {t_name} ORDER BY id LIMIT 10",
            ])
            broken_query = mutation
        
        # =====================================================================
        # MEDIUM MUTATIONS: Schema/logic errors requiring investigation
        # Agent needs to DESCRIBE tables and check column names (3-5 steps)
        # =====================================================================
        elif difficulty == "medium":
            correct_query = f"SELECT {col1}, {col2} FROM {t_name} WHERE id > 0 ORDER BY id LIMIT 10"
            mutation = random.choice([
                # 1. Wrong column name (agent must DESCRIBE to find the right one)
                f"SELECT nonexistent_column, {col2} FROM {t_name} WHERE id > 0 ORDER BY id LIMIT 10",
                # 2. Wrong table name (agent must SHOW_TABLES to find the right one)
                f"SELECT {col1}, {col2} FROM wrong_table_name WHERE id > 0 ORDER BY id LIMIT 10",
                # 3. Missing WHERE column (plausible but wrong)
                f"SELECT {col1}, {col2} FROM {t_name} WHERE fake_status = 'active' ORDER BY id LIMIT 10",
                # 4. Using * but with a non-existent alias
                f"SELECT t.{col1}, t.{col2} FROM {t_name} AS x WHERE x.id > 0 ORDER BY x.id LIMIT 10",
                # 5. Wrong column in ORDER BY
                f"SELECT {col1}, {col2} FROM {t_name} WHERE id > 0 ORDER BY missing_col LIMIT 10",
            ])
            broken_query = mutation
        
        # =====================================================================
        # HARD MUTATIONS: Multi-table / logic errors requiring deep analysis
        # Agent needs SHOW_TABLES + DESCRIBE + EXPLAIN (5-10 steps)
        # =====================================================================
        else:  # hard
            second_table = tables[1] if len(tables) > 1 else tables[0]
            t2_name = second_table["name"]
            t2_cols = [c for c in second_table["columns"] if c["name"] != "id"]
            t2_col = t2_cols[0]["name"] if t2_cols else "id"
            
            correct_query = f"SELECT {col1}, {col2} FROM {t_name} WHERE id > 0 ORDER BY id LIMIT 10"
            mutation = random.choice([
                # 1. Broken JOIN with wrong ON clause
                f"SELECT a.{col1}, b.{t2_col} FROM {t_name} a JOIN {t2_name} b ON a.id = b.nonexistent_fk ORDER BY a.id LIMIT 10",
                # 2. Subquery referencing wrong table
                f"SELECT {col1} FROM {t_name} WHERE {col1} IN (SELECT {col1} FROM nonexistent_subtable) ORDER BY id LIMIT 10",
                # 3. Wrong aggregation with missing GROUP BY
                f"SELECT {col1}, COUNT(*) FROM {t_name} WHERE id > 0 ORDER BY id LIMIT 10",
                # 4. Mixed-up column references across tables
                f"SELECT {t2_col} FROM {t_name} WHERE {t2_col} IS NOT NULL ORDER BY id LIMIT 10",
                # 5. HAVING without GROUP BY
                f"SELECT {col1} FROM {t_name} HAVING COUNT(*) > 1 ORDER BY id LIMIT 10",
                # 6. Ambiguous column in a self-referencing context
                f"SELECT {col1}, {col2} FROM {t_name}, {t2_name} WHERE id > 0 ORDER BY id LIMIT 10",
            ])
            broken_query = mutation
        
        # Execute correct query to get expected output
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(correct_query)
        cols = [c[0] for c in cursor.description]
        expected_output = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()
        
        return TaskInfo(
            task_id=difficulty,
            broken_query=broken_query,
            schema_sql=schema_str,
            expected_output=expected_output,
            db_path=db_path
        )
        
    def close(self):
        """Clean up the temp dynamic db."""
        if hasattr(self, 'current_task') and self.current_task and self.current_task.db_path:
            try:
                if os.path.exists(self.current_task.db_path):
                    os.remove(self.current_task.db_path)
            except Exception:
                pass
        super().close()


"""
# ============================================================================
# INTEGRATION NOTES 
# ============================================================================

To use this dynamic schema generation module in your existing project without 
breaking existing code:

1. Install the `Faker` library:
   pip install faker

2. In your `main.py` or training script, swap the environment class imports.
   Instead of using `SQLDebugEnv`, use `DynamicSQLEnv`.

   # OLD:
   # from environment import SQLDebugEnv
   # default_env = SQLDebugEnv()
   
   # NEW:
   from dynamic_schema import DynamicSQLEnv
   default_env = DynamicSQLEnv()

That's it! `DynamicSQLEnv` fully inherits the `reset()`, `step()`, and OpenEnv 
WebSocket framework behavior from your existing implementation, but replaces the
`_load_task()` method to create custom DB paths with messy data on the fly.
"""
