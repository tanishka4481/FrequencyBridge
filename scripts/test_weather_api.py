import requests

def test_api():
    tokyo = "https://api.open-meteo.com/v1/forecast?latitude=35.6895&longitude=139.6917&current=cloudcover,windspeed_10m&timezone=Asia%2FTokyo"
    osaka = "https://api.open-meteo.com/v1/forecast?latitude=34.6937&longitude=135.5023&current=cloudcover,windspeed_10m&timezone=Asia%2FTokyo"

    print("Fetching Tokyo...")
    print(requests.get(tokyo).json())
    print("\nFetching Osaka...")
    print(requests.get(osaka).json())

if __name__ == "__main__":
    test_api()
