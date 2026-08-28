from dotenv import load_dotenv
from openai import OpenAI
import os
import json
from datetime import datetime
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

def get_todays_date():
    now = datetime.now()
    res=now.strftime("%Y-%m-%d %H:%M:%S")
    print("************ "+res)
    return res


def get_todays_wether():
    # use wether api from IMDB and pull the information
    # return result
    return {
  "location": {
    "city": "Sangli",
    "district": "Sangli",
    "state": "Maharashtra",
    "latitude": 16.8524,
    "longitude": 74.5815
  },
  "current": {
    "temperature": 28.5,
    "feels_like": 30.2,
    "humidity": 78,
    "pressure": 1008,
    "wind_speed": 12,
    "wind_direction": "SW",
    "visibility": 6,
    "weather": "Partly Cloudy",
    "weather_code": "02"
  },
  "forecast": [
    {
      "date": "2026-08-23",
      "min_temperature": 24,
      "max_temperature": 30,
      "rain_probability": 70,
      "rainfall_mm": 12.5,
      "weather": "Light Rain"
    },
    {
      "date": "2026-08-24",
      "min_temperature": 24,
      "max_temperature": 31,
      "rain_probability": 60,
      "rainfall_mm": 8.2,
      "weather": "Partly Cloudy"
    }
  ],
  "alerts": [
    {
      "type": "Heavy Rain",
      "severity": "Moderate",
      "description": "Heavy rainfall is likely in isolated areas.",
      "valid_from": "2026-08-23T12:00:00+05:30",
      "valid_until": "2026-08-24T12:00:00+05:30"
    }
  ]
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_date_time",
            "description": "gets the current date and time of the system",
            "parameters": {}
        }
    },
    {
            "type": "function",
            "function": {
                "name": "get_wether",
                "description": "gets the current wether including temrature and rain forecast",
                "parameters": {}
            }
        }
]

messages = [
    {
        "role":"user",
        "content":"will it rain tomorrow"
    }
]

response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            # passing body part along query to brain saying that you can use body parts based on need
            tools=tools
        )
print(response.choices[0])
# detect if tool call is being suggested by llm
tools = response.choices[0].message.tool_calls
if len(tools) > 0:
    # execute the tool call
    tool_name = tools[0].function.name
    tool_call_id = tools[0].function.name
    messages.append({
    "role":"assistant",
    "tool_calls":[
            {
                "id":tool_call_id,
                "type":"function",
                "function":{
                    "name":tool_name,
                    "arguments":""
                }
            }
        ]
    })
    print(f"tool call is recommened by llm  {tool_name}")
    tool_result =""
    message_with_tool = {}
    if tool_name=="get_date_time":
        tool_result = get_todays_date()
    message_with_tool = {
        "role":"tool",
        "tool_call_id":tool_call_id,
        "content":tool_result
    }
    if tool_name=="get_wether":
        tool_result = get_todays_wether()
        message_with_tool = {
        "role":"tool",
        "tool_call_id":tool_call_id,
        "content":json.dumps(tool_result)
        }
    messages.append(message_with_tool)
    response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            # passing body part along query to brain saying that you can use body parts based on need
            tools=tools
        )
    print(response.choices[0].message.content)
    
else:
    print(response.choices[0].message.content)