# Transit Route Search CLI 🚉

A Python command-line script that fetches transit route info (travel time, transfer count, fare, and step-by-step transfer details) from Yahoo! Transit (Japan).

[日本語版 README はこちら](./README.md)

## Features

- Interactively prompts for a departure station and destination station
- Lets you choose between "depart-by" and "arrive-by" search types
- Lets you search using today's date/time or a custom date and time
- Prints the following for the resulting route:
  - Total travel time
  - Number of transfers
  - Fare
  - Station name, line name, travel time, and segment fare for each leg

## Requirements

- Python 3.9+

### Dependencies

```
requests
beautifulsoup4
```

Install with:

```bash
pip install requests beautifulsoup4
```

## Usage

```bash
python train.py
```

Running the script will prompt you for the following, in order:

1. **出発駅を入力してください：** (Departure station) e.g. Wakayama
2. **到着駅を入力してください：** (Destination station) e.g. Namba
3. **出発時間で検索するなら1、到着時間で検索するなら4を入力してください：** (Enter `1` to search by departure time, `4` to search by arrival time)
4. **日付を今日にするなら 1、自分で指定するなら 2 を入力してください：** (Enter `1` to use today's date, `2` to specify a custom date)
   - If you choose `2`, you'll also be asked for month and day
5. **時（0-23）：** / **分（0-59）：** (Hour / minute)

Once all inputs are provided, the script prints the search URL it built and then the route details.

### Example output

```
検索URL： https://transit.yahoo.co.jp/search/print?from=和歌山&to=難波&type=1&y=2025&m=04&d=10&hh=08&m1=0&m2=0
====== 和歌山 から 難波 ======
所要時間：1時間5分
乗換：1回
料金：970円
======乗り換え情報======
和歌山
 | JR阪和線 45分 650円
天王寺
 | 南海本線 20分 320円
難波
```

(All prompt and output text is in Japanese, since the source data is Yahoo! Japan's transit site.)

## Notes / Limitations

- The script scrapes Yahoo! Transit's HTML structure, so it may break if the site changes its layout.
- The search year (`year`) is hardcoded to `2025` and must be updated manually for future years.
- Station names must match Yahoo! Transit's naming; typos or ambiguous/duplicate station names can return unexpected routes.
- There is no error handling for network failures, timeouts, or missing HTML elements — the script will raise an exception if the request fails or the page structure differs from what's expected.

## License

No license specified. Add one if you plan to share or open-source this project.
