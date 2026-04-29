import os
import asyncio
import json
import re
from dotenv import load_dotenv
from groq import Groq

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
from embeddings import search_destinations

# -----------------------------
# ENV + LLM
# -----------------------------
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# -----------------------------
# MEMORY
# -----------------------------
SESSION_MEMORY = {}

# -----------------------------
# MCP CONFIG
# -----------------------------
AIRBNB_CONFIG = StdioServerParameters(
    command="npx",
    args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
)

WEATHER_CONFIG = StdioServerParameters(
    command="npx",
    args=["-y", "@dangahagan/weather-mcp@latest"]
)

# -----------------------------
# KEYWORDS
# -----------------------------
WEATHER_KEYWORDS = ["weather", "temperature", "climate", "rain", "forecast", "humid", "hot", "cold", "sunny", "cloudy"]
HOTEL_KEYWORDS   = ["hotel", "hotels", "stay", "airbnb", "accommodation", "hostel", "resort", "booking", "room"]

# Words to strip when extracting place name
FILLER_WORDS = (
    r"\b(weather|temperature|climate|rain|forecast|humid|sunny|cloudy|hot|cold|"
    r"hotel|hotels|stay|airbnb|accommodation|hostel|resort|booking|room|"
    r"in|at|of|for|near|around|show|me|find|get|tell|give|"
    r"what|whats|what's|is|the|a|an|"
    r"india|please|right\s*now|today|tonight|currently|check)\b"
)

# -----------------------------
# PLACE EXTRACTOR
# -----------------------------
def extract_place(text: str) -> str:
    """Strip all filler/intent words and return the bare place name."""
    result = re.sub(FILLER_WORDS, " ", text, flags=re.I)
    result = re.sub(r"[^\w\s]", " ", result)       # remove punctuation
    result = re.sub(r"\s+", " ", result).strip()    # collapse spaces
    return result.title() if result else ""

# -----------------------------
# INTENT DETECTOR
# -----------------------------
def detect_intent(query: str):
    """
    Returns: ("weather", place) | ("hotel", place) | ("general", "")
    """
    ql = query.lower().strip()

    has_hotel   = any(kw in ql for kw in HOTEL_KEYWORDS)
    has_weather = any(kw in ql for kw in WEATHER_KEYWORDS)

    # Hotel takes priority
    if has_hotel:
        place = extract_place(query)
        return "hotel", place

    if has_weather:
        place = extract_place(query)
        return "weather", place

    # Plain city name fallback (e.g. just "Delhi" or "New York")
    words = query.strip().split()
    no_question = not any(w in ql for w in ["?", "how", "why", "what", "tell", "give", "recommend"])
    if 1 <= len(words) <= 4 and no_question:
        return "weather", query.strip().title()

    return "general", ""

# -----------------------------
# MCP SAFE CALL — 30s timeout for weather (needs 2 round trips)
# -----------------------------
async def safe_call(func, *args, timeout=30):
    try:
        return await asyncio.wait_for(func(*args), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"⏰ Timeout in {func.__name__}")
        return None
    except Exception as e:
        print(f"❌ Error in {func.__name__}: {e}")
        return None

# -----------------------------
# AIRBNB TOOL
# -----------------------------
async def tool_airbnb(place, budget):
    try:
        async with stdio_client(AIRBNB_CONFIG) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                raw = await session.call_tool(
                    "airbnb_search",
                    {"location": f"{place}, India", "adults": 2}
                )

        if not raw or not raw.content:
            return []

        data = json.loads(raw.content[0].text)

        stays = []
        for item in data.get("searchResults", [])[:8]:
            try:
                price_text = item["structuredDisplayPrice"]["primaryLine"]["accessibilityLabel"]
                match = re.search(r"₹([\d,]+).*for (\d+) nights", price_text)
                per_night = None
                if match:
                    total = int(match.group(1).replace(",", ""))
                    nights = int(match.group(2))
                    per_night = int(total / nights)

                stays.append({
                    "name": item["demandStayListing"]["description"]["name"]["localizedStringWithTranslationPreference"],
                    "price": price_text,
                    "per_night": per_night,
                    "link": item.get("url", "")
                })
            except:
                continue

        if budget:
            filtered = []
            for s in stays:
                if s["per_night"] is None:
                    continue
                val = s["per_night"]
                if budget == "low"    and val <= 3000:              filtered.append(s)
                elif budget == "medium" and 3000 < val <= 5000:     filtered.append(s)
                elif budget == "high"   and 5000 < val <= 10000:    filtered.append(s)

            return filtered[:3] if len(filtered) >= 3 else stays[:3]

        return stays[:3]

    except Exception as e:
        print(f"❌ Airbnb error: {e}")
        return []

# -----------------------------
# WEATHER TOOL — single MCP session for both calls
# -----------------------------
async def tool_weather(place):
    try:
        print(f"🌍 Fetching weather for: {place}")

        async with stdio_client(WEATHER_CONFIG) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # STEP 1: search location
                loc_raw = await session.call_tool(
                    "search_location",
                    {"query": place, "limit": 1}
                )

                if not loc_raw or not loc_raw.content:
                    print("❌ No location result")
                    return {}

                text_loc = loc_raw.content[0].text
                print(f"📍 Location raw: {text_loc[:200]}")

                lat_match = re.search(r"Latitude[:\s]+([\d.-]+)", text_loc)
                lon_match = re.search(r"Longitude[:\s]+([\d.-]+)", text_loc)

                if not lat_match or not lon_match:
                    print("❌ Could not parse lat/lon")
                    return {}

                lat = float(lat_match.group(1))
                lon = float(lon_match.group(1))
                print(f"📍 Coords: {lat}, {lon}")

                # STEP 2: forecast
                forecast_raw = await session.call_tool(
                    "get_forecast",
                    {"latitude": lat, "longitude": lon, "days": 1}
                )

                if not forecast_raw or not forecast_raw.content:
                    print("❌ No forecast result")
                    return {}

                text = forecast_raw.content[0].text
                print(f"🌤️ Forecast raw: {text[:300]}")

                def extract(pattern):
                    m = re.search(pattern, text, re.I)
                    return m.group(1).strip() if m else None

                # Try °F first, fallback to °C directly
                high_f = extract(r"High[:\s]+(\d+)[°\s]*F")
                low_f  = extract(r"Low[:\s]+(\d+)[°\s]*F")
                high_c = extract(r"High[:\s]+(\d+)[°\s]*C")
                low_c  = extract(r"Low[:\s]+(\d+)[°\s]*C")
                cond   = extract(r"Conditions?[:\s]+(.*)")
                rain   = extract(r"Precipitation Chance[:\s]+(\d+)%")

                if high_f and low_f:
                    temp = f"{round((int(high_f)-32)*5/9)}°C / {round((int(low_f)-32)*5/9)}°C"
                elif high_c and low_c:
                    temp = f"{high_c}°C / {low_c}°C"
                else:
                    # Try to extract any temperature number as fallback
                    any_temp = extract(r"(\d+)[°\s]*[FC]")
                    temp = f"{any_temp}°" if any_temp else "N/A"

                return {
                    "temp": temp,
                    "condition": cond or "Clear",
                    "rain": rain or "0"
                }

    except Exception as e:
        print(f"❌ Weather error: {e}")
        return {}

# -----------------------------
# MAIN AGENT
# -----------------------------
async def travel_agent(query, session_id="default"):

    # Budget follow-up check
    if session_id in SESSION_MEMORY:
        last = SESSION_MEMORY[session_id]
        if last.get("awaiting_budget"):
            place = last["place"]
            SESSION_MEMORY.pop(session_id)
            stays = await safe_call(tool_airbnb, place, query.lower(), timeout=30)
            return [{
                "Destination": place,
                "Stays": stays or []
            }], f"💰 Showing {query} budget stays in {place}"

    intent, place = detect_intent(query)
    print(f"🧠 Intent: {intent} | Place: '{place}'")

    # ---- WEATHER ----
    if intent == "weather":
        if not place:
            return [], "Please mention a city name for the weather."

        weather = await safe_call(tool_weather, place, timeout=60)

        if weather and weather.get("temp"):
            return [], (
                f"🌦️ **{place} Weather**\n"
                f"🌡️ {weather['temp']}\n"
                f"☁️  {weather['condition']}\n"
                f"🌧️ Rain: {weather['rain']}%"
            )
        return [], f"⚠️ Weather data not available for **{place}** right now. Please try again."

    # ---- HOTEL ----
    if intent == "hotel":
        if not place:
            return [], "Please mention a city name to search stays."

        stays = await safe_call(tool_airbnb, place, None, timeout=30)

        SESSION_MEMORY[session_id] = {
            "awaiting_budget": True,
            "place": place
        }

        return [{
            "Destination": place,
            "Stays": stays or []
        }], "💰 Do you have a budget? (low / medium / high)"

    # ---- DEFAULT: embeddings search ----
    destinations = search_destinations(query)
    if destinations.empty:
        return [], "No destinations found."

    return destinations.to_dict("records"), "Here are some recommendations."

# -----------------------------
# RUNNER
# -----------------------------
async def run_agent(query, session_id="default"):
    return await travel_agent(query, session_id)