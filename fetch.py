from main import get_all_stations, filter_by_postcode, get_cheapest
from db import save_results

if __name__ == "__main__":
    stations = get_all_stations()
    matches = filter_by_postcode(stations, "SO")
    results = get_cheapest(matches, "E10")
    save_results(results, "E10")