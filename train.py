# -*- coding: utf-8 -*-
"""
train.py: 互換性および直接実行用スクリプト。
実体は src/trainstatus パッケージに実装されています。
"""

import sys
from pathlib import Path

# src ディレクトリを検索パスに追加
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from trainstatus import (  # noqa: F401
    Route,
    RouteStep,
    RouteError,
    RouteNotFoundError,
    RouteParseError,
    search_route,
    parse_route_html,
    build_search_params,
    format_route,
    main,
    __version__,
)

if __name__ == "__main__":
    main()