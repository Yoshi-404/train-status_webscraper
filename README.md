# 路線検索CLI / Pythonライブラリ 🚉 (trainstatus v0.1.0)

[![CI](https://github.com/Yoshi-404/train-status_webscraper/actions/workflows/ci.yml/badge.svg)](https://github.com/Yoshi-404/train-status_webscraper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Yahoo!路線情報から乗換案内（所要時間・乗換回数・料金・乗換詳細）を取得するPythonライブラリおよびCLIツールです。新幹線・特急・高速バス・飛行機など日本全国の経路検索に対応しています。

[English README is here](README_EN.md)

---

## 主な特徴

- **日本全国の経路検索に対応**: 新幹線・特急・飛行機・高速バスなどの全国交通機関を網羅した経路検索が可能
- **型付き構造化データ**:
  - `duration_minutes: int`（所要分数、例: `150`）
  - `transfer_count: int`（乗換回数、例: `0`）
  - `fare_yen: int`（運賃数値、例: `13870`）
  - `departure_time` / `arrival_time`（発着時刻、例: `"09:00"`, `"11:30"`）
  - 整形前のオリジナルテキストも保持
- **クリーンな路線名 & プラットフォーム分離**:
  - 路線名から `[発] 17番線 → [着] 23番線` などのプラットフォーム表記を除去し、`departure_platform` と `arrival_platform` に個別格納
- **計算された各区間の所要時間**: 各区間の発着時刻差分から `duration_minutes` および `estimated_time`（例: `"2時間30分"`）を自動計算
- **安全なパッケージ構造 (`src/trainstatus`)**: グローバル名前空間を汚染しないプロフェッショナルな設計（従来の `python train.py` 実行との完全な後方互換性も維持）
- **堅牢なエラーハンドリング**:
  - ネットワークタイムアウト（デフォルト10秒）
  - `raise_for_status()` によるHTTPステータス検査
  - 経路未検出時の `RouteNotFoundError` 例外処理
  - ページ構造破損時の `RouteParseError` 例外処理
  - HTML欠損データに対する完全な `None` 安全処理

---

## インストール方法

### GitHubから直接インストール (推奨)

```bash
pip install git+https://github.com/Yoshi-404/train-status_webscraper.git
```

### ローカル環境での開発インストール

```bash
git clone https://github.com/Yoshi-404/train-status_webscraper.git
cd train-status_webscraper
pip install -e .
```

---

## 使い方

### 1. コマンドライン (CLI) での利用

pipでインストール後、ターミナルで `train-search` コマンドを実行するか、スクリプトを直接実行します：

```bash
# pipインストール後
train-search

# または直接実行（リポジトリ直下）
python train.py
```

実行すると、対話形式で条件を入力できます（Enterキーのみで現在時刻やデフォルト値が適用されます）：

1. **出発駅を入力してください：** 例）東京
2. **到着駅を入力してください：** 例）新大阪
3. **出発時間で検索するなら1、到着時間で検索するなら4を入力してください [デフォルト: 1]：**
4. **日付を今日にするなら 1、自分で指定するなら 2 を入力してください [デフォルト: 1]：**
   - `2` を選んだ場合、年・月・日を追加で入力
5. **時（0-23） / 分（0-59）：**

#### 出力例

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

### 2. Pythonライブラリとしての利用

BotやWebアプリ、スクリプト等から直接インポートして利用できます。

```python
from trainstatus import search_route, RouteNotFoundError

try:
    # 全国検索（新幹線・特急等を含む）
    route = search_route(
        departure_station="東京",
        destination_station="新大阪",
        search_type=1,           # 1: 出発時刻基準, 4: 到着時刻基準
        include_shinkansen=True, # 新幹線利用 (デフォルト: True)
        include_express=True,    # 有料特急利用 (デフォルト: True)
        include_airplane=True,   # 飛行機利用 (デフォルト: True)
        timeout=10.0             # タイムアウト秒数
    )

    print(f"経路: {route.departure} -> {route.destination}")
    print(f"所要分数: {route.duration_minutes} 分 (文字列: {route.total_time})")
    print(f"乗換回数: {route.transfer_count} 回")
    print(f"総運賃: {route.fare_yen} 円 (文字列: {route.fare})")
    print(f"発着時刻: {route.departure_time} 発 -> {route.arrival_time} 着")

    print("\n--- 各区間の詳細 ---")
    for step in route.steps:
        print(f"[{step.departure_station} ({step.departure_time})] -> [{step.arrival_station} ({step.arrival_time})]")
        print(f"  路線名: {step.transport}")
        if step.duration_minutes is not None:
            print(f"  区間所要時間: {step.duration_minutes} 分 ({step.estimated_time})")
        if step.departure_platform or step.arrival_platform:
            print(f"  番線: [発] {step.departure_platform or '-'} -> [着] {step.arrival_platform or '-'}")
        if step.fare_yen is not None:
            print(f"  区間運賃: {step.fare_yen} 円 ({step.fare})")

except RouteNotFoundError as e:
    print(f"⚠️ ルートが見つかりませんでした: {e}")
except Exception as e:
    print(f"⚠️ エラーが発生しました: {e}")
```

#### 利用可能なデータ構造 (`Route` / `RouteStep`)

- **`Route`**
  - `departure`: 出発駅名 (`str`)
  - `destination`: 到着駅名 (`str`)
  - `duration_minutes`: 総所要分数 (`Optional[int]`)
  - `transfer_count`: 乗換回数 (`int`)
  - `fare_yen`: 総運賃数値 (`Optional[int]`)
  - `departure_time`: 出発時刻 (`Optional[str]`, 例: `"09:00"`)
  - `arrival_time`: 到着時刻 (`Optional[str]`, 例: `"11:30"`)
  - `total_time`: サマリーテキスト (`str`)
  - `transfers`: 乗換サマリーテキスト (`str`)
  - `fare`: 運賃サマリーテキスト (`str`)
  - `steps`: 区間詳細リスト (`List[RouteStep]`)
  - `stations`: 経由駅名リスト (`List[str]`)
  - `search_url`: Yahoo!路線情報の検索URL (`str`)

- **`RouteStep`**
  - `departure_station`: 出発駅 (`str`)
  - `arrival_station`: 到着駅 (`str`)
  - `transport`: クリーンな路線・種別名 (`str`, プラットフォーム情報は含みません)
  - `departure_time`: 出発時刻 (`str`)
  - `arrival_time`: 到着時刻 (`str`)
  - `duration_minutes`: 区間所要分数 (`Optional[int]`)
  - `estimated_time`: 区間所要時間文字列 (`str`, 例: `"2時間30分"`, `"4分"`)
  - `fare`: 区間運賃文字列 (`str`)
  - `fare_yen`: 区間運賃数値 (`Optional[int]`)
  - `stops`: 停車駅数 (`str`, 例: `"5駅"`)
  - `departure_platform`: 発車番線 (`str`, 例: `"17番線"`)
  - `arrival_platform`: 到着番線 (`str`, 例: `"23番線"`)

---

## 3. テストの実行

### オフライン単体テスト (CIで自動実行)
軽量化されたHTMLフィクスチャおよびモックを使用するため、高速（数ミリ秒）かつ外部要因に左右されず確実に実行されます：

```bash
python -m unittest discover tests -v
```

### Yahoo!路線情報へのライブ疎通テスト
実サービスとの疎通およびレイアウト変更を検証する場合（GitHub Actionsの週次ワークフローでも自動監視）：

```bash
LIVE_TESTS=1 python -m unittest discover tests -v
```

---

## ⚠️ 免責事項・利用上の注意

- 本プロジェクトは個人利用および学習・研究目的で作成されたオープンソースツールです。
- データ取得元である [Yahoo!路線情報](https://transit.yahoo.co.jp/) の利用規約および各鉄道・交通事業者の利用ガイドラインを遵守してください。
- サーバーに過度な負荷をかける短時間での連続アクセスやスクレイピング行為は絶対に行わないでください。

---

## ライセンス

本プロジェクトは [MIT License](LICENSE) のもとで公開されています。
