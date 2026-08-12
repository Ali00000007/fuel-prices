from datetime import datetime
import os
import time
import sqlite3

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.fuel-finder.service.gov.uk"
TOKEN_URL = f"{BASE_URL}/api/v1/oauth/generate_access_token"
FUEL_PRICES_URL = f"{BASE_URL}/api/v1/pfs/fuel-prices"
STATIONS_URL = f"{BASE_URL}/api/v1/pfs"



CLIENT_ID = os.environ["FF_CLIENT_ID"]
CLIENT_SECRET = os.environ["FF_CLIENT_SECRET"]


_access_token = None
_token_expires_at = 0


def get_token():
    global _access_token, _token_expires_at

    if _access_token and time.time() < _token_expires_at - 60:
        return _access_token

    resp = requests.post(TOKEN_URL, json={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    resp.raise_for_status()
    data = resp.json()["data"]

    _access_token = data["access_token"]
    _token_expires_at = time.time() + data["expires_in"]
    return _access_token

def get_prices(batch):
    resp = requests.get(FUEL_PRICES_URL, headers={
        "Authorization": f"Bearer {get_token()}"
    },
    params={
        "batch-number" : batch,
    })
    resp.raise_for_status()
    return resp.json()

def get_stations(batch):
    resp = requests.get(STATIONS_URL, headers={
            "Authorization": f"Bearer {get_token()}"
        },
        params={
            "batch-number" : batch
        })
    resp.raise_for_status()
    return resp.json()

def get_all_stations():
    stations = []
    counter = 1
    while True:
        try:
            batch = get_stations(counter)
        except requests.HTTPError:
            break
        if not batch or counter > 100:
            break
        else:
            stations.extend(batch)
            counter += 1
    return stations

def get_all_prices():
    prices = []
    counter = 1
    while True:
            try:
                batch = get_prices(counter)
            except requests.HTTPError:
                break
            if not batch or counter > 100:
                break
            else:
                prices.extend(batch)
                counter += 1
    return prices

def filter_by_postcode(stations, prefix):
    matches = []
    for station in stations:
        postcode = station["location"]["postcode"]
        if not postcode: continue
        elif postcode.startswith(prefix):
            matches.append(station)
    return matches

def show_prices(stations, fuel_type):
    prices = get_all_prices()
    print(f"stations: {len(stations)}, prices: {len(prices)}")
    matched = 0
    results = []
    for station in stations:
        for record in prices:
            if record["node_id"] == station["node_id"]:
                for entry in record["fuel_prices"]:
                    if entry["fuel_type"] == fuel_type:
                        results.append((entry["price"], station["location"]["address_line_1"], station["location"]["postcode"], station["trading_name"]))
    results.sort()
    return results

def save_results(results, fuel_type):
    conn = sqlite3.connect("fuel.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
                recorded_at TEXT,
                station_name TEXT,
                address TEXT,
                postcode TEXT,
                fuel_type TEXT,
                price REAL
            )
""")
    time_now = datetime.now().isoformat()
    for price, address, postcode, name in results:
        cursor.execute("""
            INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?)
""", (time_now, name, address, postcode, fuel_type, price))
    conn.commit()
    conn.close()

def show_results():
    conn = sqlite3.connect("fuel.db")
    for row in conn.execute("SELECT * FROM prices LIMIT 5"):
        print(row)

if __name__ == "__main__":
    #stations = get_all_stations()
    #matches = filter_by_postcode(stations, "SO")
    #results = show_prices(matches, "E10")
    #save_results(results, "E10")
    #for price, address, postcode, name in results:
    #    print(f"{price:>7}  {name:<40} {postcode}")
    show_results()