from dotenv import load_dotenv
from openai import OpenAI
import os
import json
from datetime import datetime
import time

import requests
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

def get_todays_date():
    now = datetime.now()
    res=now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"************ From Function get_todays_date: {res} \n")
    return res

def get_lat_long(city_name: str):

    print(f"************ Pulling latitude and logitude for city: {city_name} \n")
    time.sleep(5)  # Simulate a delay for the API call
    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    response = requests.get(url, params=params)

    response.raise_for_status()

    data = response.json()

    if "results" not in data or not data["results"]:
        return None

    location = data["results"][0]

    print(f"************ From Function get_lat_long: {location.get('country')} \n")

    return {
        "city": location["name"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "country": location.get("country")
    }


def get_wether_by_lat_long(latitude: str, longitude: str):
    # use weather api from Open-Meteo and pull the information
    # return result
    # The city is supplied by the model from the user's message.

    print(f"************ Pulling weather data for: {latitude}, {longitude} \n")
    time.sleep(5)  # Simulate a delay for the API call
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
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
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum,"
            "precipitation_probability_max"
        ),
        "timezone": "auto"
    }

    response_wth = requests.get(
        url,
        params=params,
        timeout=10
    )

    response_wth.raise_for_status()
    print(f"************ From Function get_wether_by_lat_long: {response_wth.json()}\n")
    return response_wth.json()

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_date_time",
            "description": "gets the current date and time of the system",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
            "type": "function",
            "function": {
            "name": "get_lat_long_for_city",
                "description": "Gets the latitude and longitude for a specified city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city requested by the user, for example Delhi or Pune."
                        }
                    },
                    "required": ["city"],
                    "additionalProperties": False
                }
            }
        }
        ,
        {
            "type": "function",
            "function": {
            "name": "get_wether_by_lat_long",
                "description": "Gets the current weather and rain forecast for a specified location using latitude and longitude.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "string",
                            "description": "The latitude of the location for which to get weather information."
                        },
                        "longitude": {
                            "type": "string",
                            "description": "The longitude of the location for which to get weather information."
                        }
                    },
                    "required": ["latitude", "longitude"],
                    "additionalProperties": False
                }
            }
        }
]

def ask_llm(question: str):
    messages = [
        {
            "role": "user",
            "content": question
        }
    ]


    while True:
    
        print(f"Before 1st call LLM: {messages}\n")
        response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    # passing body part along query to brain saying that you can use body parts based on need
                    tools=tools
                )
        print(f"1st Response from LLM: {response.choices[0]}\n")
        # detect if tool call is being suggested by llm
        tool_calls = response.choices[0].message.tool_calls or []
        if tool_calls:
            # execute the tool call
            tool_call = tool_calls[0]
            tool_name = tool_call.function.name
            tool_call_id = tool_call.id
            tool_args = json.loads(tool_call.function.arguments or "{}")
            messages.append({
            "role":"assistant",
            "tool_calls":[
                    {
                        "id":tool_call_id,
                        "type":"function",
                        "function":{
                            "name":tool_name,
                            "arguments": tool_call.function.arguments
                        }
                    }
                ]
            })
            print(f"tool call is recommened by llm  {tool_name}\n")
            if tool_name=="get_date_time":
                tool_result = get_todays_date()
                tool_content = tool_result
            elif tool_name=="get_lat_long_for_city":
                city = tool_args["city"]
                tool_result = get_lat_long(city)
                tool_content = json.dumps(tool_result)
            elif tool_name=="get_wether_by_lat_long":
                latitude = tool_args["latitude"]
                longitude = tool_args["longitude"]
                tool_result = get_wether_by_lat_long(latitude, longitude)
                tool_content = json.dumps(tool_result)
            else:
                tool_content = json.dumps({"error": f"Unknown tool: {tool_name}"})

            message_with_tool = {
                "role":"tool",
                "tool_call_id":tool_call_id,
                "content":tool_content
            }
            messages.append(message_with_tool)
            response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    # passing body part along query to brain saying that you can use body parts based on need
                    tools=tools
                )
            print(f"Final Response from LLM: {response.choices[0].message.content}")
            
        else:
            print(f"Final Response from LLM ELSE: {response.choices[0].message.content}")
            break


ask_llm("Will it rain in Pune tomorrow?")