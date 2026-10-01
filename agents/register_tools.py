"""agents/register_tools.py
W03-B: 工具實作與 tools 註冊器的掛接入口。
"""
from __future__ import annotations

try:
    from agents.tools import register_tool
    from agents.tools_impl import (
        search_evidence,
        read_evidence,
        get_financial_snapshot,
        get_macro_snapshot,
        get_price_window,
        calculate_metrics,
    )
except ImportError:
    from tools import register_tool  # type: ignore
    from tools_impl import (  # type: ignore
        search_evidence,
        read_evidence,
        get_financial_snapshot,
        get_macro_snapshot,
        get_price_window,
        calculate_metrics,
    )


def init_tools() -> None:
    """將 6 大工具具體實作掛載至 agents.tools._REGISTRY"""
    register_tool("search_evidence", search_evidence)
    register_tool("read_evidence", read_evidence)
    register_tool("get_financial_snapshot", get_financial_snapshot)
    register_tool("get_macro_snapshot", get_macro_snapshot)
    register_tool("get_price_window", get_price_window)
    register_tool("calculate_metrics", calculate_metrics)


# 模組載入時自動完成註冊
init_tools()