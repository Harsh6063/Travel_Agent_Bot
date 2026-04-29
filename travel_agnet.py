import os
import asyncio
import json
import re
from dotenv import load_dotenv
from groq import Groq
from geopy.geocoders import Nominatim
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

from embeddings import search_destinations

# -----------------------------
# ENV + LLM
# -----------------------------
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_explanation(query, results):
    try:
        prompt = f"""
        User query: {query}
        Travel Data: {results}

        As a travel expert, briefly explain why these options are good. 
        Keep it professional and concise.
        """
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except:
        return "These are excellent travel options tailored to your preferences."

# -----------------------------
# GEO
# -----------------------------
geo = Nominatim(user_agent="travel_agent")

def get_coordinates(place, state):
    try:
        loc = geo.geocode(f"{place}, {state}, India", timeout=5)
        if loc:
            # Force to floats - MCP servers require float types
            return float(loc.latitude), float(loc.longitude)
    except:
        pass
    return 20.5937, 78.9629

# -----------------------------
# MCP CONFIG
# -----------------------------
AIRBNB_CONFIG = StdioServerParameters(
    command="npx",
    args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
)

WEATHER_CONFIG = StdioServerParameters(
    command="npx",
    args=["-y", "@dangahagan/weather-mcp"]
)

# -----------------------------
# MCP CALL
# -----------------------------
async def call_mcp(config, tool, params):
    async with stdio_client(config) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, params)

# -----------------------------
# HELPERS 
# -----------------------------
async def safe_call(func, *args, timeout=12):
    try:
        return await asyncio.wait_for(func(*args), timeout)
    except Exception as e:
        print(f"⚠️ Tool Error: {e}")
        return None

def clean_text(value):
    if not value: return "N/A"
    return value.replace("**", "").strip()

def extract_price_and_nights(price_str):
    price_match = re.search(r"₹([\d,]+)", price_str)
    nights_match = re.search(r"for (\d+) nights", price_str)
    if not price_match: return 0, 1
    total = int(price_match.group(1).replace(",", ""))
    nights = int(nights_match.group(1)) if nights_match else 1
    return total, nights

def filter_by_budget(results, budget):
    filtered = []
    for r in results:
        total, nights = extract_price_and_nights(r["price"])
        per_night = total / nights
        if budget == "low" and per_night <= 3000: filtered.append(r)
        elif budget == "medium" and 3000 < per_night <= 8000: filtered.append(r)
        elif budget == "high" and per_night > 8000: filtered.append(r)
    return filtered if filtered else results

# -----------------------------
# TOOLS (Weather Logic Fixed)
# -----------------------------
async def tool_airbnb(place, state, budget):
    try:
        raw = await call_mcp(AIRBNB_CONFIG, "airbnb_search", 
                               {"location": f"{place}, {state}, India", "adults": 2})
        data = json.loads(raw.content[0].text)
        stays = []
        for item in data.get("searchResults", [])[:5]:
            try:
                stays.append({
                    "name": item["demandStayListing"]["description"]["name"]["localizedStringWithTranslationPreference"],
                    "price": item["structuredDisplayPrice"]["primaryLine"]["accessibilityLabel"],
                    "link": item.get("url", "")
                })
            except: continue
        return filter_by_budget(stays, budget)
    except: return []

async def tool_weather(place, state):
    try:
        lat, lon = get_coordinates(place, state)
        raw = await call_mcp(WEATHER_CONFIG, "get_forecast", 
                             {"latitude": lat, "longitude": lon})
        
        if not raw or not raw.content: return {}
        text = raw.content[0].text

        # Improved Regex to catch values even without '##' formatting
        def safe_search(pat):
            m = re.search(pat, text, re.IGNORECASE)
            return m.group(1) if m else None

        high = safe_search(r"High:?\s*(\d+)°F")
        low = safe_search(r"Low:?\s*(\d+)°F")
        cond = safe_search(r"Conditions:?\s*(.*)")
        rain = safe_search(r"Precipitation Chance:?\s*(\d+)%")

        if high and low:
            temp = f"{round((int(high)-32)*5/9)}°C / {round((int(low)-32)*5/9)}°C"
        else: temp = "N/A"

        return {
            "temp": temp,
            "condition": clean_text(cond),
            "rain": f"{rain}%" if rain else "0%"
        }
    except Exception as e:
        print(f"Weather tool failed: {e}")
        return {}

# -----------------------------
# MAIN AGENT
# -----------------------------
async def travel_agent(query, budget):
    q = query.lower()
    tools_needed = {
        "weather": any(w in q for w in ["weather", "temp", "climate"]),
        "stays": any(w in q for w in ["stay", "hotel", "airbnb"])
    }

    destinations = search_destinations(query)
    
    if destinations.empty:
        import pandas as pd
        destinations = pd.DataFrame([
            {"Destination Name": "Goa", "State": "Goa", "Category": "Beach"},
            {"Destination Name": "Manali", "State": "Himachal Pradesh", "Category": "Nature"}
        ])

    final_results = []

    for _, row in destinations.head(3).iterrows():
        place, state = row["Destination Name"], row["State"]
        item = {"Destination": place, "Category": row["Category"]}

        tasks = []
        if tools_needed["weather"]:
            tasks.append(safe_call(tool_weather, place, state))
        else:
            tasks.append(asyncio.sleep(0, result=None))

        if tools_needed["stays"]:
            tasks.append(safe_call(tool_airbnb, place, state, budget))
        else:
            tasks.append(asyncio.sleep(0, result=None))

        weather_res, stays_res = await asyncio.gather(*tasks)
        
        if weather_res: item["Weather"] = weather_res
        if stays_res: item["Stays"] = stays_res
        
        final_results.append(item)

    explanation = generate_explanation(query, final_results)
    
    return final_results, explanation

async def run_agent(query, budget, memory):
    return await travel_agent(query, budget)