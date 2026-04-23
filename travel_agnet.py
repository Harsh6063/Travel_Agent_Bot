import asyncio
from transformers import pipeline
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from mcp.client.stdio import stdio_client
from mcp import ClientSession

from embeddings import search_destinations

# -----------------------------
# LLM
# -----------------------------
llm = pipeline("text-generation", model="distilgpt2")

def generate_explanation(prompt):
    return llm(
        prompt,
        max_new_tokens=120,
        truncation=True,
        temperature=0.7,
        do_sample=True
    )[0]["generated_text"]

# -----------------------------
# GEOCODER (FIX CORE ISSUE)
# -----------------------------
geolocator = Nominatim(user_agent="travel_agent")

def resolve_location(place, state):
    query = f"{place}, {state}, India"

    try:
        location = geolocator.geocode(query, timeout=3)

        if location:
            return location.address
        else:
            # fallback to state
            state_loc = geolocator.geocode(f"{state}, India", timeout=3)
            return state_loc.address if state_loc else query

    except GeocoderTimedOut:
        return query

# -----------------------------
# MCP CONFIGS
# -----------------------------
AIRBNB_CONFIG = {
    "command": "npx",
    "args": ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
}

WEATHER_CONFIG = {
    "command": "npx",
    "args": ["-y", "@dangahagan/weather-mcp"]
}

MAPS_CONFIG = {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-google-maps"]
}

# -----------------------------
# MCP CALL
# -----------------------------
async def call_mcp(config, tool, params):
    async with stdio_client(config) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, params)
            return result

# -----------------------------
# MCP TOOLS (WITH GEO FIX)
# -----------------------------
async def tool_weather(place, state):
    location = resolve_location(place, state)

    try:
        return await call_mcp(WEATHER_CONFIG, "get_forecast", {
            "location": location
        })
    except Exception as e:
        return f"Weather unavailable ({e})"


async def tool_airbnb(place, state):
    location = resolve_location(place, state)

    try:
        return await call_mcp(AIRBNB_CONFIG, "search", {
            "location": location
        })
    except Exception as e:
        return f"No stays found ({e})"


async def tool_maps(place, state):
    location = resolve_location(place, state)

    try:
        return await call_mcp(MAPS_CONFIG, "distance", {
            "destination": location
        })
    except Exception as e:
        return f"Distance unavailable ({e})"

# -----------------------------
# ROUTER
# -----------------------------
def mcp_router(query):
    tools = ["faiss"]

    q = query.lower()

    if "weather" in q:
        tools.append("weather")

    if "stay" in q or "hotel" in q:
        tools.append("airbnb")

    if "distance" in q:
        tools.append("maps")

    return tools

# -----------------------------
# MAIN AGENT
# -----------------------------
async def travel_agent(query):
    print("\n🧠 Query:", query)

    tools = mcp_router(query)

    destinations = search_destinations(query)

    results = []

    for _, row in destinations.iterrows():
        place = row["Destination Name"]
        state = row["State"]

        item = {
            "Destination": place,
            "State": state,
            "Category": row["Category"],
            "Budget": row["Budget"]
        }

        if "weather" in tools:
            item["Weather"] = await tool_weather(place, state)

        if "airbnb" in tools:
            item["Stays"] = await tool_airbnb(place, state)

        if "maps" in tools:
            item["Distance"] = await tool_maps(place, state)

        results.append(item)

    # -----------------------------
    # LLM EXPLANATION (OPTIMIZED)
    # -----------------------------
    short_results = [
        {"place": r["Destination"], "category": r["Category"]}
        for r in results
    ]

    prompt = f"""
    User query: {query}
    Recommended places: {short_results}
    Explain why these are good options.
    """

    explanation = generate_explanation(prompt)

    return results, explanation

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    query = "budget mountain trip with weather and stay"

    results, explanation = asyncio.run(travel_agent(query))

    print("\n📍 RESULTS:")
    for r in results:
        print(r)

    print("\n🧾 EXPLANATION:")
    print(explanation)