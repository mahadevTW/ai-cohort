import os
import json
import requests
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_KEY")

if not OPENAI_KEY:
    raise ValueError("OPENAI_KEY is not set in the .env file")

client = OpenAI(api_key=OPENAI_KEY)

MODEL = "gpt-4o-mini"


# ============================================================
# 1. GET TODAY'S DATE
# ============================================================

def get_todays_date():
    """
    Returns today's current date and time.
    """

    now = datetime.now()

    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S")
    }


# ============================================================
# 2. GET COORDINATES
# ============================================================

def get_coordinates(city):
    """
    Converts a city name into latitude and longitude
    using the Open-Meteo Geocoding API.
    """

    geocoding_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )

    geocoding_params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    response = requests.get(
        geocoding_url,
        params=geocoding_params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if "results" not in data or not data["results"]:
        return {
            "error": f"Could not find city: {city}"
        }

    location = data["results"][0]

    return {
        "city": location.get("name"),
        "state": location.get("admin1"),
        "country": location.get("country"),
        "country_code": location.get("country_code"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "timezone": location.get("timezone")
    }


# ============================================================
# 3. GET WEATHER USING COORDINATES
# ============================================================

def get_weather(latitude, longitude):
    """
    Gets current weather and a 3-day forecast
    using latitude and longitude.
    """

    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_params = {
        "latitude": latitude,
        "longitude": longitude,

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "weather_code,"
            "wind_speed_10m"
        ),

        "daily": (
            "weather_code,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum,"
            "rain_sum"
        ),

        "forecast_days": 3,

        "timezone": "auto"
    }

    response = requests.get(
        weather_url,
        params=weather_params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    return {
        "current_weather": data.get("current"),
        "daily_forecast": data.get("daily")
    }


# ============================================================
# 4. GET AIR QUALITY USING COORDINATES
# ============================================================

def get_air_quality(latitude, longitude):
    """
    Gets current air quality using latitude and longitude.

    Returns:
    - US AQI
    - European AQI
    - PM2.5
    - PM10
    """

    air_quality_url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
    )

    air_quality_params = {
        "latitude": latitude,
        "longitude": longitude,

        "current": (
            "us_aqi,"
            "european_aqi,"
            "pm2_5,"
            "pm10"
        ),

        "timezone": "auto"
    }

    response = requests.get(
        air_quality_url,
        params=air_quality_params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    return {
        "current_air_quality": data.get("current")
    }


# ============================================================
# 5. GET SUNRISE / SUNSET USING COORDINATES
# ============================================================

def get_sunrise_sunset(latitude, longitude):
    """
    Gets today's sunrise and sunset times
    using latitude and longitude.
    """

    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_params = {
        "latitude": latitude,
        "longitude": longitude,

        "daily": "sunrise,sunset",

        "forecast_days": 1,

        "timezone": "auto"
    }

    response = requests.get(
        weather_url,
        params=weather_params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    daily = data.get("daily", {})

    dates = daily.get("time", [])
    sunrise = daily.get("sunrise", [])
    sunset = daily.get("sunset", [])

    return {
        "date": dates[0] if dates else None,
        "sunrise": sunrise[0] if sunrise else None,
        "sunset": sunset[0] if sunset else None
    }


# ============================================================
# 6. OPENAI TOOL DEFINITIONS
# ============================================================

tools = [

    # --------------------------------------------------------
    # DATE TOOL
    # --------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": "get_todays_date",

            "description": (
                "Gets today's current date and time."
            ),

            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },


    # --------------------------------------------------------
    # COORDINATES TOOL
    # --------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": "get_coordinates",

            "description": (
                "Converts a city name into latitude and "
                "longitude. Use this before calling weather, "
                "air quality, or sunrise/sunset tools when "
                "only a city name is available."
            ),

            "parameters": {
                "type": "object",

                "properties": {

                    "city": {
                        "type": "string",

                        "description": (
                            "Name of the city."
                        )
                    }
                },

                "required": ["city"]
            }
        }
    },


    # --------------------------------------------------------
    # WEATHER TOOL
    # --------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": "get_weather",

            "description": (
                "Gets current weather and a 3-day forecast "
                "using latitude and longitude."
            ),

            "parameters": {
                "type": "object",

                "properties": {

                    "latitude": {
                        "type": "number",

                        "description": (
                            "Latitude of the location."
                        )
                    },

                    "longitude": {
                        "type": "number",

                        "description": (
                            "Longitude of the location."
                        )
                    }
                },

                "required": [
                    "latitude",
                    "longitude"
                ]
            }
        }
    },


    # --------------------------------------------------------
    # AIR QUALITY TOOL
    # --------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": "get_air_quality",

            "description": (
                "Gets current air quality information "
                "using latitude and longitude. Returns "
                "US AQI, European AQI, PM2.5 and PM10."
            ),

            "parameters": {
                "type": "object",

                "properties": {

                    "latitude": {
                        "type": "number",

                        "description": (
                            "Latitude of the location."
                        )
                    },

                    "longitude": {
                        "type": "number",

                        "description": (
                            "Longitude of the location."
                        )
                    }
                },

                "required": [
                    "latitude",
                    "longitude"
                ]
            }
        }
    },


    # --------------------------------------------------------
    # SUNRISE / SUNSET TOOL
    # --------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": "get_sunrise_sunset",

            "description": (
                "Gets today's sunrise and sunset times "
                "using latitude and longitude."
            ),

            "parameters": {
                "type": "object",

                "properties": {

                    "latitude": {
                        "type": "number",

                        "description": (
                            "Latitude of the location."
                        )
                    },

                    "longitude": {
                        "type": "number",

                        "description": (
                            "Longitude of the location."
                        )
                    }
                },

                "required": [
                    "latitude",
                    "longitude"
                ]
            }
        }
    }
]


# ============================================================
# 7. TOOL EXECUTION FUNCTION
# ============================================================

def execute_tool(tool_name, arguments):
    """
    Executes the requested tool.
    """

    if tool_name == "get_todays_date":

        return get_todays_date()


    elif tool_name == "get_coordinates":

        return get_coordinates(
            **arguments
        )


    elif tool_name == "get_weather":

        return get_weather(
            **arguments
        )


    elif tool_name == "get_air_quality":

        return get_air_quality(
            **arguments
        )


    elif tool_name == "get_sunrise_sunset":

        return get_sunrise_sunset(
            **arguments
        )


    else:

        return {
            "error": f"Unknown tool: {tool_name}"
        }


# ============================================================
# 8. CONVERSATION HISTORY
# ============================================================

messages = [

    {
        "role": "system",

        "content": (
            "You are a helpful AI assistant.\n\n"

            "For current date information, use "
            "get_todays_date.\n\n"

            "For weather, air quality, sunrise, or sunset "
            "information:\n"
            "1. If only a city name is available, first call "
            "get_coordinates.\n"
            "2. Use the latitude and longitude returned by "
            "get_coordinates for the other required tools.\n"
            "3. After receiving a tool result, decide whether "
            "another tool is required.\n"
            "4. Continue calling tools until you have enough "
            "information to answer the user's question.\n\n"

            "For a request such as a complete weather summary, "
            "you should normally obtain weather, air quality, "
            "sunrise and sunset information before producing "
            "the final answer.\n\n"

            "Do not guess current weather or air quality data."
        )
    }
]


# ============================================================
# 9. CHAT LOOP WITH TOOL CHAINING
# ============================================================

while True:

    user_question = input("\nYou: ")

    # --------------------------------------------------------
    # Exit
    # --------------------------------------------------------

    if user_question.lower().strip() in [
        "exit",
        "quit",
        "bye"
    ]:

        print("Assistant: Goodbye!")

        break


    # --------------------------------------------------------
    # Add user message
    # --------------------------------------------------------

    messages.append(
        {
            "role": "user",
            "content": user_question
        }
    )


    # ========================================================
    # TOOL-CHAIN LOOP
    # ========================================================

    while True:

        response = client.chat.completions.create(

            model=MODEL,

            messages=messages,

            tools=tools,

            tool_choice="auto"
        )

        assistant_message = response.choices[0].message


        # ----------------------------------------------------
        # CASE 1:
        # LLM wants to call one or more tools
        # ----------------------------------------------------

        if assistant_message.tool_calls:

            # Store the assistant's tool-call message
            messages.append(assistant_message)


            # ------------------------------------------------
            # Execute each tool requested by the LLM
            # ------------------------------------------------

            for tool_call in assistant_message.tool_calls:

                tool_name = tool_call.function.name

                tool_call_id = tool_call.id

                arguments = json.loads(
                    tool_call.function.arguments
                )


                # --------------------------------------------
                # Show tool call in terminal
                # --------------------------------------------

                print(
                    f"\n[Tool Call] {tool_name}"
                )

                print(
                    f"[Arguments] {arguments}"
                )


                # --------------------------------------------
                # Execute tool
                # --------------------------------------------

                try:

                    result = execute_tool(
                        tool_name,
                        arguments
                    )

                except Exception as e:

                    result = {
                        "error": str(e)
                    }


                # --------------------------------------------
                # Show result
                # --------------------------------------------

                print(
                    f"[Tool Result] {result}"
                )


                # --------------------------------------------
                # Send result back to LLM
                # --------------------------------------------

                messages.append(
                    {
                        "role": "tool",

                        "tool_call_id": tool_call_id,

                        "content": json.dumps(result)
                    }
                )


            # ------------------------------------------------
            # IMPORTANT:
            #
            # DO NOT break here.
            #
            # Call the LLM again so it can decide whether
            # another tool is required.
            # ------------------------------------------------

            continue


        # ----------------------------------------------------
        # CASE 2:
        # LLM has final answer
        # ----------------------------------------------------

        else:

            messages.append(
                assistant_message
            )

            print(
                f"\nAssistant: {assistant_message.content}"
            )

            break

