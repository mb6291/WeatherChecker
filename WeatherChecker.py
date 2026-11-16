import os
import json
from urllib import response
import requests
from dotenv import load_dotenv
from datetime import datetime

## GLOBALS
#Load API key from .env file
load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")

AQI_MEANING = {
    1: "Good",
    2: "Fair",
    3: "Moderate",
    4: "Poor",
    5: "Very Poor"
}

FAVORITE_FILES = "favorite.json"

# ============================================
# Version History
# --------------------------------------------
# V1: Basic weather lookup using city name
# V2: Added geocoding API + city disambiguation
# V3: Added menu + program loop for repeated use
# V4: Added main helper functions to refactor main()
#     making it easier to read and reducing 
#     redundent code
# ============================================

def safe_api_request(url, params, timeout=5):
    """
    Safely execute HTTP GET requests with timeout and error handling.
    Returns the parsed JSON dictionary/list on success, or None on 
    failure.
    """
    try:
        response = requests.get(url, params=params, timeout=timeout)

        # Automatically raises an HTTPError for invalid responses
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        print("\n[Network Error] Request timed out. Please check your connection.")
    except requests.exceptions.HTTPError as err:
        print(f"\n[API Error] HTTP status {response.status_code}: {err}")
    except requests.exceptions.ConnectionError:
        print("\n[Network Error] Could not connect to OpenWeather. Are you offline?")
    except requests.exceptions.RequestException as e:
        print(f"\n[Error] Something went wrong with the network request: {e}")

    return None



# -----------------------------
# SEARCH CITY (GEOCODING API)
# -----------------------------
def search_city(city):
    """Return a list of matching cities"""
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": city,
        "limit": 5,
        "appid": API_KEY
        }

    data = safe_api_request(url, params)
    # if the request failed, return an empty list so resolve_city doesn't crash
    return data if data is not None else []


# -----------------------------
# USER CHOOSE CITY V2
# -----------------------------
def choose_city(matches):
    """Ask the user to choose the correct city from a list."""
    print("\nMultiple locations found:")
    for i, m in enumerate(matches, start=1):
        state = m.get("state", "N/A")
        print(f"{i}. {m['name']}, {state}, {m['country']}")

    choice = get_int("\nWhich one did you mean? Enter number: ",
                     min_val=1,
                     max_val=len(matches))

    return matches[choice - 1]



# -----------------------------
# GET WEATHER BY LAT/LON
# -----------------------------
def get_weather(lat, lon):
    """Fetch current weather data using latitude and longitude."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "imperial"
    }

    data = safe_api_request(url, params)
    if not data:
        return None

    return {
        "city": data["name"],
        "temp": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "wind": data["wind"]["speed"],
        "description": data["weather"][0]["description"]
    }

# -----------------------------
# GET 5 DAY FORECAST
# -----------------------------
def get_forecast(lat, lon):
    """Fetch 5-day forecast data using latitude and longitude."""
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "imperial"
    }

    data = safe_api_request(url, params)
    if not data:
        return None

    # Summarize by day
    daily = {}
    for entry in data["list"]:
        date = entry["dt_txt"].split(" ")[0]
        temp = entry["main"]["temp"]
        desc = entry["weather"][0]["description"]

        if date not in daily:
            daily[date] = {
                "temps": [],
                "descriptions": []
            }

        daily[date]["temps"].append(temp)
        daily[date]["descriptions"].append(desc)

    # Build clean summary with high/low temps
    summary = []
    for date, info in daily.items():
        high_temp = max(info["temps"])
        low_temp = min(info["temps"])
        common_desc = max(set(info["descriptions"]), key=info["descriptions"].count)

        summary.append((date, high_temp, low_temp, common_desc))

    return summary

# -----------------------------
# GET air quality
# -----------------------------
def get_air_quality(lat, lon):
    """Fetch air quality index (AQI) and pollutant levels."""
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY
    }

    data = safe_api_request(url, params)
    if not data:
        return None
    
    info = data["list"][0]

    return {
        "aqi": info["main"]["aqi"],
        "components": info["components"]
    }


# New Addition 8/24
####
# JSON persistence helpers
# - Handle reading/writing from/to disk 
###################################################################################
def load_favorites():
    """Load favorite cities from a local JSON file"""
    if not os.path.exists(FAVORITE_FILES):
        return []
    try:
        with open(FAVORITE_FILES, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print("\n[Warning] Failed to read favorites file. Starting fresh.")
        return []

def save_favorites(favorites):
    """Save the list of favorite cities to a local JSON file."""
    try:
        with open(FAVORITE_FILES, "w", encoding="utf-8") as file:
            json.dump(favorites, file, indent=4)
        print("Saved to favorites!")
    except OSError as e:
        print(f"\n[Error] Could not save favorites: {e}")
##################################################################################

def choose_favorite():
    """Display saved favorites and return selected coordinates, or None."""
    favorites = load_favorites()
    if not favorites:
        print("\nNo saved favorites found.")
        return None

    print("\n--- Favorite Cities ---")
    for i, fav in enumerate(favorites, start=1):
        state = f", {fav['state']}" if fav.get("state") else ""
        print(f"{i}. {fav['name']}{state}, {fav['country']}")

    choice = get_int("\nSelect a favorite city number (0 to cancel): ", 
                     min_val=0, 
                     max_val=len(favorites))
    
    if choice == 0:
        return None

    selected = favorites[choice - 1]
    return selected["lat"], selected["lon"]

def choose_city(matches):
    """Ask the user to choose the correct city and offer to save to favorites."""
    print("\nMultiple locations found:")
    for i, m in enumerate(matches, start=1):
        state = m.get("state", "N/A")
        print(f"{i}. {m['name']}, {state}, {m['country']}")

    choice = get_int("\nWhich one did you mean? Enter number: ",
                     min_val=1,
                     max_val=len(matches))

    chosen = matches[choice - 1]

    # Ask to save to favorites
    save_choice = input("Would you like to save this city to your favorites? (y/n): ").strip().lower()
    if save_choice == "y":
        favorites = load_favorites()
        
        # Prevent duplicates by checking latitude and longitude
        already_saved = any(f["lat"] == chosen["lat"] and f["lon"] == chosen["lon"] for f in favorites)
        
        if not already_saved:
            fav_data = {
                "name": chosen["name"],
                "state": chosen.get("state", ""),
                "country": chosen["country"],
                "lat": chosen["lat"],
                "lon": chosen["lon"]
            }
            favorites.append(fav_data)
            save_favorites(favorites)
        else:
            print("City is already in your favorites list.")

    return chosen

# -----------------------------
# Cleans date format
# -----------------------------
def format_date(date_str):
    """ Convert YYYY-MM-DD into 'Mon (Aug 3)' format """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%a (%b %d)")


# ---------------------------------------------------------
# MAIN HELPER FUNCTIONS
# ---------------------------------------------------------

# def resolve_city():
#     """
#     Ask user for a city, perform search, 
#     handle disambiguation, return (lat, lon).
#     """
#     while True:
#         city = input("Enter a city: ").strip()

#         if city == "":
#             print("City name cannot be empty.")
#             continue

#         matches = search_city(city)
#         break

#     if len(matches) == 0:
#         print("No matches found.")
#         return None

#     elif len(matches) == 1:
#         chosen = matches[0]
#     else:
#         chosen = choose_city(matches)

#     return chosen["lat"], chosen["lon"]

def resolve_city():
    """Ask user to search for a city or load from saved favorites."""
    print("\nLocation Options:")
    print("1. Search for a city")
    print("2. Choose from Favorites")
    
    choice = get_int("Choose an option: ", min_val=1, max_val=2)
    
    if choice == 2:
        coords = choose_favorite()
        if coords:
            return coords
        print("Defaulting to city search...")

    while True:
        city = input("\nEnter a city name: ").strip()
        if city == "":
            print("City name cannot be empty.")
            continue

        matches = search_city(city)
        break

    if len(matches) == 0:
        print("No matches found.")
        return None
    elif len(matches) == 1:
        chosen = matches[0]
    else:
        chosen = choose_city(matches)

    return chosen["lat"], chosen["lon"]

# -----------------------------
# Main helper function 
# -----------------------------
def get_int(prompt, min_val=None, max_val=None):
    """
    Safely get an integer from the user with optional range limits.
    """
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a valid integer.")
            continue
        
        if min_val is not None and value < min_val:
            print(f"Please enter a number >= {min_val}.")
            continue

        if max_val is not None and value > max_val:
            print(f"Please enter a number <= {max_val}.")
            continue

        return value


# -----------------------------
# Main helper function 
# -----------------------------
def print_current_weather(weather, show_feels_like=False):
    """Print formatted current weather report"""
    if not weather:
        return

    print(f"\n--- Weather Report ---")
    print(f"City: {weather['city']}")
    print(f"Temperature: {weather['temp']}°F")

    if show_feels_like and "feels like" in weather:
        print(f"Feels Like: {weather['feels_like']}°F")

    print(f"Humidity: {weather['humidity']}%")
    print(f"Wind Speed: {weather['wind']} mph")
    print(f"Conditions: {weather['description'].title()}")


def print_five_day_forecast(forecast):
    """Print 5-day forecast"""
    if not forecast:
        return

    print("\n--- 5-Day Forecast ---")
    for date, high, low, desc in forecast:
        formatted_date = format_date(date)
        print(f"{formatted_date}:")
        print(f"    High {high:.1f}°F")
        print(f"    Low  {low:.1f}°F")
        print(f"    {desc.title()}")


def print_air_quality(aq):
    """Print air quality"""
    if not aq:
        return

    print("\n--- Air Quality Report ---")
    print(f"AQI: {aq['aqi']} ({AQI_MEANING[aq['aqi']]})")
    print("\nPollutants (μg/m³):")
    for comp, value in aq["components"].items():
        print(f"{comp.upper()}: {value}")



def main():
    print("==== WeatherChecker ====")

    while True:
        print("\n--Menu--")
        print("1. Check Weather")
        print("2. 5-Day Forecast")
        print("3. Air Quality")
        print("4. Full Weather Report")
        print("0. Exit")

        choice = get_int("Choose an option: ", min_val=0, max_val=4)

        if choice == 0:
            print("Goodbye!")
            break

        # Getting coordinates ONCE for all options that need them
        coords = resolve_city()
        if not coords:
            continue # User made no choice or search failed, back to menu

        lat, lon = coords

        # Check Single Day weather
        if choice == 1:
            weather = get_weather(lat, lon)
            print_current_weather(weather)
        
        # Check 5-day forecast
        elif choice == 2:
            forecast = get_forecast(lat, lon)
            print_five_day_forecast(forecast)
        
        # Check Air Quality
        elif choice == 3:
            aq = get_air_quality(lat, lon)
            print_air_quality(aq)

        # Full Weather report including day, 5-day and air quality
        elif choice == 4:
            print("\n==== Full Weather Report ====")
            
            weather = get_weather(lat, lon)
            aq = get_air_quality(lat, lon)
            forecast = get_forecast(lat, lon)
            
            print_current_weather(weather)
            print_air_quality(aq)
            print_five_day_forecast(forecast)



if __name__ == "__main__":
    main()