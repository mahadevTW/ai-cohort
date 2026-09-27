from fastmcp import FastMCP
import uvicorn

mcp = FastMCP()

@mcp.tool
def greet(name: str):
    """Greet a person by name."""
    return f"Hello, {name}!"

@mcp.tool
def getTodaysDate():
    """Get today's date."""
    from datetime import date
    return date.today().isoformat()

    
if __name__ == "__main__":
    
    mcp.run(transport="http", host="0.0.0.0", port=8001)
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)