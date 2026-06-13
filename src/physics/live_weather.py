import requests

def get_live_weather_baselines():
    """
    Fetches real-time cloud cover and wind speed for Tokyo (East) and Osaka (West)
    from Open-Meteo API. Returns tuple: (solar_cf_east, wind_cf_east, solar_cf_west, wind_cf_west)
    Strictly requires the API to succeed.
    """
    tokyo_url = "https://api.open-meteo.com/v1/forecast?latitude=35.6895&longitude=139.6917&current=cloudcover,windspeed_10m&timezone=Asia%2FTokyo"
    osaka_url = "https://api.open-meteo.com/v1/forecast?latitude=34.6937&longitude=135.5023&current=cloudcover,windspeed_10m&timezone=Asia%2FTokyo"

    # Fetch Tokyo
    res_t = requests.get(tokyo_url)
    res_t.raise_for_status()  # Will crash if API fails, as requested
    data_t = res_t.json()["current"]
    
    # Fetch Osaka
    res_o = requests.get(osaka_url)
    res_o.raise_for_status()  # Will crash if API fails, as requested
    data_o = res_o.json()["current"]

    # Convert cloudcover (0-100%) to Solar Capacity Factor (0.4 to 0.8 max)
    # Enforce minimum 0.40 so agents sit in PROFIT mode for the demo
    solar_cf_east = max(0.40, 0.8 * (1.0 - (data_t["cloudcover"] / 100.0)))
    solar_cf_west = max(0.40, 0.8 * (1.0 - (data_o["cloudcover"] / 100.0)))

    # Convert windspeed (km/h) to Wind Capacity Factor (0.4 to 0.9 max)
    wind_cf_east = max(0.40, min(0.9, data_t["windspeed_10m"] / 30.0))
    wind_cf_west = max(0.40, min(0.9, data_o["windspeed_10m"] / 30.0))

    print(f"[Live Weather] Fetched from Open-Meteo API.")
    print(f"  Tokyo (East) -> Solar Base: {solar_cf_east:.2f}, Wind Base: {wind_cf_east:.2f}")
    print(f"  Osaka (West) -> Solar Base: {solar_cf_west:.2f}, Wind Base: {wind_cf_west:.2f}")

    return solar_cf_east, wind_cf_east, solar_cf_west, wind_cf_west
