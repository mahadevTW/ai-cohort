import os
from datetime import datetime
import requests

def get_todays_date():
    now = datetime.now()
    res=now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"************ From Function get_todays_date: {res} \n")
    return res

def get_lat_long(city_name: str):

    print(f"************ Pulling latitude and logitude for city: {city_name} \n")
    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    response = requests.get(url, params=params, timeout=float(os.getenv("WEATHER_HTTP_TIMEOUT", "10")))

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
        timeout=float(os.getenv("WEATHER_HTTP_TIMEOUT", "10"))
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
