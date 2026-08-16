# UK Fuel Price Tracker

A Python tool that tracks fuel prices across a UK postcode area using the government's Fuel Finder open data API, stores them in SQLite, and serves the results through a small Flask web interface.

Under the Motor Fuel Price (Open Data) Regulations 2025, all UK petrol stations must report their prices to a central service within 30 minutes of any change at the pump. This project pulls that data, filters it to a postcode area, records it with a timestamp, and lets you view current prices or a single station's price history.

## What it does

- Authenticates with the Fuel Finder API using OAuth 2.0 client credentials
- Caches the access token and reuses it until close to expiry, as the API guidance requires
- Pages through all batches of both the station and price endpoints (~8,000 forecourts nationally)
- Joins the two datasets on each station's `node_id`
- Filters to a postcode prefix and stores results in SQLite with a timestamp
- Serves a table of current prices and a per-station history page over HTTP

## Project structure

```
main.py           API client, filtering, and the fetch job
db.py             SQLite connection, schema, and queries
app.py            Flask web server
templates/
  prices.html     Current prices, cheapest first
  history.html    One station's price over time
```

`main.py` writes to the database. `app.py` only reads from it. The two never talk to each other directly, which keeps the fetch job independent of the web server.

## Requirements

- Python 3.9+
- Fuel Finder API credentials (client ID and secret)

Register as an Information Recipient at the [Fuel Finder Developer Portal](https://www.developer.fuel-finder.service.gov.uk/) using a GOV.UK One Login account. Registration is open to individuals, not just organisations.

## Setup

```bash
git clone <your-repo-url>
cd fuel-prices

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your credentials:

```
FF_CLIENT_ID=your-client-id
FF_CLIENT_SECRET=your-client-secret
```

`.env` is gitignored and must never be committed.

## Usage

### Fetching prices

```bash
python main.py
```

Fetches every station and price record, filters to the configured postcode prefix, and appends the results to `fuel.db` with the current timestamp. Takes roughly a minute. Run it repeatedly over days or weeks to build price history.

The postcode prefix and fuel type are set in the `__main__` block of `main.py`. The `MODE` variable there also switches between fetching and printing saved results from the terminal.

### Web interface

```bash
python app.py
```

Then open `http://localhost:5000`.

| Route | Shows |
|-------|-------|
| `/` | Most recent snapshot, cheapest first |
| `/history?station=NAME` | One station's recorded prices over time |

### Fuel type codes

| Code | Fuel |
|------|------|
| `E5` | Super unleaded (5% ethanol) |
| `E10` | Standard unleaded (10% ethanol) |
| `B7_STANDARD` | Standard diesel |
| `B7_PREMIUM` | Premium diesel |
| `B10` | 10% biodiesel |

## How it works

**Authentication.** A POST to `/api/v1/oauth/generate_access_token` with the client ID and secret as a JSON body returns an access token valid for one hour. The token is cached in module-level state with its expiry timestamp; `get_token()` returns the cached value unless it is within 60 seconds of expiring. This matters because a full run makes 30+ requests, and the API documentation explicitly asks callers not to request a new token per call.

**Pagination.** Both data endpoints require a `batch-number` query parameter starting at 1. The API signals the end of the data with a `404`, not an empty response, so the paging loop catches `requests.HTTPError` and breaks. A maximum batch count guards against an infinite loop.

**Joining.** Prices and station details come from separate endpoints, with no location data on the price records and no prices on the station records. They share a `node_id`, which is the join key. The current implementation is a nested loop; building a dictionary keyed on `node_id` would reduce this from O(n^2) to O(n) and is the obvious next optimisation.

**Filtering.** Filtering is done on postcode prefix rather than the `city` field. The city data is inconsistent in ways that would silently drop results — values include `EASTLEIGH SOUTHAMPTON`, empty strings, and towns that don't match the station's own address. Postcode prefixes are reliable.

**Storage.** Each run appends a full set of rows tagged with a single ISO 8601 timestamp, rather than updating in place, so the table accumulates history. Timestamps are stored as `TEXT`; ISO 8601 sorts correctly as a string, which is what makes `MAX(recorded_at)` work for finding the latest snapshot.

**Queries.** All parameters are passed using `?` placeholders rather than string formatting, so user-supplied values — including the station name from the web request — can never be interpreted as SQL.

## Known limitations

- A full run fetches every UK station and price record, which takes around a minute; it cannot run inside a web request
- Postcode prefix is a coarse geographic filter; the API returns latitude and longitude per station, so distance-based filtering would be more accurate
- SQLite is single-file and local, which is fine for one process but would need replacing with Postgres for a deployed multi-process setup
- Not all stations stock all fuel types, so a station may appear for one fuel and not another
- The fetch is manual; there is no scheduling yet

## Planned

- [ ] Link station names on the prices page through to their history
- [ ] Schedule the fetch so history accumulates automatically
- [ ] Distance-based filtering using station coordinates
- [ ] Command-line arguments for postcode, fuel type, and result limit
- [ ] Price history chart
- [ ] Containerise the web server, fetch job, and database

## Data source

Fuel Finder, operated by VE3 Global Ltd on behalf of the Department for Energy Security and Net Zero. Data is published under the Open Government Licence v3.0.