from fastmcp import FastMCP

mcp = FastMCP("Demo")

@mcp.tool
def add (a: float, b: float):
    """Add two numbers."""
    print(f"Adding {a} and {b}")
    return a + b

@mcp.tool
def subtract (a: float, b: float):
    """Subtract two numbers."""
    return a - b

@mcp.tool
def multiply (a: float, b: float):
    """Multiply two numbers."""
    return a * b

@mcp.tool
def divide (a: float, b: float):
    """Divide two numbers."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b

@mcp.tool
def get_weather (city: str):
    """Get the current weather for a city."""
    # This is a placeholder implementation. In a real application, you would call a weather API.
    return f"The current weather in {city} is sunny with a temperature of 25°C."

@mcp.tool
def get_todays_date ():
    """Get today's date."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

if __name__ == "__main__":
    mcp.run(transport="http", host="localhost", port=8001)