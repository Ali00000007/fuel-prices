# UK Fuel Price Tracker

**Live at [fuel.solenttransfers.co.uk](https://fuel.solenttransfers.co.uk)**

Tracks fuel prices across a UK postcode area using the government's Fuel Finder open data API, stores them in SQLite with timestamps, and serves current prices and per-station history through a Flask web interface. Runs as Docker containers on a VPS behind Caddy, with a twice-daily scheduled fetch.

Under the Motor Fuel Price (Open Data) Regulations 2025, all UK petrol stations must report their prices to a central service within 30 minutes of any change at the pump. This project pulls that data, filters it to a postcode area, records it, and lets you see what a station charges now and what it has charged over time.

## What it does

- Authenticates with the Fuel Finder API using OAuth 2.0 client credentials
- Caches the access token and reuses it until close to expiry, as the API guidance requires
- Pages through all batches of both the station and price endpoints (~8,000 forecourts nationally)
- Joins the two datasets on each station's `node_id`
- Filters to a postcode prefix and appends results to SQLite with a UTC timestamp
- Serves a table of current prices and a per-station history page
- Runs as three Docker services, fetched twice daily by cron, served over HTTPS

## Architecture

```
                    internet
                       │
                   :443 │ HTTPS
                       ▼
              ┌──────────────────┐
              │      caddy       │   TLS termination, reverse proxy
              └────────┬─────────┘
                       │ web:5000  (internal Docker network)
                       ▼
              ┌──────────────────┐
              │       web        │   Flask — reads only
              └────────┬─────────┘
                       │
                  ┌────▼─────┐
                  │ fuel.db  │      bind-mounted from the host
                  └────▲─────┘
                       │
              ┌────────┴─────────┐
              │     fetcher      │   run by cron, exits when done
              └────────┬─────────┘
                       │
                Fuel Finder API
```

`fetcher` writes, `web` reads, and neither imports the other. That separation is what allows them to run as independent services built from the same image.

## Project structure

```
fetch.py             Entry point for the fetch job
main.py              API client — auth, pagination, filtering, the join
db.py                SQLite connection, schema, and queries
app.py               Flask web server
templates/
  prices.html        Current prices, cheapest first
  history.html       One station's price over time
Dockerfile           Image definition, shared by web and fetcher
docker-compose.yml   Service definitions
Caddyfile            Reverse proxy and TLS configuration
```

## Requirements

- Fuel Finder API credentials (client ID and secret)
- Docker, or Python 3.9+ to run it directly

Register as an Information Recipient at the [Fuel Finder Developer Portal](https://www.developer.fuel-finder.service.gov.uk/) using a GOV.UK One Login account. Registration is open to individuals, not just organisations.

## Setup

Clone the repo, then copy `.env.example` to `.env` and fill in your credentials:

```
FF_CLIENT_ID=your-client-id
FF_CLIENT_SECRET=your-client-secret
```

`.env` is excluded from both git and the Docker image, and must never be committed.

## Running with Docker

```bash
touch fuel.db                      # must exist, or Docker creates a directory at the mount point
docker compose up -d --build web   # web only; caddy needs a real domain pointed at the host
docker compose run --rm fetcher    # fetch prices once
```

Then open `http://localhost:5000`.

The database is bind-mounted, so data written by the fetcher persists on the host and is visible to the web service immediately. `--build` is required after any code change — `COPY . .` snapshots the source at build time, so edits are not picked up otherwise.

## Running without Docker

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt

python fetch.py               # fetch prices once
python app.py                 # start the web server
```

### Routes

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

The postcode prefix and fuel type are set in `fetch.py`.

## Deployment

Running on a DigitalOcean droplet (Ubuntu 24.04, 1 vCPU, 1GB), reached over SSH with key authentication.

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh

git clone https://github.com/Ali00000007/fuel-prices
cd fuel-prices

nano .env                          # credentials, created by hand — never in git
touch fuel.db                      # bind-mount targets must exist first

docker compose up -d --build
docker compose run --rm fetcher    # first run creates the schema
```

An A record points `fuel.solenttransfers.co.uk` at the droplet's IP. Caddy handles TLS — it requests a Let's Encrypt certificate on first start, renews automatically, and redirects HTTP to HTTPS. The certificate is kept in a named volume so restarts do not trigger a re-request, which matters because Let's Encrypt rate-limits.

Only Caddy exposes ports. The Flask service has no `ports:` block at all and is reachable solely through the internal Docker network, so there is no way to bypass TLS.

Scheduling uses cron rather than a long-running container, so the fetcher exists only while it is working:

```
0 7,19 * * * cd /root/fuel-prices && docker compose run --rm fetcher >> /root/fetch.log 2>&1
```

The server runs UTC, so that is 08:00 and 20:00 during BST.

The server holds its own clone of the repo, and pushing from a development machine does not update it. Deploying a change means `git pull` followed by `docker compose up -d --build` on the server.

## How it works

**Finding the API.** The developer portal documents the request format and endpoint paths but never states the host, and the OpenAPI spec has no `servers` block. The base URL was inferred from the pattern of the portal's own sign-out link, which sits at `/onelogin/api/v1/auth/logout` on the service domain, and confirmed by a successful token request.

**Authentication.** A POST to `/api/v1/oauth/generate_access_token` with the client ID and secret as a JSON body returns an access token valid for one hour. The published authentication guidance describes a form-encoded body with a `scope` parameter; the OpenAPI spec, which is correct, specifies JSON with only the two credentials. The token is cached in module-level state alongside its expiry timestamp, and `get_token()` returns the cached value unless it is within 60 seconds of expiring. This matters because a full run makes 30+ requests, and the documentation explicitly asks callers not to request a new token per call.

**Pagination.** Both data endpoints require a `batch-number` query parameter starting at 1. The API signals the end of the data with a `404` rather than an empty response, so the paging loop catches `requests.HTTPError` and breaks. A maximum batch count guards against an infinite loop.

**Joining.** Prices and station details come from separate endpoints — no location data on the price records, no prices on the station records. They share a `node_id`, which is the join key. The current implementation is a nested loop; building a dictionary keyed on `node_id` would reduce this from O(n^2) to O(n) and is the obvious next optimisation.

**Filtering.** Filtering is done on postcode prefix rather than the `city` field. The city data is inconsistent in ways that would silently drop results — values include `EASTLEIGH SOUTHAMPTON`, empty strings, and towns that do not match the station's own address. Postcode prefixes are reliable.

**Timestamps.** Rows are stored as UTC-aware ISO 8601 strings and converted to `Europe/London` for display via a Jinja filter. Storing local time would produce ambiguous data at the BST/GMT transition — an hour that occurs twice in October and one that does not exist in March. It would also mean the same row rendered differently on a UTC server than on a UK laptop, which is a bug this project hit before the timestamps were made timezone-aware. ISO 8601 sorts correctly as text, which is what makes `MAX(recorded_at)` work for finding the latest snapshot.

**Queries.** All parameters are passed using `?` placeholders rather than string formatting, so user-supplied values — including the station name arriving from the web request — can never be interpreted as SQL.

**Containers.** `web` and `fetcher` build from the same Dockerfile and differ only in the `command` they run, so there is one environment definition rather than two to keep in step. `requirements.txt` is copied and installed before the application code so the pip layer stays cached across code changes. The database is bind-mounted rather than copied into the image, since a container's filesystem is discarded when it stops.

## Known limitations

- A full run fetches every UK station and price record, taking around a minute; it cannot run inside a web request
- Every run stores a full set of rows even when no price has changed, so the table grows faster than the information in it
- Postcode prefix is a coarse geographic filter; the API returns latitude and longitude per station, so distance-based filtering would be more accurate
- SQLite is a single local file with no backup; losing the droplet would lose the price history
- Flask's built-in development server is used rather than a production WSGI server
- Containers have no restart policy, so a host reboot requires starting them manually

## Planned

- [ ] Only store a row when the price has changed since the last reading
- [ ] Replace Flask's development server with gunicorn
- [ ] Add restart policies and back up the database off the droplet
- [ ] Replace SQLite with Postgres as a fourth Compose service
- [ ] Distance-based filtering using station coordinates
- [ ] Price history chart

## Data source

Fuel Finder, operated by VE3 Global Ltd on behalf of the Department for Energy Security and Net Zero. Data is published under the Open Government Licence v3.0.