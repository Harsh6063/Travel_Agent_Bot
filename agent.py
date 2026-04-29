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
# MEMORY (FOR BUDGET FLOW)
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
# MCP CALL
# -----------------------------
async def call_mcp(config, tool, params):
    try:
        async with stdio_client(config) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, params)
    except Exception as e:
        print(f"MCP error ({tool}):", e)
        return None

async def safe_call(func, *args):
    try:
        return await asyncio.wait_for(func(*args), timeout=8)
    except Exception as e:
        print(f"{func.__name__} error:", e)
        return None

# -----------------------------
# LLM
# -----------------------------
def generate_explanation(query, results):
    try:
        prompt = f"Query: {query}\nResults: {results}\nExplain briefly."
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except:
        return "These destinations match your travel interest."

# -----------------------------
# AIRBNB TOOL (UNCHANGED + PER NIGHT)
# -----------------------------
async def tool_airbnb(place, budget):
    try:
        raw = await call_mcp(
            AIRBNB_CONFIG,
            "airbnb_search",
            {"location": f"{place}, India", "adults": 2}
        )

        if not raw or not raw.content:
            return []

        data = json.loads(raw.content[0].text)

        stays = []
        for item in data.get("searchResults", [])[:5]:
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
                    "per_night": f"₹{per_night}/night" if per_night else "",
                    "link": item.get("url", "")
                })
            except:
                continue

        # -----------------------------
        # UPDATED BUDGET FILTER
        # -----------------------------
        if budget:
            filtered = []
            for s in stays:
                if not s["per_night"]:
                    continue

                val = int(s["per_night"].replace("₹", "").replace("/night", ""))

                if budget == "low" and val <= 3000:
                    filtered.append(s)
                elif budget == "medium" and 3000 < val <= 5000:
                    filtered.append(s)
                elif budget == "high" and 5000 < val <= 10000:
                    filtered.append(s)

            return filtered if filtered else stays

        return stays

    except Exception as e:
        print("Airbnb error:", e)
        return []

# -----------------------------
# WEATHER TOOL (FIXED 🔥)
# -----------------------------
async def tool_weather(place):
    try:
        # STEP 1: GET LOCATION
        loc_raw = await call_mcp(
            WEATHER_CONFIG,
            "search_location",
            {"query": place, "limit": 1}
        )

        lat, lon = None, None

        if loc_raw and loc_raw.content:
            try:
                loc_data = json.loads(loc_raw.content[0].text)
                if isinstance(loc_data, list) and len(loc_data) > 0:
                    lat = loc_data[0].get("latitude")
                    lon = loc_data[0].get("longitude")
            except:
                pass

        # fallback if MCP fails
        if lat is None or lon is None:
            lat, lon = 20.5937, 78.9629

        # STEP 2: GET FORECAST (FAST)
        raw = await call_mcp(
            WEATHER_CONFIG,
            "get_forecast",
            {
                "latitude": float(lat),
                "longitude": float(lon),
                "days": 1
            }
        )

        if not raw or not raw.content:
            return {}

        text = raw.content[0].text

        def extract(pattern):
            try:
                m = re.search(pattern, text, re.IGNORECASE)
                return m.group(1).strip() if m else None
            except:
                return None

        high = extract(r"High:?\s*(\d+)°F")
        low = extract(r"Low:?\s*(\d+)°F")
        cond = extract(r"Conditions:?\s*(.*)")
        rain = extract(r"Precipitation Chance:?\s*(\d+)%")

        temp = "N/A"
        if high and low:
            temp = f"{round((int(high)-32)*5/9)}°C / {round((int(low)-32)*5/9)}°C"

        return {
            "temp": temp,
            "condition": cond or "Clear",
            "rain": rain or "0"
        }

    except Exception as e:
        print("Weather error:", e)
        return {}

# -----------------------------
# MAIN AGENT
# -----------------------------
async def travel_agent(query, budget=None, session_id="default"):
    q = query.lower()

    needs_weather = any(x in q for x in [
        "weather", "temperature", "climate", "rain", "hot", "cold"
    ])
    needs_stays = any(x in q for x in ["hotel", "stay", "airbnb"])

    # -----------------------------
    # BUDGET FOLLOW-UP
    # -----------------------------
    if session_id in SESSION_MEMORY:
        last = SESSION_MEMORY[session_id]

        if last.get("awaiting_budget"):
            place = last["place"]
            SESSION_MEMORY.pop(session_id)

            stays = await safe_call(tool_airbnb, place, query.lower())

            return [{
                "Destination": place,
                "Stays": stays
            }], f"💰 Showing {query} budget stays in {place}"

    # -----------------------------
    # WEATHER ONLY
    # -----------------------------
    if needs_weather and not needs_stays:
        place = re.sub(r"(weather|temperature|climate)", "", query, flags=re.I).strip()

        weather = await safe_call(tool_weather, place)

        if weather:
            return [], f"""
🌦️ {place.title()} Weather
🌡️ {weather['temp']}
☁️ {weather['condition']}
🌧️ Rain: {weather['rain']}%
"""
        return [], "Weather not available."

    # -----------------------------
    # HOTEL FLOW
    # -----------------------------
    if needs_stays:
        place = re.sub(r"(hotels|hotel|stay|airbnb)", "", query, flags=re.I).strip()

        stays = await safe_call(tool_airbnb, place, None)

        SESSION_MEMORY[session_id] = {
            "awaiting_budget": True,
            "place": place
        }

        return [{
            "Destination": place,
            "Stays": stays
        }], "💰 Do you have a budget? (low / medium / high)"

    # -----------------------------
    # DEFAULT DESTINATIONS
    # -----------------------------
    destinations = search_destinations(query)

    if destinations.empty:
        return [], "No destinations found."

    results = []

    for _, row in destinations.head(3).iterrows():
        place = row["Destination Name"]

        item = {
            "Destination": place,
            "Category": row["Category"]
        }

        if needs_weather:
            weather = await safe_call(tool_weather, place)
            if weather:
                item["Weather"] = weather

        results.append(item)

    explanation = generate_explanation(query, results)

    return results, explanation

# -----------------------------
# RUNNER
# -----------------------------
async def run_agent(query, budget=None, memory=None, session_id="default"):
    return await travel_agent(query, budget, session_id)