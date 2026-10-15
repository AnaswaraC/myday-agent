from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException , Query
import httpx
from .config import settings
from .tools.weather_api import (
    get_weather,
    get_weather_by_coords,
    CityNotFound,
    WeatherUnavailable,
    build_spoken_summary,
    )

app = FastAPI(title="myday-agent")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "city": settings.default_city}


@app.get("/weather")
def weather(city: str | None = None, country: str | None = None):
    """Example: /weather?city=Palakkad  or  /weather?city=mumbai&country=India"""
    try:
        data = get_weather(city or settings.default_city, country)
    except CityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (WeatherUnavailable, httpx.HTTPError):
        raise HTTPException(status_code=503, detail=BUSY)
    return {"data": data, "spoken": build_spoken_summary(data)}


@app.get("/weather/here")
def weather_here(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    place: str = "your location",
):
    """Example: /weather/here?lat=10.78&lon=76.65&place=Palakkad"""
    try:
        data = get_weather_by_coords(lat, lon, place)
    except (WeatherUnavailable, httpx.HTTPError):
        raise HTTPException(status_code=503, detail=BUSY)
    return {"data": data, "spoken": build_spoken_summary(data)}
