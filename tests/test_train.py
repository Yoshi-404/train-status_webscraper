# -*- coding: utf-8 -*-
"""
trainstatus 自動テストスイート。
ユニットテスト（パーサー、数値型フィールド、パラメータ構築、モックHTTP）および
堅牢性テスト（異常系・None処理・CI検知）を網羅します。
"""

import os
from datetime import datetime
import unittest
from unittest.mock import Mock, patch
import requests

from trainstatus import (
    build_search_params,
    parse_route_html,
    search_route,
    format_route,
    parse_duration_minutes,
    parse_transfer_count,
    parse_fare_yen,
    Route,
    RouteStep,
    RouteNotFoundError,
    RouteParseError,
    RouteError,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestHelperParsers(unittest.TestCase):
    """数値・型変換ヘルパー関数の単体テスト。"""

    def test_parse_duration_minutes(self):
        self.assertEqual(parse_duration_minutes("2時間30分"), 150)
        self.assertEqual(parse_duration_minutes("45分"), 45)
        self.assertEqual(parse_duration_minutes("1時間"), 60)
        self.assertEqual(parse_duration_minutes("09:00発→11:30着2時間30分(乗車2時間30分)"), 150)
        self.assertIsNone(parse_duration_minutes(""))
        self.assertIsNone(parse_duration_minutes(None))

    def test_parse_transfer_count(self):
        self.assertEqual(parse_transfer_count("乗換：0回"), 0)
        self.assertEqual(parse_transfer_count("乗換：3回"), 3)
        self.assertEqual(parse_transfer_count("なし"), 0)
        self.assertEqual(parse_transfer_count(None), 0)

    def test_parse_fare_yen(self):
        self.assertEqual(parse_fare_yen("13,870円"), 13870)
        self.assertEqual(parse_fare_yen("IC優先：1,120円"), 1120)
        self.assertEqual(parse_fare_yen("490円"), 490)
        self.assertIsNone(parse_fare_yen(""))
        self.assertIsNone(parse_fare_yen(None))


class TestBuildSearchParams(unittest.TestCase):
    """build_search_params のパラメータ生成と正規化テスト。"""

    def test_default_params_contain_nationwide_flags(self):
        params = build_search_params(departure_station="東京", destination_station="新大阪")
        self.assertEqual(params["from"], "東京")
        self.assertEqual(params["to"], "新大阪")
        self.assertEqual(params["type"], "1")
        self.assertEqual(params["shin"], "1")
        self.assertEqual(params["ex"], "1")
        self.assertEqual(params["al"], "1")
        self.assertEqual(params["hb"], "1")
        self.assertEqual(params["lb"], "1")
        self.assertEqual(params["sr"], "1")
        self.assertEqual(params["y"], str(datetime.now().year))

    def test_custom_datetime_formatting(self):
        dt = datetime(2027, 4, 5, 8, 9)
        params = build_search_params(
            departure_station=" 札幌 ",
            destination_station=" 函館 ",
            search_type=4,
            date=dt,
        )
        self.assertEqual(params["from"], "札幌")
        self.assertEqual(params["to"], "函館")
        self.assertEqual(params["type"], "4")
        self.assertEqual(params["y"], "2027")
        self.assertEqual(params["m"], "04")
        self.assertEqual(params["d"], "05")
        self.assertEqual(params["hh"], "08")
        self.assertEqual(params["m1"], "0")
        self.assertEqual(params["m2"], "9")

    def test_disabled_transport_options(self):
        params = build_search_params(
            departure_station="東京",
            destination_station="新大阪",
            include_shinkansen=False,
            include_airplane=False,
            include_express=False,
        )
        self.assertEqual(params["shin"], "0")
        self.assertEqual(params["al"], "0")
        self.assertEqual(params["ex"], "0")
        self.assertEqual(params["hb"], "1")


class TestParseRouteHtml(unittest.TestCase):
    """parse_route_html の解析精度、型付きフィールド、プラットフォーム分離のテスト。"""

    def test_parse_shinkansen_tokyo_osaka(self):
        html = load_fixture("shinkansen_tokyo_osaka.html")
        route = parse_route_html(
            html=html,
            departure_station="東京",
            destination_station="新大阪",
            search_url="https://transit.yahoo.co.jp/search/print?mock=1",
        )

        self.assertIsInstance(route, Route)
        self.assertEqual(route.departure, "東京")
        self.assertEqual(route.destination, "新大阪")

        # 数値型フィールドの検証
        self.assertEqual(route.duration_minutes, 150)
        self.assertEqual(route.transfer_count, 0)
        self.assertEqual(route.fare_yen, 13870)
        self.assertEqual(route.departure_time, "12:24")
        self.assertEqual(route.arrival_time, "14:54")

        # 1区間のみ（新幹線）
        self.assertEqual(len(route.steps), 1)
        step = route.steps[0]
        self.assertEqual(step.departure_station, "東京")
        self.assertEqual(step.arrival_station, "新大阪")

        # プラットフォーム情報が路線名から分離されていること
        self.assertEqual(step.departure_platform, "17番線")
        self.assertEqual(step.arrival_platform, "23番線")
        self.assertNotIn("[発]", step.transport)
        self.assertNotIn("[着]", step.transport)
        self.assertEqual(step.transport, "ＪＲ新幹線のぞみ393号(当駅始発)新大阪行")

        # 所要時間・運賃が適切に計算されていること
        self.assertEqual(step.duration_minutes, 150)
        self.assertEqual(step.estimated_time, "2時間30分")
        self.assertEqual(step.fare_yen, 13870)
        self.assertIn("13,870円", step.fare)
        self.assertIn("乗車券：8,910円", step.fare)
        self.assertIn("自由席：4,960円", step.fare)

    def test_parse_transfer_wakayama_namba(self):
        html = load_fixture("transfer_wakayama_namba.html")
        route = parse_route_html(
            html=html,
            departure_station="和歌山",
            destination_station="難波",
        )

        self.assertIsInstance(route, Route)
        self.assertEqual(len(route.stations), 4)
        self.assertEqual(len(route.steps), 3)

        # ステップ 0: 和歌山 -> 新今宮
        step0 = route.steps[0]
        self.assertEqual(step0.departure_station, "和歌山")
        self.assertEqual(step0.arrival_station, "新今宮")
        self.assertEqual(step0.departure_time, "12:30")
        self.assertEqual(step0.arrival_time, "13:43")
        self.assertEqual(step0.duration_minutes, 73)
        self.assertEqual(step0.estimated_time, "1時間13分")
        self.assertEqual(step0.stops, "17駅")
        self.assertEqual(step0.departure_platform, "3番線")
        self.assertEqual(step0.arrival_platform, "3・4番線")
        self.assertNotIn("[発]", step0.transport)

        # ステップ 1: 新今宮 -> ＪＲ難波
        step1 = route.steps[1]
        self.assertEqual(step1.departure_station, "新今宮")
        self.assertEqual(step1.arrival_station, "ＪＲ難波")
        self.assertEqual(step1.departure_time, "13:46")
        self.assertEqual(step1.arrival_time, "13:50")
        self.assertEqual(step1.duration_minutes, 4)
        self.assertEqual(step1.estimated_time, "4分")
        self.assertEqual(step1.stops, "2駅")
        self.assertEqual(step1.departure_platform, "3番線")
        # 「情報なし」は空文字に正規化されていること
        self.assertEqual(step1.arrival_platform, "")
        self.assertNotIn("[着] 情報なし", step1.transport)

        # ステップ 2: ＪＲ難波 -> 大阪難波 (徒歩)
        step2 = route.steps[2]
        self.assertEqual(step2.departure_station, "ＪＲ難波")
        self.assertEqual(step2.arrival_station, "大阪難波")
        self.assertEqual(step2.transport, "徒歩")
        self.assertEqual(step2.departure_time, "13:52")
        self.assertEqual(step2.arrival_time, "13:57")
        self.assertEqual(step2.duration_minutes, 5)
        self.assertEqual(step2.estimated_time, "5分")

        # 複数区間で共有された通算運賃は各ステップで重複させず、Routeにのみ集約されていること
        self.assertEqual(route.fare_yen, 1120)
        self.assertIn("1,120円", route.fare)
        self.assertEqual(step0.fare, "")
        self.assertIsNone(step0.fare_yen)
        self.assertEqual(step1.fare, "")
        self.assertIsNone(step1.fare_yen)
        self.assertEqual(step2.fare, "")
        self.assertIsNone(step2.fare_yen)

    def test_parse_not_found_raises_route_not_found_error(self):
        html = load_fixture("not_found_station.html")
        with self.assertRaises(RouteNotFoundError):
            parse_route_html(html=html, departure_station="存在しない駅", destination_station="東京")

    def test_parse_empty_html_raises_route_not_found_error(self):
        with self.assertRaises(RouteNotFoundError):
            parse_route_html(html="")
        with self.assertRaises(RouteNotFoundError):
            parse_route_html(html="   \n\t  ")

    def test_parse_structural_inconsistency_raises_route_parse_error(self):
        # 駅数(1)に対してアクセス数(2)がある破損した構造
        html = """
        <html><body>
          <div class="routeSummary">
            <ul><li class="time">1時間</li></ul>
          </div>
          <div class="routeDetail">
            <div class="station"><dt>駅1</dt></div>
            <div class="access"><div>アクセス1</div></div>
            <div class="access"><div>アクセス2</div></div>
          </div>
        </body></html>
        """
        with self.assertRaises(RouteParseError):
            parse_route_html(html=html, departure_station="駅1", destination_station="駅2")


class TestSearchRoute(unittest.TestCase):
    """search_route 関数のネットワークモックとエラーハンドリングテスト。"""

    @patch("requests.get")
    def test_search_route_success(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = load_fixture("shinkansen_tokyo_osaka.html")
        mock_resp.url = "https://transit.yahoo.co.jp/search/print?from=東京&to=新大阪"
        mock_get.return_value = mock_resp

        route = search_route(departure_station="東京", destination_station="新大阪")
        self.assertIsInstance(route, Route)
        self.assertEqual(route.departure, "東京")
        self.assertEqual(route.destination, "新大阪")
        self.assertEqual(route.duration_minutes, 150)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_search_route_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        with self.assertRaises(requests.exceptions.Timeout):
            search_route(departure_station="東京", destination_station="新大阪")

    @patch("requests.get")
    def test_search_route_http_error(self, mock_get):
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_resp
        with self.assertRaises(requests.exceptions.HTTPError):
            search_route(departure_station="東京", destination_station="新大阪")


class TestFormatRoute(unittest.TestCase):
    """format_route 関数の出力文字列フォーマットテスト。"""

    def test_format_complete_route(self):
        step = RouteStep(
            departure_station="東京",
            arrival_station="新大阪",
            transport="ＪＲ新幹線のぞみ",
            departure_time="09:00",
            arrival_time="11:30",
            duration_minutes=150,
            estimated_time="2時間30分",
            fare="13,870円",
            stops="5駅",
            departure_platform="17番線",
            arrival_platform="23番線",
        )
        route = Route(
            departure="東京",
            destination="新大阪",
            search_url="https://transit.yahoo.co.jp/test",
            duration_minutes=150,
            transfer_count=0,
            fare_yen=13870,
            total_time="2時間30分",
            transfers="乗換：0回",
            fare="13,870円",
            steps=[step],
            stations=["東京", "新大阪"],
        )

        formatted = format_route(route)
        self.assertIn("東京 から 新大阪", formatted)
        self.assertIn("所要時間：2時間30分", formatted)
        self.assertIn("乗換：0回", formatted)
        self.assertIn("料金：13,870円", formatted)
        self.assertIn("東京 (09:00)", formatted)
        self.assertIn("ＪＲ新幹線のぞみ", formatted)
        self.assertIn("[発] 17番線 → [着] 23番線", formatted)
        self.assertIn("新大阪 (11:30)", formatted)


@unittest.skipUnless(
    os.environ.get("LIVE_TESTS") == "1",
    "Live tests disabled by default. Set LIVE_TESTS=1 to run against Yahoo! Transit.",
)
class TestLiveSearch(unittest.TestCase):
    """
    Yahoo!路線情報の実際のサービスに対するライブ疎通テスト。
    ネットワーク通信失敗時のみ skipTest とし、HTML変更によるパース失敗時はテストを落とす。
    """

    def test_live_shinkansen_route(self):
        try:
            route = search_route(
                departure_station="東京",
                destination_station="新大阪",
                timeout=10.0,
            )
        except requests.exceptions.RequestException as e:
            # ネットワーク接続障害・タイムアウト時のみスキップ
            self.skipTest(f"Live network test skipped due to network error: {e}")

        # ネットワークが200 OKを返した場合は、必ず正しいRouteが抽出できていること
        self.assertIsInstance(route, Route)
        self.assertEqual(route.departure, "東京")
        self.assertEqual(route.destination, "新大阪")
        self.assertGreater(len(route.steps), 0)
        self.assertIsNotNone(route.duration_minutes)
        self.assertIsNotNone(route.fare_yen)


if __name__ == "__main__":
    unittest.main()
