from datetime import date

from fastmcp import FastMCP

mcp = FastMCP("demo_server")


@mcp.tool()
def greet() -> str:
    """Return a friendly hello message."""
    return "Hello!"


@mcp.tool()
def get_todays_date() -> str:
    """Return today's date in YYYY-MM-DD format."""
    return date.today().isoformat()


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=9001)
