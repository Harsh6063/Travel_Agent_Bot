import asyncio
import json
import re
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
from geopy.geocoders import Nominatim

# -----------------------------
# MCP CONFIGS
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
# GEO
# -----------------------------
geo = Nominatim(user_agent="travel_app")

def get_coordinates(place, state):
    try:
        loc = geo.geocode(f"{place}, {state}, India")
        if loc:
            return loc.latitude, loc.longitude
    except:
        pass
    return 20.5937, 78.9629

# -----------------------------
# MCP CALL
# -----------------------------
async def call_mcp(config, tool, params):
    async with stdio_client(config) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, params)

# -----------------------------
# CLEAN TEXT
# -----------------------------
def clean_text(value):
    if not value:
        return "N/A"
    return value.replace("**", "").strip()

# -----------------------------
# PRICE PARSING (IMPORTANT)
# -----------------------------
def extract_price_and_nights(price_str):
    """
    Example: '₹15,178 for 5 nights'
    """
    price_match = re.search(r"₹([\d,]+)", price_str)
    nights_match = re.search(r"for (\d+) nights", price_str)

    if not price_match:
        return 0, 1

    total_price = int(price_match.group(1).replace(",", ""))
    nights = int(nights_match.group(1)) if nights_match else 1

    return total_price, nights

def filter_by_budget(results, budget):
    filtered = []

    for r in results:
        total_price, nights = extract_price_and_nights(r["price"])
        per_night = total_price / nights if nights else total_price

        if budget == "low" and per_night <= 5000:
            filtered.append(r)
        elif budget == "medium" and 5000 < per_night <= 10000:
            filtered.append(r)
        elif budget == "high" and per_night > 10000:
            filtered.append(r)

    return filtered if filtered else results

# -----------------------------
# AIRBNB TOOL
# -----------------------------
async def tool_airbnb(place, state, budget):
    location = f"{place}, {state}, India"

    try:
        raw = await call_mcp(
            AIRBNB_CONFIG,
            "airbnb_search",
            {"location": location, "adults": 2}
        )

        if not raw or not raw.content:
            return []

        text_data = raw.content[0].text
        data = json.loads(text_data)

        results = []

        for item in data.get("searchResults", [])[:5]:
            try:
                name = item["demandStayListing"]["description"]["name"]["localizedStringWithTranslationPreference"]
                price = item["structuredDisplayPrice"]["primaryLine"]["accessibilityLabel"]
                url = item.get("url", "")

                results.append({
                    "name": name,
                    "price": price,
                    "link": url
                })
            except:
                continue

        # 🔥 APPLY PER-NIGHT FILTER
        results = filter_by_budget(results, budget)

        return results

    except Exception as e:
        return f"Airbnb error: {e}"

# -----------------------------
# WEATHER TOOL
# -----------------------------
async def tool_weather(place, state):
    lat, lon = get_coordinates(place, state)

    try:
        raw = await call_mcp(
            WEATHER_CONFIG,
            "get_forecast",
            {
                "latitude": lat,
                "longitude": lon
            }
        )

        if not raw or not raw.content:
            return "Weather unavailable"

        text = raw.content[0].text
        parts = text.split("##")

        if len(parts) < 2:
            return "Weather data unavailable"

        today = parts[1]

        def safe_search(pattern):
            match = re.search(pattern, today)
            return match.group(1) if match else None

        high_f = safe_search(r"High (\d+)°F")
        low_f = safe_search(r"Low (\d+)°F")
        condition = clean_text(safe_search(r"Conditions:\s*(.*)"))
        rain_val = safe_search(r"Precipitation Chance:\s*(\d+)%")
        wind = clean_text(safe_search(r"Wind:\s*(.*)"))

        if high_f and low_f:
            high_c = round((int(high_f) - 32) * 5/9)
            low_c = round((int(low_f) - 32) * 5/9)
            temp = f"{high_c}°C / {low_c}°C"
        else:
            temp = "N/A"

        rain = f"{rain_val}%" if rain_val else "N/A"

        return {
            "location": place,
            "temperature": temp,
            "condition": condition,
            "rain": rain,
            "wind": wind
        }

    except Exception as e:
        return f"Weather error: {e}"

# -----------------------------
# MAIN
# -----------------------------
async def main():
    place = input("Enter destination: ")
    budget = input("Enter budget (low/medium/high): ").lower()
    state = place

    print("\n🌍 Destination:", place)

    # Airbnb
    print("\n🏨 Airbnb Stays:\n")
    stays = await tool_airbnb(place, state, budget)

    if isinstance(stays, list):
        for i, s in enumerate(stays, 1):
            print(f"{i}. {s['name']}")
            print(f"   💰 {s['price']}")
            print(f"   🔗 {s['link']}\n")
    else:
        print(stays)

    # Weather
    print("\n🌦️ Weather:\n")
    weather = await tool_weather(place, state)

    if isinstance(weather, dict):
        print(f"📍 {weather['location']}")
        print(f"🌡️ Temp: {weather['temperature']}")
        print(f"☁️ Condition: {weather['condition']}")
        print(f"🌧️ Rain: {weather['rain']}")
        print(f"💨 Wind: {weather['wind']}")
    else:
        print(weather)

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())