# Transit Route Search CLI & Python Library 🚉 (trainstatus v0.1.0)

[![CI](https://github.com/Yoshi-404/train-status_webscraper/actions/workflows/ci.yml/badge.svg)](https://github.com/Yoshi-404/train-status_webscraper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A Python command-line tool and library for querying transit routes (travel times, transfer counts, fares, and step-by-step leg details) from Yahoo! Transit (Japan). Supports nationwide searches across Japan including Shinkansen bullet trains, limited express trains, highway buses, and domestic flights.

[日本語版 README はこちら](README.md)

---

## Key Features

- **Nationwide Route Search**: Search routes across all of Japan, taking advantage of Shinkansen, limited express trains, highway buses, local buses, and flights.
- **Typed & Structured Data**:
  - `duration_minutes: int` (e.g. `150`)
  - `transfer_count: int` (e.g. `0`)
  - `fare_yen: int` (e.g. `13870`)
  - `departure_time` / `arrival_time` (e.g. `"09:00"`, `"11:30"`)
  - Preserves original raw strings for human display
- **Clean Transport Names & Dedicated Platform Fields**:
  - Automatically strips platform metadata (`[発] 17番線 → [着] 23番線`) from the train/line name and isolates them in `departure_platform` and `arrival_platform`.
- **Calculated Leg Durations**:
  - Auto-calculates duration per leg from station departure and arrival timestamps (`duration_minutes` and `estimated_time`).
- **Professional Package Layout (`src/trainstatus`)**: Avoids polluting the global Python module namespace while preserving complete backward compatibility with `python train.py`.
- **Robust Error Handling**:
  - Configurable timeouts (default: 10s)
  - HTTP status validation with `response.raise_for_status()`
  - Explicit `RouteNotFoundError` and `RouteParseError` exceptions
  - Defensive `None` checks across all parsed HTML elements

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

After installing via pip, run `train-search` or execute the script directly:

```bash
# After pip install:
train-search

# Or run directly from repo root:
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
 | ＪＲ新幹線のぞみ135号(当駅始発)新大阪行 [2時間30分 / 5駅 / [発] 15番線 → [着] 21番線 / 13,870円 (乗車券：8,910円 + 自由席：4,960円)]
新大阪 (11:30)
```

---

### 2. Usage as a Python Library

Import `search_route` directly into your own applications, bots, or automation workflows:

```python
from trainstatus import search_route, RouteNotFoundError

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

    print(f"Route: {route.departure} -> {route.destination}")
    print(f"Duration: {route.duration_minutes} minutes (raw: {route.total_time})")
    print(f"Transfers: {route.transfer_count}")
    print(f"Fare: {route.fare_yen} JPY (raw: {route.fare})")
    print(f"Schedule: {route.departure_time} -> {route.arrival_time}")

    print("\n--- Route Legs ---")
    for step in route.steps:
        print(f"[{step.departure_station} ({step.departure_time})] -> [{step.arrival_station} ({step.arrival_time})]")
        print(f"  Transport: {step.transport}")
        if step.duration_minutes is not None:
            print(f"  Duration: {step.duration_minutes} min ({step.estimated_time})")
        if step.departure_platform or step.arrival_platform:
            print(f"  Platform: [Dep] {step.departure_platform or '-'} -> [Arr] {step.arrival_platform or '-'}")
        if step.fare_yen is not None:
            print(f"  Fare: {step.fare_yen} JPY ({step.fare})")

except RouteNotFoundError as e:
    print(f"⚠️ Route not found: {e}")
except Exception as e:
    print(f"⚠️ Error: {e}")
```

#### Available Data Structures (`Route` / `RouteStep`)

- **`Route`**
  - `departure`: Departure station (`str`)
  - `destination`: Destination station (`str`)
  - `duration_minutes`: Total journey duration in minutes (`Optional[int]`)
  - `transfer_count`: Total number of transfers (`int`)
  - `fare_yen`: Total fare in Yen (`Optional[int]`)
  - `departure_time`: Formatted departure time (`Optional[str]`, e.g. `"09:00"`)
  - `arrival_time`: Formatted arrival time (`Optional[str]`, e.g. `"11:30"`)
  - `total_time`: Raw summary text (`str`)
  - `transfers`: Raw transfer text (`str`)
  - `fare`: Raw fare text (`str`)
  - `steps`: List of leg segments (`List[RouteStep]`)
  - `stations`: List of all station names visited (`List[str]`)
  - `search_url`: Raw Yahoo! Transit search URL (`str`)

- **`RouteStep`**
  - `departure_station`: Leg departure station (`str`)
  - `arrival_station`: Leg arrival station (`str`)
  - `transport`: Clean line name / train name (`str`, platform info excluded)
  - `departure_time`: Departure timestamp (`str`)
  - `arrival_time`: Arrival timestamp (`str`)
  - `duration_minutes`: Duration in minutes for this leg (`Optional[int]`)
  - `estimated_time`: Formatted duration (`str`, e.g. `"2時間30分"`, `"4分"`)
  - `fare`: Leg fare string (`str`)
  - `fare_yen`: Leg fare integer in Yen (`Optional[int]`)
  - `stops`: Intermediate stop count string (`str`, e.g. `"5駅"`)
  - `departure_platform`: Departure platform / track (`str`, e.g. `"17番線"`)
  - `arrival_platform`: Arrival platform / track (`str`, e.g. `"23番線"`)

---

## 3. Running Tests

### Offline Unit Tests (Executed automatically in CI)
Uses lightweight offline HTML fixtures and mocks, executing deterministically in milliseconds without external network dependencies:

```bash
python -m unittest discover tests -v
```

### Live Network Test (Yahoo! Transit)
To test connectivity against the live Yahoo! Transit site and catch upstream HTML layout changes (monitored automatically via weekly GitHub Actions):

```bash
LIVE_TESTS=1 python -m unittest discover tests -v
```

---

## ⚠️ Disclaimer & Terms of Use

- This project is an open-source tool created strictly for personal and educational use.
- Please comply with the Terms of Service of [Yahoo! Transit (Yahoo! JAPAN)](https://transit.yahoo.co.jp/) and the respective data providers.
- Avoid making automated or high-frequency requests that could cause an unnecessary load on Yahoo! JAPAN servers.

---

## License

This project is licensed under the [MIT License](LICENSE).
