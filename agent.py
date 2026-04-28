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
# 1. SETUP & LLM (Groq)
# -----------------------------
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_explanation(query, results):
    """Uses Groq to explain why the results match the user's intent."""
    try:
        prompt = f"""
        User Query: {query}
        Travel Data: {results}

        As an expert travel agent, briefly explain why these 3 destinations are perfect.
        - Mention the specific weather conditions and stay options found.
        - Keep the tone helpful and concise (max 4 sentences).
        """
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except:
        return "These destinations are top-rated picks based on your interests."

# -----------------------------
# 2. CONFIGS & GEO
# -----------------------------
AIRBNB_CONFIG = StdioServerParameters(
    command="npx",
    args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
)

WEATHER_CONFIG = StdioServerParameters(
    command="npx",
    args=["-y", "@dangahagan/weather-mcp"]
)

geo = Nominatim(user_agent="travel_agent_pro")

def get_coordinates(place, state):
    try:
        loc = geo.geocode(f"{place}, {state}, India", timeout=5)
        if loc: return float(loc.latitude), float(loc.longitude)
    except: pass
    return 20.5937, 78.9629  # Default to India center

# -----------------------------
# 3. HELPERS (Filtering & Safety)
# -----------------------------
async def call_mcp(config, tool, params):
    """Standardized MCP Tool caller."""
    async with stdio_client(config) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, params)

async def safe_call(func, *args, timeout=12):
    """Prevents the entire agent from crashing if one tool fails."""
    try:
        return await asyncio.wait_for(func(*args), timeout)
    except Exception as e:
        print(f"⚠️ Tool Alert ({args[0] if args else ''}): {e}")
        return None

def extract_price_and_nights(price_str):
    """Parses '₹15,000 for 5 nights' -> (15000, 5)."""
    price_match = re.search(r"₹([\d,]+)", price_str)
    nights_match = re.search(r"for (\d+) nights", price_str)
    if not price_match: return 0, 1
    total = int(price_match.group(1).replace(",", ""))
    nights = int(nights_match.group(1)) if nights_match else 1
    return total, nights

def filter_by_budget(results, budget):
    """Filters Airbnb results by price per night."""
    filtered = []
    for r in results:
        total, nights = extract_price_and_nights(r["price"])
        per_night = total / nights
        if budget == "low" and per_night <= 3000: filtered.append(r)
        elif budget == "medium" and 3000 < per_night <= 8000: filtered.append(r)
        elif budget == "high" and per_night > 8000: filtered.append(r)
    return filtered if filtered else results

# -----------------------------
# 4. TOOLS
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
        raw = await call_mcp(WEATHER_CONFIG, "get_forecast", {"latitude": lat, "longitude": lon})
        text = raw.content[0].text
        parts = text.split("##")
        if len(parts) < 2: return {}
        today = parts[1]
        
        def safe_search(pat):
            m = re.search(pat, today)
            return m.group(1) if m else None

        high, low = safe_search(r"High (\d+)°F"), safe_search(r"Low (\d+)°F")
        temp = f"{round((int(high)-32)*5/9)}°C / {round((int(low)-32)*5/9)}°C" if high and low else "N/A"
        
        return {
            "temp": temp,
            "condition": (safe_search(r"Conditions:\s*(.*)") or "N/A").replace("**", ""),
            "rain": safe_search(r"Precipitation Chance:\s*(\d+)%") or "0"
        }
    except: return {}

# -----------------------------
# 5. AGENT ENGINE
# -----------------------------
async def travel_agent(query, budget):
    print(f"🧠 Processing Query: {query} (Budget: {budget})")
    
    # Check if tools are actually needed
    q_lower = query.lower()
    needs_weather = any(w in q_lower for w in ["weather", "temp", "climate"])
    needs_stays = any(w in q_lower for w in ["stay", "hotel", "airbnb"])

    destinations = search_destinations(query)
    if destinations.empty:
        return [], "No matching destinations found."

    results = []
    # Process top 3 destinations
    for _, row in destinations.head(3).iterrows():
        place, state = row["Destination Name"], row["State"]
        item = {"Destination": place, "Category": row["Category"]}

        # Parallel Tool Calling (Faster)
        tasks = []
        tasks.append(safe_call(tool_weather, place, state) if needs_weather else asyncio.sleep(0))
        tasks.append(safe_call(tool_airbnb, place, state, budget) if needs_stays else asyncio.sleep(0))

        weather_data, stays_data = await asyncio.gather(*tasks)
        
        if weather_res := weather_data: item["Weather"] = weather_res
        if stays_res := stays_data: item["Stays"] = stays_res
        
        results.append(item)

    # Final logic: Output generation
    explanation = generate_explanation(query, results)
    
    # Format the terminal output nicely
    output_text = f"\n{explanation}\n"
    for r in results:
        output_text += f"\n📍 {r['Destination']} ({r['Category']})"
        if "Weather" in r:
            w = r["Weather"]
            output_text += f"\n   🌦️ {w.get('temp')} | {w.get('condition')} | {w.get('rain')}% Rain"
        if "Stays" in r:
            output_text += "\n   🏨 Top Stays:"
            for s in r["Stays"][:2]:
                output_text += f"\n      - {s['name']} ({s['price']})"
        output_text += "\n"

    return results, output_text

# -----------------------------
# FASTAPI / RUNNER
# -----------------------------
async def run_agent(query, budget, memory=None):
    return await travel_agent(query, budget)

if __name__ == "__main__":
    q = input("What kind of trip are you looking for? ")
    b = input("Budget (low/medium/high): ")
    _, final_msg = asyncio.run(run_agent(q, b))
    print(final_msg)