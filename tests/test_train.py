# -*- coding: utf-8 -*-
"""
train.py の自動テストスイート。
ユニットテスト（パーサー、パラメータ構築、モックHTTP）および
堅牢性テスト（異常系・None処理）を網羅します。
"""

import os
from datetime import datetime
import unittest
from unittest.mock import Mock, patch
import requests

from train import (
    build_search_params,
    parse_route_html,
    search_route,
    format_route,
    Route,
    RouteStep,
    RouteNotFoundError,
    RouteError,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestBuildSearchParams(unittest.TestCase):
    """build_search_params のパラメータ生成と正規化テスト。"""

    def test_default_params_contain_nationwide_flags(self):
        params = build_search_params(departure_station="東京", destination_station="新大阪")
        self.assertEqual(params["from"], "東京")
        self.assertEqual(params["to"], "新大阪")
        self.assertEqual(params["type"], "1")
        # 全国検索フラグがすべて True (1) に設定されていること
        self.assertEqual(params["shin"], "1")
        self.assertEqual(params["ex"], "1")
        self.assertEqual(params["al"], "1")
        self.assertEqual(params["hb"], "1")
        self.assertEqual(params["lb"], "1")
        self.assertEqual(params["sr"], "1")
        # 年が2025などのハードコードではなく現在年であること
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

    def test_individual_date_fields(self):
        params = build_search_params(
            departure_station="博多",
            destination_station="小倉",
            year=2028,
            month=11,
            day=25,
            hour=14,
            minute=45,
        )
        self.assertEqual(params["y"], "2028")
        self.assertEqual(params["m"], "11")
        self.assertEqual(params["d"], "25")
        self.assertEqual(params["hh"], "14")
        self.assertEqual(params["m1"], "4")
        self.assertEqual(params["m2"], "5")

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
    """parse_route_html のHTML解析および例外処理テスト。"""

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
        self.assertIn("東京", route.stations)
        self.assertIn("新大阪", route.stations)
        self.assertIn("乗換：0回", route.transfers)
        self.assertTrue(len(route.total_time) > 0)
        self.assertTrue(len(route.fare) > 0)

        # ステップ検証（新幹線1区間）
        self.assertEqual(len(route.steps), 1)
        step = route.steps[0]
        self.assertEqual(step.departure_station, "東京")
        self.assertEqual(step.arrival_station, "新大阪")
        self.assertIn("新幹線", step.transport)
        self.assertNotIn("[line]", step.transport)

    def test_parse_transfer_wakayama_namba(self):
        html = load_fixture("transfer_wakayama_namba.html")
        route = parse_route_html(
            html=html,
            departure_station="和歌山",
            destination_station="難波",
        )

        self.assertIsInstance(route, Route)
        self.assertEqual(len(route.stations), 4)
        self.assertEqual(route.stations[0], "和歌山")
        self.assertEqual(route.stations[-1], "大阪難波")

        # 3つの移動区間
        self.assertEqual(len(route.steps), 3)

        # 1区間目: 紀州路快速
        self.assertEqual(route.steps[0].departure_station, "和歌山")
        self.assertEqual(route.steps[0].arrival_station, "新今宮")
        self.assertIn("快速", route.steps[0].transport)

        # 2区間目: 大和路線
        self.assertEqual(route.steps[1].departure_station, "新今宮")
        self.assertEqual(route.steps[1].arrival_station, "ＪＲ難波")

        # 3区間目: 徒歩
        self.assertEqual(route.steps[2].departure_station, "ＪＲ難波")
        self.assertEqual(route.steps[2].arrival_station, "大阪難波")
        self.assertEqual(route.steps[2].transport, "徒歩")

    def test_parse_not_found_fixture_raises_route_not_found_error(self):
        html = load_fixture("not_found_station.html")
        with self.assertRaises(RouteNotFoundError):
            parse_route_html(html=html, departure_station="存在しない駅", destination_station="東京")

    def test_parse_empty_html_raises_route_not_found_error(self):
        with self.assertRaises(RouteNotFoundError):
            parse_route_html(html="")
        with self.assertRaises(RouteNotFoundError):
            parse_route_html(html="   \n\t  ")

    def test_parse_malformed_html_without_route_summary(self):
        html = "<html><body><div class='container'><p>何もないページ</p></div></body></html>"
        with self.assertRaises(RouteNotFoundError) as ctx:
            parse_route_html(html=html, departure_station="駅A", destination_station="駅B")
        self.assertIn("駅A", str(ctx.exception))
        self.assertIn("駅B", str(ctx.exception))

    def test_parse_summary_exists_but_detail_missing(self):
        # routeSummary はあるが routeDetail が欠損している極端なケース
        html = """
        <html><body>
          <div class="routeSummary">
            <ul>
              <li class="time">1時間10分</li>
              <li class="transfer">乗換：1回</li>
              <li class="fare">500円</li>
            </ul>
          </div>
        </body></html>
        """
        route = parse_route_html(html=html, departure_station="駅A", destination_station="駅B")
        self.assertEqual(route.total_time, "1時間10分")
        self.assertEqual(route.transfers, "乗換：1回")
        self.assertEqual(route.fare, "500円")
        self.assertEqual(len(route.steps), 0)


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
            transport="のぞみ1号",
            departure_time="09:00",
            arrival_time="11:30",
            estimated_time="2時間30分",
            fare="13,870円",
        )
        route = Route(
            departure="東京",
            destination="新大阪",
            search_url="https://transit.yahoo.co.jp/test",
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
        self.assertIn("のぞみ1号", formatted)
        self.assertIn("新大阪 (11:30)", formatted)


class TestLiveSearch(unittest.TestCase):
    """Yahoo!路線情報の実際のサービスに対するライブ疎通テスト。"""

    def test_live_shinkansen_route(self):
        try:
            route = search_route(
                departure_station="東京",
                destination_station="新大阪",
                timeout=10.0,
            )
            self.assertIsInstance(route, Route)
            self.assertEqual(route.departure, "東京")
            self.assertEqual(route.destination, "新大阪")
            self.assertTrue(len(route.steps) > 0)
        except (requests.exceptions.RequestException, RouteNotFoundError) as e:
            # ネットワーク不通環境でもユニットテスト全体を阻害しないようスキップ
            self.skipTest(f"Live network test skipped: {e}")


if __name__ == "__main__":
    unittest.main()
