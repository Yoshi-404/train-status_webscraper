# -*- coding: utf-8 -*-
"""
trainstatus.core: Yahoo!路線情報 (Yahoo! Transit Japan) のスクレイピングコアロジック。
全国の経路検索、数値型を含む堅牢なデータクラス、およびエラーハンドリングを提供します。
"""

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import List, Optional, Tuple
import requests
from bs4 import BeautifulSoup

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
    """HTMLパース処理中に構造の不整合や予期せぬ欠損が発生した場合の例外。"""
    pass


@dataclass
class RouteStep:
    """経路内の1区間（移動ステップ）の情報を保持するデータクラス。"""
    departure_station: str
    arrival_station: str
    transport: str
    departure_time: str = ""
    arrival_time: str = ""
    duration_minutes: Optional[int] = None
    estimated_time: str = ""
    fare: str = ""
    fare_yen: Optional[int] = None
    stops: str = ""
    departure_platform: str = ""
    arrival_platform: str = ""


@dataclass
class Route:
    """検索された全体の経路情報を保持するデータクラス。"""
    departure: str
    destination: str
    search_url: str
    duration_minutes: Optional[int] = None
    transfer_count: int = 0
    fare_yen: Optional[int] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    total_time: str = ""
    transfers: str = ""
    fare: str = ""
    steps: List[RouteStep] = field(default_factory=list)
    stations: List[str] = field(default_factory=list)


def clean_text(text: Optional[str]) -> str:
    """連続する空白や改行を1つのスペースに正規化する。"""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def parse_duration_minutes(text: Optional[str]) -> Optional[int]:
    """
    時間文字列（例：'2時間30分', '45分', '1時間'）から分数を計算して int で返却する。
    """
    if not text:
        return None
    m_hm = re.search(r"(?:(\d+)\s*時間)?\s*(?:(\d+)\s*分)", text)
    if m_hm and (m_hm.group(1) or m_hm.group(2)):
        hours = int(m_hm.group(1)) if m_hm.group(1) else 0
        minutes = int(m_hm.group(2)) if m_hm.group(2) else 0
        return hours * 60 + minutes
    m_h = re.search(r"(\d+)\s*時間", text)
    if m_h:
        return int(m_h.group(1)) * 60
    return None


def parse_transfer_count(text: Optional[str]) -> int:
    """'乗換：0回' などの文字列から乗換回数を int で返却する。"""
    if not text:
        return 0
    m = re.search(r"(\d+)\s*回", text)
    return int(m.group(1)) if m else 0


def parse_fare_yen(text: Optional[str]) -> Optional[int]:
    """'13,870円' や 'IC優先：1,120円' などの文字列から数値を抽出して int で返却する。"""
    if not text:
        return None
    m = re.search(r"([0-9,]+)\s*円", text)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def parse_dep_arr_times(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """'12:24発→14:54着...' から出発時刻と到着時刻を抽出する。"""
    if not text:
        return None, None
    dep_time = None
    arr_time = None
    m_dep = re.search(r"(\d{1,2}:\d{2})\s*発", text)
    if m_dep:
        dep_time = m_dep.group(1)
    m_arr = re.search(r"(\d{1,2}:\d{2})\s*着", text)
    if m_arr:
        arr_time = m_arr.group(1)
    return dep_time, arr_time


def calc_duration_minutes(dep_time_str: str, arr_time_str: str) -> Optional[int]:
    """2つの時刻（HH:MM）から所要時間（分数）を算出する。日跨ぎにも対応。"""
    if not dep_time_str or not arr_time_str:
        return None
    try:
        dh, dm = map(int, dep_time_str.split(":"))
        ah, am = map(int, arr_time_str.split(":"))
        diff = (ah * 60 + am) - (dh * 60 + dm)
        if diff < 0:
            diff += 24 * 60  # 日跨ぎの補正
        return diff
    except Exception:
        return None


def format_duration(minutes: Optional[int]) -> str:
    """分数を 'X時間Y分' または 'Y分' 形式の文字列にフォーマットする。"""
    if minutes is None:
        return ""
    h = minutes // 60
    m = minutes % 60
    if h > 0 and m > 0:
        return f"{h}時間{m}分"
    elif h > 0:
        return f"{h}時間"
    else:
        return f"{m}分"


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


def parse_route_html(
    html: str,
    departure_station: str = "",
    destination_station: str = "",
    search_url: str = "",
) -> Route:
    """
    Yahoo!路線情報のHTMLテキストを解析し、構造化された Route オブジェクトを生成する。
    """
    if not html or not html.strip():
        raise RouteNotFoundError("HTMLコンテンツが空です。")

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        raise RouteParseError(f"HTMLの解析に失敗しました: {e}") from e

    # 1. 経路サマリーの解析
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

    total_time_text = clean_text(time_elem.get_text()) if time_elem else ""
    transfers_text = clean_text(transfer_elem.get_text()) if transfer_elem else ""
    fare_text = clean_text(fare_elem.get_text()) if fare_elem else ""

    # 数値・個別フィールドの抽出
    duration_min = parse_duration_minutes(total_time_text)
    transfer_num = parse_transfer_count(transfers_text)
    fare_num = parse_fare_yen(fare_text)
    dep_time_summary, arr_time_summary = parse_dep_arr_times(total_time_text)

    # 2. 経路詳細（routeDetail）の解析
    route_detail = soup.find("div", class_="routeDetail")
    steps: List[RouteStep] = []
    station_names: List[str] = []

    if route_detail:
        station_divs = route_detail.find_all("div", class_="station")
        raw_stations = []
        total_stations = len(station_divs)

        for idx, s in enumerate(station_divs):
            dt_elem = s.find("dt")
            name = clean_text(dt_elem.get_text()) if dt_elem else clean_text(s.get_text())
            time_lis = [clean_text(li.get_text()) for li in s.find_all("li")]

            dep_time_val = ""
            arr_time_val = ""
            for t_item in time_lis:
                if "発" in t_item:
                    dep_time_val = t_item.replace("発", "").strip()
                elif "着" in t_item:
                    arr_time_val = t_item.replace("着", "").strip()
                elif re.match(r"^\d{1,2}:\d{2}$", t_item):
                    if idx == 0:
                        dep_time_val = t_item
                    elif idx == total_stations - 1:
                        arr_time_val = t_item
                    else:
                        if not arr_time_val:
                            arr_time_val = t_item
                        else:
                            dep_time_val = t_item

            raw_stations.append({
                "name": name,
                "dep_time": dep_time_val,
                "arr_time": arr_time_val,
            })
            station_names.append(name)

        access_divs = route_detail.find_all("div", class_="access")
        raw_transports = []

        for acc in access_divs:
            transport_li = acc.find("li", class_="transport")
            dep_plat = ""
            arr_plat = ""
            stops_text = ""
            transport_name = ""

            # 停車駅数
            stop_li = acc.find("li", class_="stop")
            if stop_li:
                stops_text = clean_text(stop_li.get_text())

            if transport_li:
                # プラットフォーム番線の抽出と、路線名からの分離
                t_div = transport_li.find("div")
                if t_div:
                    # プラットフォームspanを探して番線情報を取得後、divから分離
                    plat_span = t_div.find("span", class_="platform")
                    if plat_span:
                        plat_text = clean_text(plat_span.get_text())
                        dep_m = re.search(r"\[発\]\s*([^→]+)", plat_text)
                        arr_m = re.search(r"\[着\]\s*(.+)", plat_text)
                        if dep_m:
                            val = dep_m.group(1).strip()
                            dep_plat = "" if "情報なし" in val else val
                        if arr_m:
                            val = arr_m.group(1).strip()
                            arr_plat = "" if "情報なし" in val else val
                        plat_span.extract()

                    raw_name = clean_text(t_div.get_text())
                else:
                    raw_name = clean_text(transport_li.get_text())

                # 路線名の整形（[line] や 残余プラットフォーム表記を除去）
                raw_name = re.sub(r"\[line.*?\]", "", raw_name)
                raw_name = re.sub(r"\[発\].*?\[着\].*", "", raw_name)
                transport_name = clean_text(raw_name)
            else:
                walk_span = acc.find("span", class_="lineWalk")
                if walk_span or "徒歩" in acc.get_text():
                    transport_name = "徒歩"
                else:
                    transport_name = clean_text(re.sub(r"\[line.*?\]", "", acc.get_text()))

            # 親の fareSection から運賃を階層的に抽出
            parent_fs_list = []
            curr = acc.parent
            while curr and curr != route_detail:
                if curr.name == "div" and "fareSection" in curr.get("class", []):
                    parent_fs_list.append(curr)
                curr = curr.parent

            # 直近および親の fareSection にある fare タグを収集
            fares_found = []
            for fs in parent_fs_list:
                for p in fs.find_all("p", class_="fare", recursive=False):
                    f_val = clean_text(p.get_text())
                    if f_val and f_val not in fares_found:
                        fares_found.append(f_val)

            # 運賃の合計とテキストの決定
            step_fare_str = ""
            step_fare_yen = None

            if fares_found:
                total_step_yen = 0
                for f_item in fares_found:
                    yen = parse_fare_yen(f_item)
                    if yen:
                        total_step_yen += yen
                if total_step_yen > 0:
                    step_fare_yen = total_step_yen
                    if len(fares_found) > 1:
                        # Shinkansen等の複数料金合算（例：13,870円 (乗車券 8,910円 / 自由席 4,960円)）
                        breakdown = " + ".join(fares_found)
                        step_fare_str = f"{total_step_yen:,}円 ({breakdown})"
                    else:
                        step_fare_str = fares_found[0]

            raw_transports.append({
                "transport": transport_name,
                "fare": step_fare_str,
                "fare_yen": step_fare_yen,
                "stops": stops_text,
                "dep_platform": dep_plat,
                "arr_platform": arr_plat,
            })

        # 構造整合性チェック: 駅数 N に対してアクセス数は原則 N-1
        if raw_stations and len(raw_stations) < len(raw_transports):
            raise RouteParseError(
                f"経路詳細の構造不整合: 駅数({len(raw_stations)})がアクセス数({len(raw_transports)})未満です。"
            )

        # 各移動区間 (RouteStep) を組み立て
        for i in range(len(raw_transports)):
            st_dep = raw_stations[i] if i < len(raw_stations) else {"name": "", "dep_time": "", "arr_time": ""}
            st_arr = raw_stations[i + 1] if i + 1 < len(raw_stations) else {"name": "", "dep_time": "", "arr_time": ""}
            trans_info = raw_transports[i]

            step_dep_time = st_dep.get("dep_time", "")
            step_arr_time = st_arr.get("arr_time", "")

            # 時刻差分から所要時間を計算
            step_dur_min = calc_duration_minutes(step_dep_time, step_arr_time)
            step_est_time = format_duration(step_dur_min)

            steps.append(
                RouteStep(
                    departure_station=st_dep["name"],
                    arrival_station=st_arr["name"],
                    transport=trans_info["transport"],
                    departure_time=step_dep_time,
                    arrival_time=step_arr_time,
                    duration_minutes=step_dur_min,
                    estimated_time=step_est_time,
                    fare=trans_info["fare"],
                    fare_yen=trans_info["fare_yen"],
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
        duration_minutes=duration_min,
        transfer_count=transfer_num,
        fare_yen=fare_num,
        departure_time=dep_time_summary,
        arrival_time=arr_time_summary,
        total_time=total_time_text,
        transfers=transfers_text,
        fare=fare_text,
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
