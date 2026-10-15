import httpx
from mcp.server.fastmcp import FastMCP

from app.tools.weather_api import (
    CityNotFound,
    WeatherUnavailable,
    build_spoken_summary,
    get_weather,
    get_weather_by_coords,
)

mcp = FastMCP("weather")

BUSY = "Weather service unavailable, please try again."


@mcp.tool()
def weather_by_city(city: str, country: str | None = None) -> dict:
    """Get today's live weather for a city. City may include a state, e.g. 'Palakkad, Kerala'.
    Optional country as a code (IN) or name (India)."""
    try:
        data = get_weather(city, country)
    except CityNotFound as e:
        return {"error": str(e)}
    except (WeatherUnavailable, httpx.HTTPError):
        return {"error": BUSY}
    return {"data": data, "spoken": build_spoken_summary(data)}


@mcp.tool()
def weather_by_coordinates(lat: float, lon: float, place: str = "your location") -> dict:
    """Get today's live weather for GPS coordinates, such as from the user's phone."""
    try:
        data = get_weather_by_coords(lat, lon, place)
    except CityNotFound as e:
        return {"error": str(e)}
    except (WeatherUnavailable, httpx.HTTPError):
        return {"error": BUSY}
    return {"data": data, "spoken": build_spoken_summary(data)}


if __name__ == "__main__":
    mcp.run()  # stdio transport; never use print() here, stdout is the protocol channel