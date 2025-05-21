import logging
from opentelemetry import trace, _events
import tempfile
from dataclasses import dataclass
from typing import Any
from utils import ask_prompt, console, print_markdown, render_messages

import sqlite3
from pydantic import BaseModel, Field

from pydantic_ai.models import KnownModelName
from pydantic_ai import Agent, RunContext
from pydantic_ai.settings import ModelSettings
from pydantic_ai.messages import ModelMessage
from pydantic_ai.agent import InstrumentationSettings


SYSTEM_PROMPT = f"""\
You are a helpful AI assistant with a mastery of database design and querying. You have access
to an ephemeral sqlite3 database that you can query and modify through some tools. Help answer
questions and perform actions. Follow these rules:

- Make sure you always use sql_db_query_checker to validate SQL statements **before** running
  them. In pseudocode: `checked_query = sql_db_query_checker(query);
  sql_db_query(checked_query)`.
- Be creative and don't ask for permission! The database is ephemeral so it's OK to make some mistakes.
- The sqlite version is {sqlite3.sqlite_version} which supports multiple row inserts.
- Always prefer to insert multiple rows in a single call to the sql_db_query tool, if possible.
- You may request to execute multiple sql_db_query tool calls which will be run in parallel.

If you make a mistake, try to recover."""

INTRO_TEXT = """\
Starting agent using ephemeral SQLite DB {dbpath}. This demo allows you to chat with an Agent
that has full access to an ephemeral SQLite database. The database is initially empty. It is
built with the the LangGraph prebuilt **ReAct Agent** and the **SQLDatabaseToolkit**. Here are some samples you can try:

**Weather**
- Create a new table to hold weather data.
- Populate the weather database with 20 example rows.
- Add a new column for weather observer notes

**Pets**
- Create a database table for pets including an `owner_id` column.
- Add 20 example rows please.
- Create an owner table.
- Link the two tables together, adding new columns, values, and rows as needed.
- Write a query to join these tables and give the result of owners and their pets.
- Show me the query, then the output as a table

---
"""

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


@dataclass
class SqlAgentDeps:
    thread_id: str
    dbpath: str


sql_agent = Agent(
    deps_type=SqlAgentDeps,
    model_settings=ModelSettings(parallel_tool_calls=True),
    system_prompt=SYSTEM_PROMPT,
    # Use OTel standard semconv which works with Cloud Trace
    # https://ai.pydantic.dev/logfire/#data-format
    instrument=InstrumentationSettings(event_mode="logs"),
)


class SqlRunResult(BaseModel):
    error: str | None = Field(
        description="If the result represents an error. It will be null or undefined if no error",
        default=None,
    )
    rows: list[tuple[str, ...]] = Field(
        description="The rows returned by the SQL query", default=[]
    )


@sql_agent.tool
@tracer.start_as_current_span("run_sql")
def run_sql(ctx: RunContext[SqlAgentDeps], sql_query: str) -> SqlRunResult:
    """Runs a SQLite query. The SQL query can be DDL or DML. Returns the rows if it's a SELECT query."""
    # Load instrumentors

    with sqlite3.connect(ctx.deps.dbpath) as db:
        try:
            cursor = db.cursor()
            cursor.execute(sql_query)
            rows_list: list[tuple[str, ...]] = []

            # Check if the query is one that would return rows (e.g., SELECT)
            if cursor.description is not None:
                fetched_rows: list[tuple[Any, ...]] = cursor.fetchall()
                rows_list = [tuple(str(col) for col in row) for row in fetched_rows]
                logger.info("Query returned %s rows", len(rows_list))
            else:
                # For DDL/DML (like INSERT, UPDATE, DELETE without RETURNING clause)
                # cursor.description is None.
                # rowcount shows number of affected rows for DML.
                logger.info("Query affected %s rows (DDL/DML)", cursor.rowcount)

            # DML statements (INSERT, UPDATE, DELETE) require a commit.
            # DDL statements are often autocommitted by SQLite, but an explicit commit here ensures DML changes are saved.
            db.commit()
            return SqlRunResult(rows=rows_list)

        except sqlite3.Error as err:
            logger.error(f"SQL Error: {err} for query: {sql_query}")
            try:
                db.rollback()  # Attempt to rollback on error
                logger.info("SQL transaction rolled back due to error.")
            except sqlite3.Error as rb_err:
                # This can happen if the connection is already closed or in an unusable state.
                logger.error(f"Failed to rollback transaction: {rb_err}")
            return SqlRunResult(error=str(err))


def get_dbpath(thread_id: str) -> str:
    # Ephemeral sqlite database per conversation thread
    _, path = tempfile.mkstemp(suffix=".db")
    return path


async def run_agent(*, model: KnownModelName) -> None:
    thread_id = "default"
    dbpath = get_dbpath(thread_id)
    deps = SqlAgentDeps(thread_id="default", dbpath=dbpath)

    print_markdown(INTRO_TEXT.format(dbpath=dbpath))

    history: list[ModelMessage] = []
    while True:
        # Accept input from the user
        try:
            prompt_txt = ask_prompt()
        except (EOFError, KeyboardInterrupt):
            print_markdown("Exiting...")
            break

        if not prompt_txt:
            continue

        with console.status("Agent is thinking"):
            result = await sql_agent.run(
                prompt_txt,
                model=model,
                deps=deps,
                message_history=history,
            )

        history = result.all_messages()

        # Print history
        render_messages(result.new_messages())
