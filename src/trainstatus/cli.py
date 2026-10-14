# -*- coding: utf-8 -*-
"""
trainstatus.cli: コマンドラインインターフェース（CLI）モジュール。
対話形式の入出力および整形表示を担当します。
"""

from datetime import datetime
import requests

from trainstatus.core import (
    Route,
    RouteNotFoundError,
    RouteParseError,
    search_route,
)


def format_route(route: Route) -> str:
    """Route オブジェクトを表示用の文字列にフォーマットする。"""
    lines = [
        f"検索URL： {route.search_url}",
        f"====== {route.departure} から {route.destination} ======",
    ]

    # 時間・乗換・料金情報の整形
    if route.total_time:
        lines.append(f"所要時間：{route.total_time}")
    elif route.duration_minutes is not None:
        lines.append(f"所要時間：{route.duration_minutes}分")

    if route.transfers:
        lines.append(f"{route.transfers}")
    else:
        lines.append(f"乗換：{route.transfer_count}回")

    if route.fare:
        lines.append(f"料金：{route.fare}")
    elif route.fare_yen is not None:
        lines.append(f"料金：{route.fare_yen:,}円")

    lines.append("======乗り換え情報======")

    for step in route.steps:
        dep_time_str = f" ({step.departure_time})" if step.departure_time else ""
        lines.append(f"{step.departure_station}{dep_time_str}")

        extra_parts = []
        if step.estimated_time:
            extra_parts.append(step.estimated_time)
        elif step.duration_minutes is not None:
            extra_parts.append(f"{step.duration_minutes}分")

        if step.stops:
            extra_parts.append(step.stops)

        # プラットフォーム情報
        plat_info = []
        if step.departure_platform:
            plat_info.append(f"[発] {step.departure_platform}")
        if step.arrival_platform:
            plat_info.append(f"[着] {step.arrival_platform}")
        if plat_info:
            extra_parts.append(" → ".join(plat_info))

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
    except RouteParseError as e:
        print(f"\n⚠️ ページ構造の解析エラー: {e}")
    except requests.exceptions.Timeout:
        print("\n⚠️ リクエストがタイムアウトしました。通信環境を確認して再度お試しください。")
    except requests.exceptions.RequestException as e:
        print(f"\n⚠️ 通信エラーが発生しました: {e}")
    except KeyboardInterrupt:
        print("\n検索をキャンセルしました。")


if __name__ == "__main__":
    main()
