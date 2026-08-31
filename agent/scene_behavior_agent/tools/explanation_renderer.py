"""Deterministic renderer for user-facing graph explanations."""

from __future__ import annotations

from typing import Any


class ExplanationRenderer:
    def render(self, state: dict[str, Any]) -> str:
        modules = state.get("process_modules", [])
        validation = state.get("validation_report", state.get("connection_validation", {}))
        module_text = ", ".join(module.get("module_id", "unknown") for module in modules) or "未生成"
        route_count = len(state.get("event_bus_draft", {}).get("routes", []))
        return (
            "Agent 对当前场景的调度理解：\n"
            f"- 模块划分：{module_text}\n"
            f"- 事件路由数量：{route_count}\n"
            "- 主链路：runtime.sim_start -> 托盘运输 -> pallet_ready -> robot_pick_request topic -> robot.pick_request -> claim -> pick_and_place。\n"
            "- backpressure：出料传送带 blocked/capacity_available 通过 topic 广播给暂停/恢复规则。\n"
            f"- 校验状态：{'通过' if validation.get('valid') else '存在问题'}。"
        )
