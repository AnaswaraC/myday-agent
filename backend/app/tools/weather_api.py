import httpx

try:
    import pycountry
except ImportError:  # the code still works without it, using the name-matching fallback
    pycountry = None

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes used by Open-Meteo, simplified
WEATHER_CODES = {
    0: "clear sky",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "thunderstorms with hail",
}

# Informal names people say, mapped to ISO country codes
COUNTRY_ALIASES = {
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "great britain": "GB",
    "england": "GB",
    "usa": "US",
    "u.s.a.": "US",
    "u.s.": "US",
    "america": "US",
    "united states of america": "US",
    "uae": "AE",
    "emirates": "AE",
    "korea": "KR",
    "south korea": "KR",
    "holland": "NL",
    "burma": "MM",
    "ivory coast": "CI",
}


class CityNotFound(ValueError):
    """The city (or country/state hint) could not be matched."""


class WeatherUnavailable(Exception):
    """The weather service answered, but without usable data."""


def _clean(text: str | None) -> str:
    """Trim and collapse extra spaces."""
    return " ".join((text or "").split())


def _country_code(country: str) -> str | None:
    """Turn any country name or code into a 2-letter code, or None if unknown."""
    if not country:
        return None
    key = country.lower()
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    if pycountry is not None:
        try:
            # Accepts names (India), codes (IN, IND) and official names
            return pycountry.countries.lookup(country).alpha_2
        except LookupError:
            return None
    # Without pycountry, only a 2-letter code can be trusted
    if len(country) == 2:
        return country.upper()
    return None


def _fetch_forecast(client: httpx.Client, lat: float, lon: float) -> dict:
    """Call the forecast API for one point. timezone=auto uses the place's local time."""
    response = client.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 1,
        },
    )
    response.raise_for_status()
    return response.json()


def _format(place: str, country: str, forecast: dict) -> dict:
    """Keep only the fields we need, in a clean dictionary."""
    try:
        current = forecast["current"]
        daily = forecast["daily"]
        return {
            "city": place,
            "country": country,
            "condition": WEATHER_CODES.get(current["weather_code"], "mixed conditions"),
            "temp_now": round(current["temperature_2m"]),
            "feels_like": round(current["apparent_temperature"]),
            "temp_max": round(daily["temperature_2m_max"][0]),
            "temp_min": round(daily["temperature_2m_min"][0]),
            "rain_chance": daily["precipitation_probability_max"][0] or 0,
            "observed_at": current["time"],  # local time of that place
        }
    except (KeyError, IndexError, TypeError):
        raise WeatherUnavailable("Weather data is unavailable right now.")


def get_weather(city: str, country: str | None = None) -> dict:
    """
    Live weather for a city name, in any letter case.
    country can be a code (IN) or a name (India, UK, USA).
    city may include a hint after a comma, e.g. "Palakkad, Kerala".
    """
    city = _clean(city)
    if not city:
        raise CityNotFound("Please give me a city name.")

    hint = ""
    if "," in city:
        city, hint = [part.strip() for part in city.split(",", 1)]
        if not city:
            raise CityNotFound("Please give me a city name.")

    country = _clean(country)
    code = _country_code(country)
    # If we could not turn the country into a code, match its name in the results
    wanted_country_name = country.lower() if country and not code else ""

    params = {"name": city, "count": 10, "language": "en"}
    if code:
        params["countryCode"] = code

    with httpx.Client(timeout=15) as client:
        geo = client.get(GEOCODE_URL, params=params)
        geo.raise_for_status()
        results = geo.json().get("results") or []

        def matches(r: dict) -> bool:
            if wanted_country_name and r.get("country", "").lower() != wanted_country_name:
                return False
            if hint:
                h = hint.lower()
                fields = [
                    r.get("admin1", ""),
                    r.get("admin2", ""),
                    r.get("country", ""),
                    r.get("country_code", ""),
                ]
                if not any(h == f.lower() for f in fields if f):
                    return False
            return True

        matched = [r for r in results if matches(r)]
        if not matched:
            extra = f" ({hint or country})" if (hint or country) else ""
            raise CityNotFound(f"City not found: {city}{extra}")
        place = matched[0]

        forecast = _fetch_forecast(client, place["latitude"], place["longitude"])

    return _format(place["name"], place.get("country", ""), forecast)


def get_weather_by_coords(lat: float, lon: float, label: str = "your location") -> dict:
    """Live weather for exact coordinates, such as from the phone's GPS."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise CityNotFound("Those coordinates are not valid.")
    with httpx.Client(timeout=15) as client:
        forecast = _fetch_forecast(client, lat, lon)
    return _format(_clean(label) or "your location", "", forecast)


def _greeting(observed_at: str) -> str:
    """Pick a greeting from the local hour in 'YYYY-MM-DDTHH:MM'."""
    try:
        hour = int(observed_at[11:13])
    except (ValueError, IndexError, TypeError):
        return "Hello"
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def build_spoken_summary(w: dict) -> str:
    """Turn the weather data into a sentence that sounds natural when spoken."""
    where = f"In {w['city']}" if w["city"] != "your location" else "Where you are"
    text = (
        f"{_greeting(w['observed_at'])}. {where} it is {w['condition']} right now, "
        f"{w['temp_now']} degrees, feeling like {w['feels_like']}. "
        f"Today's high is {w['temp_max']} and the low is {w['temp_min']}. "
        f"The chance of rain is {w['rain_chance']} percent."
    )
    if w["rain_chance"] >= 50:
        text += " Better carry an umbrella."
    elif w["temp_max"] >= 35:
        text += " It will be hot, so drink plenty of water."
    return text