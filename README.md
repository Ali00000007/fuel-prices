# UK Fuel Price Tracker

A Python tool that finds the cheapest fuel prices in a given UK postcode area, using the government's Fuel Finder open data API.

Under the Motor Fuel Price (Open Data) Regulations 2025, all UK petrol stations must report their prices to a central service within 30 minutes of any change at the pump. This tool pulls that data, filters it to a postcode area, and ranks stations by price for a chosen fuel type.

## What it does

- Authenticates with the Fuel Finder API using OAuth 2.0 client credentials
- Caches the access token and reuses it until close to expiry, as the API guidance requires
- Pages through all batches of both the station and price endpoints (~8,000 forecourts nationally)
- Joins the two datasets on each station's `node_id`
- Filters to a postcode prefix and prints results sorted cheapest first

## Example output

```
  153.9  REGENTS PARK ROAD SERVICE STATION        SO15 8SD
  156.9  TESCO SIZER WAY                          SO40 3TA
  157.9  E W PINCHBECK & SONS                     SO32 1AB
```

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

```bash
python main.py
```

The postcode prefix and fuel type are currently set in `main.py`. Edit the call in the `__main__` block to change them.

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

**Joining.** Prices and station details come from separate endpoints with no location data on the price records and no prices on the station records. They share a `node_id`, which is the join key. The current implementation is a nested loop; building a dictionary keyed on `node_id` would reduce this from O(n²) to O(n) and is the obvious next optimisation.

**Filtering.** Filtering is done on postcode prefix rather than the `city` field. The city data is inconsistent in ways that would silently drop results — values include `EASTLEIGH SOUTHAMPTON`, empty strings, and towns that don't match the station's own address. Postcode prefixes are reliable.

## Known limitations

- A full run fetches every UK station and price record, which takes around a minute
- Postcode prefix is a coarse geographic filter; the API returns latitude and longitude per station, so distance-based filtering would be more accurate
- Results are printed and discarded, with no history kept between runs
- Not all stations stock all fuel types, so a station may be absent from results for one fuel and present for another

## Planned

- [ ] Store results in SQLite with timestamps to build price history
- [ ] Distance-based filtering using station coordinates
- [ ] Command-line arguments for postcode, fuel type, and result limit
- [ ] Web interface with a price history chart

## Data source

Fuel Finder, operated by VE3 Global Ltd on behalf of the Department for Energy Security and Net Zero. Data is published under the Open Government Licence v3.0.