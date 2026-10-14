# -*- coding: utf-8 -*-
"""
trainstatus: 日本全国対応のYahoo!路線情報スクレイパー & 乗換案内ライブラリ。
"""

from trainstatus.core import (
    Route,
    RouteStep,
    RouteError,
    RouteNotFoundError,
    RouteParseError,
    search_route,
    parse_route_html,
    build_search_params,
    parse_duration_minutes,
    parse_transfer_count,
    parse_fare_yen,
)
from trainstatus.cli import format_route, main

__version__ = "0.1.0"
__all__ = [
    "Route",
    "RouteStep",
    "RouteError",
    "RouteNotFoundError",
    "RouteParseError",
    "search_route",
    "parse_route_html",
    "build_search_params",
    "parse_duration_minutes",
    "parse_transfer_count",
    "parse_fare_yen",
    "format_route",
    "main",
    "__version__",
]
