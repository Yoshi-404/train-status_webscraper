# -*- coding: utf-8 -*-
"""
Yahoo!路線情報 (Yahoo! Transit Japan) から乗換案内を取得するスクリプト。
日本全国（新幹線・特急・高速バス・飛行機等）の検索、堅牢なHTMLパーサー、
データクラスによる構造化データ返却、および再利用可能な関数群を提供します。
"""

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import List, Optional
import requests
from bs4 import BeautifulSoup

__version__ = "0.1.0"

BASE_SEARCH_URL = "https://transit.yahoo.co.jp/search/print"
DEFAULT_TIMEOUT = 10.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class RouteError(Exception):
    """ルート検索全般のエラー基本クラス。"""
    pass


class RouteNotFoundError(RouteError):
    """指定された駅や日時のルートが見つからなかった場合に発生する例外。"""
    pass


class RouteParseError(RouteError):
    """HTMLパース処理中に予期せぬデータ構造に遭遇した場合の例外。"""
    pass


@dataclass
class RouteStep:
    """経路内の1区間（移動ステップ）の情報を保持するデータクラス。"""
    departure_station: str
    arrival_station: str
    transport: str
    departure_time: str = ""
    arrival_time: str = ""
    estimated_time: str = ""
    fare: str = ""
    stops: str = ""
    departure_platform: str = ""
    arrival_platform: str = ""


@dataclass
class Route:
    """検索された全体の経路情報を保持するデータクラス。"""
    departure: str
    destination: str
    search_url: str
    total_time: str
    transfers: str
    fare: str
    steps: List[RouteStep] = field(default_factory=list)
    stations: List[str] = field(default_factory=list)


def build_search_params(
    departure_station: str,
    destination_station: str,
    search_type: int = 1,
    date: Optional[datetime] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    include_shinkansen: bool = True,
    include_express: bool = True,
    include_airplane: bool = True,
    include_highway_bus: bool = True,
    include_local_bus: bool = True,
    include_ferry: bool = True,
) -> dict:
    """
    Yahoo!路線情報向けの検索クエリパラメータ辞書を構築・正規化する。
    """
    now = datetime.now()
    if date is not None:
        y = date.year
        m = date.month
        d = date.day
        hh = date.hour
        mm = date.minute
    else:
        y = year if year is not None else now.year
        m = month if month is not None else now.month
        d = day if day is not None else now.day
        hh = hour if hour is not None else now.hour
        mm = minute if minute is not None else now.minute

    minute_str = str(mm).zfill(2)
    m1 = minute_str[0]
    m2 = minute_str[1]

    return {
        "from": departure_station.strip(),
        "to": destination_station.strip(),
        "type": str(search_type),
        "y": str(y),
        "m": str(m).zfill(2),
        "d": str(d).zfill(2),
        "hh": str(hh).zfill(2),
        "m1": m1,
        "m2": m2,
        "shin": "1" if include_shinkansen else "0",
        "ex": "1" if include_express else "0",
        "al": "1" if include_airplane else "0",
        "hb": "1" if include_highway_bus else "0",
        "lb": "1" if include_local_bus else "0",
        "sr": "1" if include_ferry else "0",
    }


def clean_text(text: Optional[str]) -> str:
    """連続する空白や改行を1つのスペースに正規化する。"""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def parse_route_html(
    html: str,
    departure_station: str = "",
    destination_station: str = "",
    search_url: str = "",
) -> Route:
    """
    Yahoo!路線情報のHTMLテキストを解析し、Route データクラスを生成する。
    Noneチェックや要素欠損に対して堅牢に処理を行う。

    Args:
        html: 検索結果ページのHTML文字列
        departure_station: 検索出発駅名（補完用）
        destination_station: 検索到着駅名（補完用）
        search_url: リクエスト時のURL（結果に保持用）

    Returns:
        Route: パースされた経路データ

    Raises:
        RouteNotFoundError: 経路情報が存在しない場合
    """
    if not html or not html.strip():
        raise RouteNotFoundError("HTMLコンテンツが空です。")

    soup = BeautifulSoup(html, "html.parser")

    # 1. サマリーの取得
    route_summary = soup.find("div", class_="routeSummary")
    if not route_summary:
        dep = departure_station or "出発駅"
        dst = destination_station or "到着駅"
        raise RouteNotFoundError(
            f"経路情報が見つかりませんでした。駅名や日時の指定を確認してください："
            f"（{dep} → {dst}）"
        )

    time_elem = route_summary.find("li", class_="time")
    transfer_elem = route_summary.find("li", class_="transfer")
    fare_elem = route_summary.find("li", class_="fare")

    total_time = clean_text(time_elem.get_text()) if time_elem else "情報なし"
    transfers = clean_text(transfer_elem.get_text()) if transfer_elem else "情報なし"
    fare = clean_text(fare_elem.get_text()) if fare_elem else "情報なし"

    # 2. 詳細（routeDetail）の解析
    route_detail = soup.find("div", class_="routeDetail")
    steps: List[RouteStep] = []
    station_names: List[str] = []

    if route_detail:
        # 駅要素の解析
        station_divs = route_detail.find_all("div", class_="station")
        raw_stations = []
        for s in station_divs:
            dt_elem = s.find("dt")
            name = clean_text(dt_elem.get_text()) if dt_elem else clean_text(s.get_text())
            time_lis = [clean_text(li.get_text()) for li in s.find_all("li")]

            # 駅の時刻抽出
            dep_time_val = ""
            arr_time_val = ""
            for t_item in time_lis:
                if "発" in t_item:
                    dep_time_val = t_item.replace("発", "").strip()
                elif "着" in t_item:
                    arr_time_val = t_item.replace("着", "").strip()
                elif not dep_time_val and not arr_time_val and re.match(r"^\d{1,2}:\d{2}$", t_item):
                    dep_time_val = t_item

            raw_stations.append({
                "name": name,
                "dep_time": dep_time_val,
                "arr_time": arr_time_val,
                "all_times": " ".join(time_lis)
            })
            station_names.append(name)

        # 移動手段・アクセス要素の解析
        access_divs = route_detail.find_all("div", class_="access")
        raw_transports = []

        for acc in access_divs:
            transport_li = acc.find("li", class_="transport")
            dep_plat = ""
            arr_plat = ""
            stops_text = ""

            # 停車駅数の取得
            stop_li = acc.find("li", class_="stop")
            if stop_li:
                stops_text = clean_text(stop_li.get_text())

            if transport_li:
                # 番線情報の取得
                plat_span = transport_li.find("span", class_="platform")
                if plat_span:
                    plat_text = clean_text(plat_span.get_text())
                    dep_match = re.search(r"\[発\]\s*([^→]+)", plat_text)
                    arr_match = re.search(r"\[着\]\s*(.+)", plat_text)
                    if dep_match:
                        dep_plat = dep_match.group(1).strip()
                    if arr_match:
                        arr_plat = arr_match.group(1).strip()

                t_div = transport_li.find("div")
                t_raw = t_div.get_text() if t_div else transport_li.get_text()
                t_text = clean_text(re.sub(r"\[line.*?\]", "", t_raw))
            else:
                walk_span = acc.find("span", class_="lineWalk")
                if walk_span or "徒歩" in acc.get_text():
                    t_text = "徒歩"
                else:
                    t_text = clean_text(re.sub(r"\[line.*?\]", "", acc.get_text()))

            # 所要時間の取得
            est_elem = acc.find("li", class_="estimatedTime")
            est_time = clean_text(est_elem.get_text()) if est_elem else ""

            # 運賃の取得（accessの親のfareSectionから探す）
            parent_fs = acc.find_parent("div", class_="fareSection")
            collected_fares = []
            if parent_fs:
                # 直近の運賃タグを収集
                for p_fare in parent_fs.find_all("p", class_="fare"):
                    f_val = clean_text(p_fare.get_text())
                    if f_val and f_val not in collected_fares:
                        collected_fares.append(f_val)
            step_fare = " / ".join(collected_fares) if collected_fares else ""

            raw_transports.append({
                "transport": t_text,
                "estimated_time": est_time,
                "fare": step_fare,
                "stops": stops_text,
                "dep_platform": dep_plat,
                "arr_platform": arr_plat,
            })

        # 駅とアクセスを紐付けて RouteStep リストを構築
        for i in range(len(raw_transports)):
            st_dep = raw_stations[i] if i < len(raw_stations) else {"name": "", "dep_time": "", "arr_time": ""}
            st_arr = raw_stations[i + 1] if i + 1 < len(raw_stations) else {"name": "", "dep_time": "", "arr_time": ""}
            trans_info = raw_transports[i]

            dep_time_step = st_dep.get("dep_time") or st_dep.get("all_times", "")
            arr_time_step = st_arr.get("arr_time") or st_arr.get("all_times", "")

            steps.append(
                RouteStep(
                    departure_station=st_dep["name"],
                    arrival_station=st_arr["name"],
                    transport=trans_info["transport"],
                    departure_time=dep_time_step,
                    arrival_time=arr_time_step,
                    estimated_time=trans_info["estimated_time"],
                    fare=trans_info["fare"],
                    stops=trans_info["stops"],
                    departure_platform=trans_info["dep_platform"],
                    arrival_platform=trans_info["arr_platform"],
                )
            )

    dep_final = departure_station or (station_names[0] if station_names else "")
    dst_final = destination_station or (station_names[-1] if station_names else "")

    return Route(
        departure=dep_final,
        destination=dst_final,
        search_url=search_url,
        total_time=total_time,
        transfers=transfers,
        fare=fare,
        steps=steps,
        stations=station_names,
    )


def search_route(
    departure_station: str,
    destination_station: str,
    search_type: int = 1,
    date: Optional[datetime] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    include_shinkansen: bool = True,
    include_express: bool = True,
    include_airplane: bool = True,
    include_highway_bus: bool = True,
    include_local_bus: bool = True,
    include_ferry: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Route:
    """
    Yahoo!路線情報から経路を検索し、Route オブジェクトとして返却する。
    """
    params = build_search_params(
        departure_station=departure_station,
        destination_station=destination_station,
        search_type=search_type,
        date=date,
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        include_shinkansen=include_shinkansen,
        include_express=include_express,
        include_airplane=include_airplane,
        include_highway_bus=include_highway_bus,
        include_local_bus=include_local_bus,
        include_ferry=include_ferry,
    )

    headers = {"User-Agent": DEFAULT_USER_AGENT}
    requester = session if session is not None else requests

    response = requester.get(
        BASE_SEARCH_URL,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    return parse_route_html(
        html=response.text,
        departure_station=departure_station,
        destination_station=destination_station,
        search_url=response.url,
    )


def format_route(route: Route) -> str:
    """Route オブジェクトを表示用の文字列にフォーマットする。"""
    lines = [
        f"検索URL： {route.search_url}",
        f"====== {route.departure} から {route.destination} ======",
        f"所要時間：{route.total_time}",
        f"{route.transfers}",
        f"料金：{route.fare}",
        "======乗り換え情報======",
    ]

    for step in route.steps:
        time_info = f" ({step.departure_time})" if step.departure_time else ""
        lines.append(f"{step.departure_station}{time_info}")

        extra_parts = []
        if step.estimated_time:
            extra_parts.append(step.estimated_time)
        if step.stops:
            extra_parts.append(step.stops)
        if step.fare:
            extra_parts.append(step.fare)

        extra_str = f" [{' / '.join(extra_parts)}]" if extra_parts else ""
        lines.append(f" | {step.transport}{extra_str}")

    if route.steps and route.steps[-1].arrival_station:
        last_step = route.steps[-1]
        last_time = f" ({last_step.arrival_time})" if last_step.arrival_time else ""
        lines.append(f"{last_step.arrival_station}{last_time}")
    elif route.stations:
        lines.append(route.stations[-1])

    return "\n".join(lines)


def prompt_user_inputs():
    """対話形式でユーザーから検索条件を取得する。"""
    departure_station = input("出発駅を入力してください：").strip()
    destination_station = input("到着駅を入力してください：").strip()

    search_type_input = input(
        "出発時間で検索するなら1、到着時間で検索するなら4を入力してください [デフォルト: 1]："
    ).strip()
    search_type = 4 if search_type_input == "4" else 1

    date_option = input(
        "日付を今日にするなら 1、自分で指定するなら 2 を入力してください [デフォルト: 1]："
    ).strip()

    now = datetime.now()
    if date_option == "2":
        year_str = input(f"年（例：{now.year}）[デフォルト: {now.year}]：").strip()
        year = int(year_str) if year_str.isdigit() else now.year

        month_str = input(f"月（例：{now.strftime('%m')}）：").strip().zfill(2)
        month = int(month_str) if month_str.isdigit() else now.month

        day_str = input(f"日（例：{now.strftime('%d')}）：").strip().zfill(2)
        day = int(day_str) if day_str.isdigit() else now.day
    else:
        year = now.year
        month = now.month
        day = now.day

    hour_str = input(f"時（0-23）[デフォルト: {now.strftime('%H')}]：").strip()
    hour = int(hour_str) if hour_str.isdigit() else now.hour

    min_str = input(f"分（0-59）[デフォルト: {now.strftime('%M')}]：").strip()
    minute = int(min_str) if min_str.isdigit() else now.minute

    return {
        "departure_station": departure_station,
        "destination_station": destination_station,
        "search_type": search_type,
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
    }


def main():
    """CLIエントリーポイント。"""
    try:
        user_inputs = prompt_user_inputs()
        if not user_inputs["departure_station"] or not user_inputs["destination_station"]:
            print("⚠️ 出発駅と到着駅は必須です。")
            return

        route = search_route(**user_inputs)
        print()
        print(format_route(route))

    except RouteNotFoundError as e:
        print(f"\n⚠️ {e}")
    except requests.exceptions.Timeout:
        print("\n⚠️ リクエストがタイムアウトしました。通信環境を確認して再度お試しください。")
    except requests.exceptions.RequestException as e:
        print(f"\n⚠️ 通信エラーが発生しました: {e}")
    except KeyboardInterrupt:
        print("\n検索をキャンセルしました。")


if __name__ == "__main__":
    main()