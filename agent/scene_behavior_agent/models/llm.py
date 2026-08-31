"""LLM protocol and deterministic fallback model.

Production can replace DeterministicPlanner with a real chat model.  Keeping a
fallback makes local validation deterministic and avoids requiring network keys.
"""

from __future__ import annotations

from typing import Any, Protocol


class PlannerModel(Protocol):
    def parse_intent(self, user_goal: str) -> dict[str, Any]: ...
    def summarize_scene(self, scene_facts: dict[str, Any], intent: dict[str, Any]) -> str: ...
    def summarize_capabilities(self, device_capabilities: dict[str, Any]) -> str: ...
    def decompose_process(self, state: dict[str, Any]) -> list[dict[str, Any]]: ...
    def model_event_state(self, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]: ...
    def model_behavior_rules(self, state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any]]: ...
    def explain(self, state: dict[str, Any]) -> str: ...
    def repair(self, state: dict[str, Any]) -> dict[str, Any]: ...


class DeterministicPlanner:
    """A deterministic planner that follows the current schema conventions.

    It is intentionally simple: it supports the pallet/conveyor/robot baseline
    and produces a valid SceneBehaviorGraph-style draft for local development.
    """

    def parse_intent(self, user_goal: str) -> dict[str, Any]:
        return {
            "natural_language": user_goal,
            "assumptions": [
                "只使用 SceneDocument 中的显式连接。",
                "Agent 只生成离线 SceneBehaviorGraph，不参与 Runtime 高频调度。",
                "Runtime Scheduler 负责运行期事件投递、规则匹配和资源仲裁。",
            ],
            "constraints": ["baseline_no_mid_run_replanning"],
            "success_criteria": [
                "工件池为空",
                "所有设备无 active actions",
                "出料传送带清空或完成条件满足",
            ],
        }

    def summarize_scene(self, scene_facts: dict[str, Any], intent: dict[str, Any]) -> str:
        instances = scene_facts.get("instances", [])
        device_summary = ", ".join(f"{item.get('instance_id')}({item.get('device_type')})" for item in instances)
        return f"场景包含 {len(instances)} 个设备/对象实例：{device_summary}。目标：{intent.get('natural_language', '')}"

    def summarize_capabilities(self, device_capabilities: dict[str, Any]) -> str:
        parts = []
        for item in device_capabilities.get("summary", {}).get("devices", []):
            parts.append(f"{item.get('spec_id')}: behaviors={item.get('behaviors')}, signals={item.get('signals')}")
        return "\n".join(parts)

    def decompose_process(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        scene = state.get("scene_facts", {})
        conveyors = [i["instance_id"] for i in scene.get("instances", []) if i.get("device_type") == "conveyor"]
        robots = [i["instance_id"] for i in scene.get("instances", []) if i.get("device_type") == "robot_arm"]
        modules: list[dict[str, Any]] = []
        if conveyors:
            modules.append(
                {
                    "module_id": "pallet_transport",
                    "mode": "one_shot",
                    "devices": [conveyors[0]],
                    "start_event": "runtime.sim_start",
                    "complete_event": f"{conveyors[0]}.pallet_ready",
                    "stop_condition": f"device_states.{conveyors[0]} == idle",
                }
            )
        if robots:
            modules.append(
                {
                    "module_id": "parallel_robot_sorting",
                    "mode": "parallel_continuous",
                    "devices": robots,
                    "start_event": f"{conveyors[0]}.pallet_ready" if conveyors else "runtime.sim_start",
                    "stop_condition": "workpiece_pool.remaining_parts.empty == true",
                }
            )
        if len(conveyors) > 1:
            modules.append(
                {
                    "module_id": "output_conveying",
                    "mode": "continuous",
                    "devices": conveyors[1:],
                    "start_event": "output_conveyor.material_arrived",
                    "stop_condition": "all output conveyor loads are empty",
                }
            )
        return modules

    def model_event_state(self, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        scene = state.get("scene_facts", {})
        instances = scene.get("instances", [])
        conveyors = [i["instance_id"] for i in instances if i.get("device_type") == "conveyor"]
        robots = [i["instance_id"] for i in instances if i.get("device_type") == "robot_arm"]
        main_conveyor = conveyors[0] if conveyors else "main_conveyor_1"
        output_conveyors = conveyors[1:] if len(conveyors) > 1 else []
        events = [
            {"event_id": "runtime.sim_start", "kind": "global_event", "source": "runtime", "payload_schema": {}, "retention": "event_log"},
            {"event_id": f"{main_conveyor}.pallet_ready", "kind": "device_signal", "source": main_conveyor, "payload_schema": {"carrier_id": "string", "location": "string"}, "retention": "event_log"},
            {"event_id": "robot.pick_request", "kind": "global_event", "source": "scheduler", "payload_schema": {"robot_id": "string"}, "retention": "event_log"},
            {"event_id": "global.workpiece_claimed", "kind": "global_event", "source": "policy", "payload_schema": {"robot_id": "string", "material_id": "string", "source_slot": "string"}, "retention": "event_log"},
            {"event_id": "robot.pick_done", "kind": "device_signal", "source": "robot_arm", "payload_schema": {"robot_id": "string", "material_id": "string", "target_conveyor": "string"}, "retention": "event_log"},
            {"event_id": "output_conveyor.material_arrived", "kind": "device_signal", "source": "output_conveyor", "payload_schema": {"conveyor_id": "string", "material_id": "string"}, "retention": "event_log"},
            {"event_id": "output_conveyor.blocked", "kind": "device_signal", "source": "output_conveyor", "payload_schema": {"conveyor_id": "string", "current_load": "integer", "max_capacity": "integer"}, "retention": "latest_value"},
            {"event_id": "output_conveyor.capacity_available", "kind": "device_signal", "source": "output_conveyor", "payload_schema": {"conveyor_id": "string", "current_load": "integer", "resume_threshold": "integer"}, "retention": "event_log"},
            {"event_id": "robot.pause_pick", "kind": "control_event", "source": "scheduler", "payload_schema": {"robot_id": "string", "reason": "string"}, "retention": "latest_value"},
            {"event_id": "robot.resume_pick", "kind": "control_event", "source": "scheduler", "payload_schema": {"robot_id": "string"}, "retention": "event_log"},
            {"event_id": "global.sorting_done", "kind": "global_event", "source": "runtime", "payload_schema": {"scene_id": "string"}, "retention": "event_log"},
            {"event_id": "observation.deadlock_detected", "kind": "observation", "source": "runtime", "payload_schema": {"reason": "string"}, "retention": "event_log"},
        ]
        topics = [
            {"topic_id": "robot_pick_request", "description": "托盘到位后广播给所有可参与分拣的机械臂候选规则。", "delivery": "broadcast"},
            {"topic_id": "backpressure", "description": "出料传送带容量变化后广播给暂停/恢复规则。", "delivery": "broadcast"},
        ]
        subscriptions = {
            "robot_pick_request": [
                {
                    "subscriber_type": "rule",
                    "subscriber_id": "idle_robot_requests_workpiece",
                    "message_event_id": "robot.pick_request",
                    "filter": f"device_states.{robot} == idle",
                    "payload_template": {"robot_id": robot},
                }
                for robot in robots
            ],
            "backpressure": [
                {
                    "subscriber_type": "rule",
                    "subscriber_id": "blocked_conveyor_pauses_robot",
                    "message_event_id": "output_conveyor.blocked",
                    "filter": "event.event_id == output_conveyor.blocked",
                    "payload_template": "source_event.payload",
                },
                {
                    "subscriber_type": "rule",
                    "subscriber_id": "capacity_available_resumes_robot",
                    "message_event_id": "output_conveyor.capacity_available",
                    "filter": "event.event_id == output_conveyor.capacity_available",
                    "payload_template": "source_event.payload",
                },
            ],
        }
        routes = [
            {"route_id": "route_sim_start_to_start_pallet_transport_rule", "from": "runtime.sim_start", "to": {"type": "rule", "id": "start_pallet_transport"}, "delivery": "direct"},
            {"route_id": "route_pallet_ready_to_robot_pick_topic", "from": f"{main_conveyor}.pallet_ready", "to": {"type": "topic", "id": "robot_pick_request"}, "delivery": "broadcast", "target_resolver": {"type": "subscription", "path": "event_bus.subscriptions.robot_pick_request"}},
            {"route_id": "route_workpiece_claimed_to_pick_rule", "from": "global.workpiece_claimed", "to": {"type": "rule", "id": "claimed_workpiece_starts_pick"}, "delivery": "direct"},
            {"route_id": "route_pick_done_to_material_arrival_rule", "from": "robot.pick_done", "to": {"type": "rule", "id": "output_conveyor_runs_when_material_arrives"}, "delivery": "direct", "target_resolver": {"type": "payload_field", "path": "payload.target_conveyor"}},
            {"route_id": "route_blocked_to_backpressure_topic", "from": "output_conveyor.blocked", "to": {"type": "topic", "id": "backpressure"}, "delivery": "broadcast", "target_resolver": {"type": "subscription", "path": "event_bus.subscriptions.backpressure"}},
            {"route_id": "route_capacity_available_to_backpressure_topic", "from": "output_conveyor.capacity_available", "to": {"type": "topic", "id": "backpressure"}, "delivery": "broadcast", "target_resolver": {"type": "subscription", "path": "event_bus.subscriptions.backpressure"}},
            {"route_id": "route_sorting_done_to_completion_checker", "from": "global.sorting_done", "to": {"type": "runtime", "id": "CompletionChecker"}, "delivery": "internal"},
        ]
        event_bus = {"events": events, "topics": topics, "subscriptions": subscriptions, "routes": routes}
        if output_conveyors and robots:
            event_bus["backpressure_bindings"] = [{"conveyor_id": conveyor, "affected_robots": robots} for conveyor in output_conveyors]

        material_ids = [material.get("material_id") for material in scene.get("materials", []) if material.get("material_id")]
        state_model = {
            "workpiece_pool": {"remaining_parts": {"initial_items": material_ids, "claimed": {}, "completed": []}},
            "material_claims": {},
            "device_states": {instance.get("instance_id"): "idle" for instance in instances if instance.get("instance_id")},
            "signal_values": {},
            "resource_locks": {},
            "active_actions": {},
            "conveyor_loads": {
                conveyor: {"current_load": 0, "max_capacity": 3, "resume_threshold": 2, "blocked": False}
                for conveyor in output_conveyors
            },
        }
        return event_bus, state_model

    def model_behavior_rules(self, state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any]]:
        scene = state.get("scene_facts", {})
        conveyors = [i["instance_id"] for i in scene.get("instances", []) if i.get("device_type") == "conveyor"]
        robots = [i["instance_id"] for i in scene.get("instances", []) if i.get("device_type") == "robot_arm"]
        main_conveyor = conveyors[0] if conveyors else "main_conveyor_1"
        rules = [
            {
                "rule_id": "start_pallet_transport",
                "module_id": "pallet_transport",
                "description": "仿真开始后，如果主传送带空闲则启动托盘运输。",
                "trigger": {"type": "event", "event_id": "runtime.sim_start"},
                "guard": {"all": [f"device_states.{main_conveyor} == idle"], "any": [], "none": []},
                "policy": {"policy_id": "deterministic_priority", "inputs": {"priority": 1}},
                "action": {"type": "start_behavior", "instance_id": main_conveyor, "behavior_id": "transport_to_exit", "payload": {"carrier_id": "pallet_1"}},
            },
            {
                "rule_id": "idle_robot_requests_workpiece",
                "module_id": "parallel_robot_sorting",
                "description": "空闲机械臂请求从共享工件池 claim 物料。",
                "trigger": {"type": "event", "event_id": "robot.pick_request"},
                "guard": {
                    "all": [
                        "workpiece_pool.remaining_parts.empty == false",
                        "device_states[trigger.payload.robot_id] == idle",
                        "resource(trigger.payload.robot_id.gripper).locked_by == null",
                    ],
                    "any": [],
                    "none": ["target_conveyors.blocked_for_robot(trigger.payload.robot_id) == true"],
                },
                "policy": {
                    "policy_id": "claim_workpiece",
                    "inputs": {"robot_id": "trigger.payload.robot_id", "source_pool": "workpiece_pool.remaining_parts"},
                    "bind_outputs_to": {"material_id": "action.payload.material_id"},
                },
                "action": {
                    "type": "emit_event",
                    "event_id": "global.workpiece_claimed",
                    "payload": {"robot_id": "trigger.payload.robot_id", "material_id": "policy.material_id", "source_slot": "policy.source_slot"},
                },
            },
            {
                "rule_id": "claimed_workpiece_starts_pick",
                "module_id": "parallel_robot_sorting",
                "description": "物料 claim 成功后，对应机械臂启动 pick_and_place。",
                "trigger": {"type": "event", "event_id": "global.workpiece_claimed"},
                "guard": {"all": ["device_states[trigger.payload.robot_id] == idle", "material_claims[trigger.payload.material_id].claimed_by == trigger.payload.robot_id"], "any": [], "none": ["target_conveyors.blocked_for_robot(trigger.payload.robot_id) == true"]},
                "policy": {"policy_id": "target_conveyor_selection", "inputs": {"robot_id": "trigger.payload.robot_id", "material_id": "trigger.payload.material_id"}, "bind_outputs_to": {"target_conveyor_id": "action.payload.target_conveyor_id"}},
                "action": {"type": "start_behavior", "instance_id": "trigger.payload.robot_id", "behavior_id": "pick_and_place", "payload": {"material_id": "trigger.payload.material_id", "target_conveyor_id": "policy.target_conveyor_id"}},
            },
            {
                "rule_id": "output_conveyor_runs_when_material_arrives",
                "module_id": "output_conveying",
                "description": "物料到达出料传送带后，目标传送带启动或保持持续运输。",
                "trigger": {"type": "event", "event_id": "output_conveyor.material_arrived"},
                "guard": {"all": ["device_states[trigger.payload.conveyor_id] in [idle, moving]", "conveyor_loads[trigger.payload.conveyor_id].current_load > 0"], "any": [], "none": []},
                "policy": {"policy_id": "backpressure", "inputs": {"conveyor_id": "trigger.payload.conveyor_id"}},
                "action": {"type": "start_or_continue_behavior", "instance_id": "trigger.payload.conveyor_id", "behavior_id": "transport_to_exit"},
            },
            {
                "rule_id": "blocked_conveyor_pauses_robot",
                "module_id": "parallel_robot_sorting",
                "description": "出料传送带 blocked 后暂停受影响机械臂后续抓取。",
                "trigger": {"type": "event", "event_id": "output_conveyor.blocked"},
                "guard": {"all": ["conveyor_loads[trigger.payload.conveyor_id].blocked == true"], "any": [], "none": []},
                "policy": {"policy_id": "backpressure", "inputs": {"conveyor_id": "trigger.payload.conveyor_id"}, "bind_outputs_to": {"target_robots": "action.target"}},
                "action": {"type": "emit_event", "event_id": "robot.pause_pick", "target": "policy.target_robots", "payload": {"reason": "target_conveyor_blocked", "conveyor_id": "trigger.payload.conveyor_id"}},
            },
            {
                "rule_id": "capacity_available_resumes_robot",
                "module_id": "parallel_robot_sorting",
                "description": "出料传送带容量恢复后恢复受影响机械臂。",
                "trigger": {"type": "event", "event_id": "output_conveyor.capacity_available"},
                "guard": {"all": ["conveyor_loads[trigger.payload.conveyor_id].blocked == false"], "any": [], "none": []},
                "policy": {"policy_id": "backpressure", "inputs": {"conveyor_id": "trigger.payload.conveyor_id"}, "bind_outputs_to": {"target_robots": "action.target"}},
                "action": {"type": "emit_event", "event_id": "robot.resume_pick", "target": "policy.target_robots", "payload": {"conveyor_id": "trigger.payload.conveyor_id"}},
            },
        ]
        transitions = [
            {"rule_id": "pallet_transport_start", "on_behavior_start": f"{main_conveyor}.transport_to_exit", "effects": [f"set device_states.{main_conveyor} = moving", f"lock {main_conveyor}.belt_surface"]},
            {"rule_id": "pallet_transport_complete", "on_behavior_complete": f"{main_conveyor}.transport_to_exit", "effects": [f"move pallet_1 to {main_conveyor}.exit", f"set device_states.{main_conveyor} = idle", f"unlock {main_conveyor}.belt_surface", f"emit {main_conveyor}.pallet_ready"]},
            {"rule_id": "claim_workpiece", "on_event": "robot.pick_request", "effects": ["PolicyLibrary.claim_workpiece atomically removes next available material from workpiece_pool", "set material_claims[material_id] = robot_id", "emit global.workpiece_claimed"]},
            {"rule_id": "robot_pick_start", "on_behavior_start": "*.pick_and_place", "effects": ["set device_states[robot_id] = busy", "lock robot_id.robot_arm", "lock robot_id.gripper"]},
            {"rule_id": "robot_pick_complete", "on_behavior_complete": "*.pick_and_place", "effects": ["move material_id to target_conveyor.entry", "append material_id to workpiece_pool.completed", "set device_states[robot_id] = idle", "unlock robot_id.gripper", "unlock robot_id.robot_arm", "emit robot.pick_done", "emit output_conveyor.material_arrived"]},
            {"rule_id": "output_material_arrival_updates_load", "on_event": "output_conveyor.material_arrived", "effects": ["increment conveyor_loads[conveyor_id].current_load", "if current_load >= max_capacity emit output_conveyor.blocked"]},
            {"rule_id": "output_conveyor_transport_complete", "on_behavior_complete": "*.transport_to_exit where instance in output_conveyors", "effects": ["decrement conveyor_loads[conveyor_id].current_load", "if blocked == true and current_load <= resume_threshold emit output_conveyor.capacity_available"]},
            {"rule_id": "robot_pause", "on_event": "robot.pause_pick", "effects": ["set device_states[robot_id] = waiting_downstream after current safe action boundary"]},
            {"rule_id": "robot_resume", "on_event": "robot.resume_pick", "effects": ["set device_states[robot_id] = idle if robot has no active action"]},
        ]
        completion = [
            "workpiece_pool.remaining_parts.empty == true",
            "active_actions.empty == true",
            "all conveyor_loads current_load == 0",
        ]
        return rules, transitions, completion

    def explain(self, state: dict[str, Any]) -> str:
        modules = state.get("process_modules", [])
        validation = state.get("validation_report", state.get("connection_validation", {}))
        module_text = ", ".join(module.get("module_id", "unknown") for module in modules)
        return (
            "Agent 对当前场景的调度理解：\n"
            f"- 模块划分：{module_text}\n"
            "- 主链路：runtime.sim_start -> 托盘运输 -> pallet_ready -> robot_pick_request topic -> robot.pick_request -> claim -> pick_and_place。\n"
            "- backpressure：出料传送带 blocked/capacity_available 通过 topic 广播给暂停/恢复规则。\n"
            f"- 校验状态：{'通过' if validation.get('valid') else '存在问题'}。"
        )

    def repair(self, state: dict[str, Any]) -> dict[str, Any]:
        state["repair_attempts"] = int(state.get("repair_attempts", 0)) + 1
        return state
