import sqlite3
from datetime import datetime

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
    time_now = datetime.now().isoformat(timespec="seconds")
    for price, address, postcode, name in results:
        cursor.execute("""
            INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?)
""", (time_now, name, address, postcode, fuel_type, price))
    conn.commit()
    conn.close()

def print_saved_prices():
    conn = sqlite3.connect("fuel.db")
    for row in conn.execute("SELECT * FROM prices"):
        print(row)
    conn.close()

def get_latest_prices():
    conn = sqlite3.connect("fuel.db")
    cursor = conn.execute("""
        SELECT * FROM prices
        WHERE recorded_at = (SELECT MAX(recorded_at) FROM prices)
        ORDER BY price
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_station_history(station_name):
    conn = sqlite3.connect("fuel.db")
    cursor = conn.execute("""
        SELECT recorded_at, price FROM prices
        WHERE station_name = ?
    """, (station_name,))
    rows = cursor.fetchall()
    conn.close()
    return rows