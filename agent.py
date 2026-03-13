from dotenv import load_dotenv

load_dotenv()

from pathlib import Path
from langchain_community.utilities import SQLDatabase
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.messages import HumanMessage

db_path = Path(__file__).parent / "Chinook.db"
db = SQLDatabase.from_uri(f"sqlite:///{db_path}")

system_prompt = """You are a customer support agent for Chinook Music Store — an online music retailer.

You help customers find tracks, albums, and artists, answer questions about pricing, and look up their purchase history. 

Use the sql_query tool to answer any question that requires data from the store's database.

Keep responses concise and friendly."""


def get_schema() -> str:
    return db.get_table_info()


@tool
def sql_query(query: str) -> str:
    """Obtain information from the inventory database using SQL queries."""
    try:
        return db.run(query)
    except Exception as e:
        return f"Error: {e}"


sql_query.description += f"\n\nThe database schema is as follows:\n{get_schema()}"


agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[sql_query],
    system_prompt=system_prompt,
)


async def chat(message: str) -> dict:
    response = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]}
    )
    output = response["messages"][-1].content
    return {"messages": response["messages"], "output": output}
