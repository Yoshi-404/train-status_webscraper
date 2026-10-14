# Transit Route Search CLI & Python Library 🚉 (v0.1.0)

A Python command-line tool and library for fetching transit route info (travel time, transfer count, fare, and step-by-step transfer details) from Yahoo! Transit (Japan). Supports nationwide searches across Japan including Shinkansen bullet trains, limited express trains, highway buses, and domestic flights.

[日本語版 README はこちら](README.md)

---

## Key Features

- **Nationwide Route Search**: Search routes across all of Japan, taking advantage of Shinkansen, limited express trains, highway buses, local buses, and flights.
- **Both Library & CLI Support**:
  - Use programmatically via `search_route()` to receive a structured `Route` dataclass in your bots, apps, or scripts.
  - Interactive terminal tool (`train-search` or `python train.py`).
- **Dynamic Date & Time**: Removed hardcoded year (`2025`); automatically uses the current year and time.
- **Safe Query Construction**: Built with `requests` parameter dictionaries (`params=`) for proper, automatic URL encoding.
- **Robust Error Handling & HTML Parser**:
  - Request timeouts (default: 10s)
  - HTTP status validation with `response.raise_for_status()`
  - Explicit `RouteNotFoundError` exception when station names are invalid or no routes are found
  - Defensive `None` checking for all parsed HTML elements

---

## Installation

### Install Directly via GitHub (Recommended)

```bash
pip install git+https://github.com/Yoshi-404/train-status_webscraper.git
```

### Local Development Installation

```bash
git clone https://github.com/Yoshi-404/train-status_webscraper.git
cd train-status_webscraper
pip install -e .
```

---

## Usage

### 1. Interactive CLI Mode

After installing via pip, you can run the CLI command `train-search` or execute the script directly:

```bash
# After pip install:
train-search

# Or run directly:
python train.py
```

Prompts you interactively for search criteria (pressing Enter accepts defaults):

1. **Departure station (出発駅):** e.g., Tokyo (東京)
2. **Destination station (到着駅):** e.g., Shin-Osaka (新大阪)
3. **Search type (出発時間 / 到着時間):** Enter `1` for departure time, `4` for arrival time [Default: 1]
4. **Date option:** Enter `1` for today, `2` for custom date [Default: 1]
   - If `2`, prompts for year, month, and day
5. **Time:** Hour (0-23) and Minute (0-59)

#### Example Output

```text
検索URL： https://transit.yahoo.co.jp/search/print?from=東京&to=新大阪&type=1&y=2026&m=10&d=14&hh=09&m1=0&m2=0&shin=1&ex=1&al=1&hb=1&lb=1&sr=1
====== 東京 から 新大阪 ======
所要時間：09:00発→11:30着2時間30分(乗車2時間30分)
乗換：0回
料金：IC優先：13,870円（乗車券8,910円　特別料金4,960円）
======乗り換え情報======
東京 (09:00)
 | ＪＲ新幹線のぞみ135号(当駅始発)博多行[発] 15番線 → [着] 21番線 [2時間30分 / 5駅 / 自由席：4,960円 / 8,910円]
新大阪 (11:30)
```

---

### 2. Usage as a Python Library

Import `search_route` directly into your own applications, bots, or automation workflows:

```python
from train import search_route, RouteNotFoundError

try:
    # Nationwide search including Shinkansen
    route = search_route(
        departure_station="東京",
        destination_station="新大阪",
        search_type=1,           # 1: depart by, 4: arrive by
        include_shinkansen=True, # Enable Shinkansen bullet trains (default: True)
        include_express=True,    # Enable limited express (default: True)
        include_airplane=True,   # Enable flights (default: True)
        timeout=10.0             # Timeout in seconds
    )

    print(f"From: {route.departure} -> To: {route.destination}")
    print(f"Total Time: {route.total_time}")
    print(f"Transfers: {route.transfers}")
    print(f"Total Fare: {route.fare}")
    print(f"Search URL: {route.search_url}")

    print("\n--- Route Legs ---")
    for step in route.steps:
        print(f"[{step.departure_station} ({step.departure_time})] -> [{step.arrival_station} ({step.arrival_time})]")
        print(f"  Transport: {step.transport}")
        if step.stops:
            print(f"  Stops: {step.stops}")
        if step.fare:
            print(f"  Fare: {step.fare}")

except RouteNotFoundError as e:
    print(f"⚠️ Route not found: {e}")
except Exception as e:
    print(f"⚠️ Unexpected error: {e}")
```

#### Available Data Structures (`Route` / `RouteStep`)

- **`Route`**
  - `departure`: Departure station
  - `destination`: Destination station
  - `search_url`: Raw Yahoo! Transit search URL
  - `total_time`: Total travel time string
  - `transfers`: Number of transfers
  - `fare`: Total calculated fare
  - `steps`: List of travel segments (`List[RouteStep]`)
  - `stations`: List of all station names visited (`List[str]`)

- **`RouteStep`**
  - `departure_station`: Departure station for this leg
  - `arrival_station`: Arrival station for this leg
  - `transport`: Train/bus line name or `徒歩` (walking)
  - `departure_time`: Departure timestamp
  - `arrival_time`: Arrival timestamp
  - `estimated_time`: Segment travel duration
  - `fare`: Segment fare
  - `stops`: Number of intermediate stops
  - `departure_platform`: Departure track / platform number
  - `arrival_platform`: Arrival track / platform number

---

## 3. Running Tests

The project includes unit tests with offline HTML fixtures and network mocks:

```bash
python -m unittest discover tests -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).
