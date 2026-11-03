"""采集管线内部库（仅标准库）。

模块划分：
- http   统一请求：UA、超时、重试退避、限速、可选代理
- store  data/auto JSON 读写、原子写入、日期/状态工具
- appstore  iTunes lookup 版本抓取与版本记录去重/裁剪
- charts  榜单 RSS 抓取、charts.json 合并（latest/top5/rankHistory）
- alerts  告警规则（top5 / rank-jump / version / suspect-hit）与去重

RSS 与 AI 本轮未实现（见 collect.py 中的 TODO 占位）。
"""
from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["http", "store", "appstore", "charts", "alerts"]
