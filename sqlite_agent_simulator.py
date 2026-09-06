import json
import logging
import os
import sqlite3

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")

MODEL = "gpt-4o-mini"
MAX_ATTEMPTS = 8
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_sim.db")


# ---------------------------------------------------------------------------
# Simulated environment: a real, on-disk SQLite file with several related
# tables and a sample dataset that requires multi-hop joins to answer
# questions about it. Inspect it afterwards with e.g. `sqlite3 agent_sim.db`.
# ---------------------------------------------------------------------------

def build_database(db_path: str = DB_PATH) -> sqlite3.Connection:
    if os.path.exists(db_path):
        os.remove(db_path)  # start from a clean file each run

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE regions (
        region_id   INTEGER PRIMARY KEY,
        region_name TEXT NOT NULL
    );

    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        region_id   INTEGER REFERENCES regions(region_id),
        signup_date TEXT
    );

    CREATE TABLE employees (
        employee_id INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        department  TEXT
    );

    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        category   TEXT,
        price      REAL NOT NULL
    );

    CREATE TABLE orders (
        order_id    INTEGER PRIMARY KEY,
        customer_id INTEGER REFERENCES customers(customer_id),
        employee_id INTEGER REFERENCES employees(employee_id),
        order_date  TEXT,
        status      TEXT
    );

    CREATE TABLE order_items (
        order_item_id INTEGER PRIMARY KEY,
        order_id      INTEGER REFERENCES orders(order_id),
        product_id    INTEGER REFERENCES products(product_id),
        quantity      INTEGER NOT NULL
    );
    """)

    cur = conn.cursor()

    cur.executemany("INSERT INTO regions VALUES (?, ?)", [
        (1, "West"), (2, "East"), (3, "North"),
    ])

    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", [
        (1, "Aria Chen",     1, "2023-01-15"),
        (2, "Ben Okafor",    1, "2023-03-02"),
        (3, "Carla Suarez",  2, "2022-11-20"),
        (4, "Dev Patel",     1, "2024-02-10"),
        (5, "Elin Karlsson", 3, "2023-07-08"),
    ])

    cur.executemany("INSERT INTO employees VALUES (?, ?, ?)", [
        (1, "Sam Rivera", "Sales"),
        (2, "Priya Nair", "Sales"),
        (3, "Tom Becker", "Support"),
    ])

    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", [
        (1, "Widget",     "Hardware", 25.0),
        (2, "Gadget",     "Hardware", 60.0),
        (3, "Pro Plan",   "Software", 199.0),
        (4, "Basic Plan", "Software", 49.0),
        (5, "Cable",      "Hardware", 8.0),
    ])

    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", [
        (1, 1, 1, "2024-01-05", "completed"),
        (2, 1, 2, "2024-02-19", "completed"),
        (3, 2, 1, "2024-01-22", "completed"),
        (4, 3, 2, "2024-03-01", "completed"),
        (5, 4, 1, "2024-03-11", "completed"),
        (6, 2, 2, "2024-04-02", "completed"),
        (7, 5, 3, "2024-04-15", "completed"),
        (8, 4, 1, "2024-04-20", "completed"),
    ])

    cur.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?)", [
        (1,  1, 3, 1),  # order1: Pro Plan x1  = 199
        (2,  1, 1, 2),  # order1: Widget x2    =  50  -> order1 total 249
        (3,  2, 2, 3),  # order2: Gadget x3    = 180
        (4,  3, 4, 2),  # order3: Basic Plan x2=  98
        (5,  4, 3, 1),  # order4: Pro Plan x1  = 199
        (6,  5, 3, 2),  # order5: Pro Plan x2  = 398
        (7,  5, 5, 5),  # order5: Cable x5     =  40  -> order5 total 438
        (8,  6, 2, 1),  # order6: Gadget x1    =  60
        (9,  7, 4, 1),  # order7: Basic Plan x1=  49
        (10, 8, 3, 1),  # order8: Pro Plan x1  = 199
        (11, 8, 1, 4),  # order8: Widget x4    = 100  -> order8 total 299
    ])

    conn.commit()
    return conn


DB_CONN = build_database()


# ---------------------------------------------------------------------------
# Hardcoded tool implementations, backed by the real SQLite file above.
# These mirror an MCP SQLite server's tool surface: the model must discover
# tables, inspect their schema, and only then write SQL - it can't resolve
# the request in one shot, it has to plan, call a tool, read the result,
# and decide the next call.
# ---------------------------------------------------------------------------

def list_tables(args: dict) -> dict:
    rows = DB_CONN.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {"tables": [r[0] for r in rows]}


def get_schema(args: dict) -> dict:
    table = args.get("table")
    rows = DB_CONN.execute(f"PRAGMA table_info({table})").fetchall()
    if not rows:
        return {"error": f"unknown table {table!r}"}
    columns = [{"name": r[1], "type": r[2], "notnull": bool(r[3]), "pk": bool(r[5])} for r in rows]
    return {"table": table, "columns": columns}


def run_query(args: dict) -> dict:
    sql = (args.get("sql") or "").strip()
    if not sql.lower().startswith("select"):
        return {"error": "only SELECT statements are allowed"}
    try:
        cur = DB_CONN.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    except sqlite3.Error as e:
        return {"error": str(e)}
    return {"columns": columns, "rows": rows}


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "Lists all tables that exist in the SQLite database.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "Gets the column names and types for a given table, so you know what you can query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "name of the table to inspect, e.g. customers"},
                },
                "required": ["table"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_query",
            "description": "Executes a read-only SELECT query against the database and returns the resulting rows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "a single SELECT statement, e.g. SELECT * FROM customers"},
                },
                "required": ["sql"],
            },
        },
    },
]

TOOL_IMPL = {
    "list_tables": list_tables,
    "get_schema": get_schema,
    "run_query": run_query,
}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(user_message: str, max_attempts: int = MAX_ATTEMPTS) -> str:
    """Runs a tool-calling agent loop for up to max_attempts model calls.

    Each attempt: ask the model, log what it said and which tools (if any)
    it wants to run, execute those tools, feed results back, and repeat
    until the model answers without requesting a tool or max_attempts runs out.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "you are a data analyst agent. you can only see the database through "
                "the list_tables, get_schema, and run_query tools - never assume a table "
                "or column exists. always discover the tables and inspect the schema of "
                "any table before querying it, then answer the user's question using only "
                "the query results you observed."
            ),
        },
        {"role": "user", "content": user_message},
    ]
    tools_executed = 0
    log.info("=== Starting agent run (max_attempts=%d) ===", max_attempts)
    log.info("User query: %r", user_message)

    for attempt in range(1, max_attempts + 1):
        log.info("--- Progress: turn %d/%d | tools executed so far: %d ---", attempt, max_attempts, tools_executed)
        log.info("Sending request to %s", MODEL)
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SPEC,
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls

        if message.content:
            log.info("LLM processed response (turn %d): %s", attempt, message.content)

        if not tool_calls:
            log.info("Turn %d/%d: model returned a final answer, stopping loop", attempt, max_attempts)
            return message.content

        log.info("Turn %d/%d: model requested %d tool call(s): %s",
                  attempt, max_attempts, len(tool_calls), [tc.function.name for tc in tool_calls])

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            log.info("  -> calling tool %r with args=%s", tool_name, args)
            impl = TOOL_IMPL.get(tool_name)
            if impl is None:
                result = {"error": f"unknown tool {tool_name}"}
                log.warning("  -> tool %r not found", tool_name)
            else:
                result = impl(args)

            tools_executed += 1
            content = result if isinstance(result, str) else json.dumps(result)
            log.info("  <- tool %r response: %s", tool_name, content)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content,
                }
            )

    log.warning("Max attempts (%d) reached without a final answer", max_attempts)
    return "Sorry, I couldn't complete the task within the allowed number of attempts."


if __name__ == "__main__":
    print(f"Database file written to: {DB_PATH}\n")
    query = (
        "Find the top 2 customers by total revenue in the 'West' region, "
        "and for each, identify which employee processed their single "
        "highest-value order."
    )
    answer = run_agent(query, max_attempts=MAX_ATTEMPTS)
    print("\nFINAL ANSWER:\n" + answer)
