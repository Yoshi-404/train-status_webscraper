# 路線検索CLI / Pythonライブラリ 🚉 (v0.1.0)

Yahoo!路線情報から乗換案内（所要時間・乗換回数・料金・乗換詳細）を取得するPythonスクリプトおよびライブラリです。新幹線・特急・高速バス・飛行機など日本全国の経路検索に対応しています。

[English README is here](README_EN.md)

---

## 主な特徴

- **日本全国の経路検索に対応**: 新幹線・特急・飛行機・高速バスなどの交通機関を網羅した経路検索が可能
- **ライブラリ & CLIの両対応**:
  - PythonスクリプトやWebアプリ、Botなどから `search_route()` で `Route` データクラスとして利用可能
  - ターミナルから対話形式ですぐに使えるコマンドラインツール（`train-search` または `python train.py`）
- **動的な現在日時対応**: 年（`year`）のハードコードを撤廃し、実行時の現在年・現在時刻を自動取得
- **安全なURLクエリ構築**: 手動の文字列連結をやめ、`requests` の `params` による安全なURLエンコーディングを採用
- **堅牢なエラーハンドリング & パーサー**:
  - HTTPタイムアウト（デフォルト10秒）
  - `raise_for_status()` による通信ステータス検査
  - 駅名誤りや経路未検出時の `RouteNotFoundError` 例外処理
  - HTML構造変更や欠損データに対する完全な `None` 安全処理

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

# または直接実行
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
 | ＪＲ新幹線のぞみ135号(当駅始発)博多行[発] 15番線 → [着] 21番線 [2時間30分 / 5駅 / 自由席：4,960円 / 8,910円]
新大阪 (11:30)
```

---

### 2. Pythonライブラリとしての利用

自作のBot、Webアプリ、バッチスクリプトなどから直接インポートして利用できます。

```python
from train import search_route, RouteNotFoundError

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

    print(f"出発: {route.departure} -> 到着: {route.destination}")
    print(f"所要時間: {route.total_time}")
    print(f"乗換回数: {route.transfers}")
    print(f"総料金: {route.fare}")
    print(f"検索URL: {route.search_url}")

    print("\n--- 各区間の詳細 ---")
    for step in route.steps:
        print(f"[{step.departure_station} ({step.departure_time})] -> [{step.arrival_station} ({step.arrival_time})]")
        print(f"  利用路線: {step.transport}")
        if step.stops:
            print(f"  停車駅数: {step.stops}")
        if step.fare:
            print(f"  区間料金: {step.fare}")

except RouteNotFoundError as e:
    print(f"⚠️ ルートが見つかりませんでした: {e}")
except Exception as e:
    print(f"⚠️ エラーが発生しました: {e}")
```

#### 利用可能なデータ構造 (`Route` / `RouteStep`)

- **`Route`**
  - `departure`: 出発駅
  - `destination`: 到着駅
  - `search_url`: Yahoo!路線情報の検索URL
  - `total_time`: 総所要時間
  - `transfers`: 乗換回数
  - `fare`: 総料金
  - `steps`: 区間詳細リスト (`List[RouteStep]`)
  - `stations`: 経由駅名リスト (`List[str]`)

- **`RouteStep`**
  - `departure_station`: 区間の出発駅
  - `arrival_station`: 区間の到着駅
  - `transport`: 路線名・種別（例: `ＪＲ新幹線...` や `徒歩`）
  - `departure_time`: 出発時刻
  - `arrival_time`: 到着時刻
  - `estimated_time`: 区間所要時間
  - `fare`: 区間料金
  - `stops`: 停車駅数
  - `departure_platform`: 発車番線
  - `arrival_platform`: 到着番線

---

## 3. テストの実行

包括的なユニットテストおよびモック通信テストが含まれています：

```bash
python -m unittest discover tests -v
```

---

## ライセンス

本プロジェクトは [MIT License](LICENSE) のもとで公開されています。
