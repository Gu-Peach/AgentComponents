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

    @staticmethod
    def _instance_params(instance: dict[str, Any]) -> dict[str, Any]:
        return {**instance.get("params", {}), **instance.get("param_overrides", {})}

    @classmethod
    def _classify_conveyors(cls, scene_facts: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        conveyors = [instance for instance in scene_facts.get("instances", []) if instance.get("device_type") == "conveyor"]
        output_conveyors = [instance for instance in conveyors if "out" in instance.get("instance_id", "")]
        main_conveyors = [instance for instance in conveyors if instance not in output_conveyors]
        if not main_conveyors and conveyors:
            main_conveyors = [conveyors[0]]
        if not output_conveyors and len(conveyors) > len(main_conveyors):
            main_ids = {instance.get("instance_id") for instance in main_conveyors}
            output_conveyors = [instance for instance in conveyors if instance.get("instance_id") not in main_ids]
        return main_conveyors, output_conveyors

    @classmethod
    def _conveyor_runtime_config(cls, instance: dict[str, Any]) -> dict[str, int]:
        params = cls._instance_params(instance)
        stop_point_count = int(params.get("stop_point_count", 4))
        capacity = int(params.get("capacity", min(stop_point_count, 3)))
        resume_threshold = int(params.get("resume_threshold", max(0, capacity - 1)))
        return {
            "stop_point_count": max(stop_point_count, 2),
            "capacity": max(capacity, 1),
            "resume_threshold": max(resume_threshold, 0),
        }

    @classmethod
    def _conveyor_stop_points(cls, instance: dict[str, Any]) -> list[dict[str, Any]]:
        conveyor_id = instance.get("instance_id", "conveyor")
        count = cls._conveyor_runtime_config(instance)["stop_point_count"]
        points = []
        for index in range(count):
            role = "middle"
            if index == 0:
                role = "entry"
            elif index == count - 1:
                role = "exit"
            points.append(
                {
                    "point_id": f"{conveyor_id}.sp_{index + 1:02d}",
                    "index": index,
                    "t": round(index / (count - 1), 4),
                    "role": role,
                    "coordinate_source": "DeviceSpec.type_specific_contract.stop_point_model.coordinate_formula",
                }
            )
        return points

    def parse_intent(self, user_goal: str) -> dict[str, Any]:
        return {
            "natural_language": user_goal,
            "assumptions": [
                "只使用 SceneDocument 中的显式连接。",
                "Agent 只生成离线 SceneBehaviorGraph，不参与 Runtime 高频调度。",
                "Runtime Scheduler 负责运行期事件投递、规则匹配和资源仲裁。",
                "所有传送带默认按停留点感知运输建模，停留点由 entry/exit 坐标和 stop_point_count 插值得到。",
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
        main_conveyors, output_conveyors = self._classify_conveyors(scene)
        main_conveyor_ids = [instance["instance_id"] for instance in main_conveyors if instance.get("instance_id")]
        output_conveyor_ids = [instance["instance_id"] for instance in output_conveyors if instance.get("instance_id")]
        robots = [i["instance_id"] for i in scene.get("instances", []) if i.get("device_type") == "robot_arm"]
        modules: list[dict[str, Any]] = []
        if main_conveyor_ids:
            modules.append(
                {
                    "module_id": "pallet_transport",
                    "mode": "sequential",
                    "transport_model": "stop_point_buffered_transport",
                    "devices": main_conveyor_ids,
                    "start_event": "runtime.sim_start",
                    "complete_event": f"{main_conveyor_ids[-1]}.pallet_ready",
                    "stop_condition": " and ".join(f"device_states.{conveyor_id} == idle" for conveyor_id in main_conveyor_ids),
                }
            )
        if robots:
            modules.append(
                {
                    "module_id": "parallel_robot_sorting",
                    "mode": "parallel_continuous",
                    "devices": robots,
                    "start_event": f"{main_conveyor_ids[-1]}.pallet_ready" if main_conveyor_ids else "runtime.sim_start",
                    "stop_condition": "workpiece_pool.remaining_parts.empty == true",
                }
            )
        if output_conveyor_ids:
            modules.append(
                {
                    "module_id": "output_conveying",
                    "mode": "continuous",
                    "transport_model": "stop_point_buffered_transport",
                    "devices": output_conveyor_ids,
                    "start_event": "output_conveyor.material_arrived",
                    "stop_condition": "all output conveyor loads and stop points are empty",
                }
            )
        return modules

    def model_event_state(self, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        scene = state.get("scene_facts", {})
        instances = scene.get("instances", [])
        main_conveyors, output_conveyors = self._classify_conveyors(scene)
        all_conveyors = main_conveyors + output_conveyors
        main_conveyor_ids = [i["instance_id"] for i in main_conveyors if i.get("instance_id")]
        output_conveyor_ids = [i["instance_id"] for i in output_conveyors if i.get("instance_id")]
        robots = [i["instance_id"] for i in instances if i.get("device_type") == "robot_arm"]
        main_conveyor = main_conveyor_ids[-1] if main_conveyor_ids else "main_conveyor_1"
        first_main_conveyor = main_conveyor_ids[0] if main_conveyor_ids else main_conveyor
        pallet_ready_event_ids = main_conveyor_ids or [main_conveyor]
        events = [
            {"event_id": "runtime.sim_start", "kind": "global_event", "source": "runtime", "payload_schema": {}, "retention": "event_log"},
            {"event_id": "conveyor.stop_point_occupied", "kind": "device_signal", "source": "conveyor", "payload_schema": {"conveyor_id": "string", "point_id": "string", "material_id": "string"}, "retention": "event_log"},
            {"event_id": "conveyor.stop_point_released", "kind": "device_signal", "source": "conveyor", "payload_schema": {"conveyor_id": "string", "point_id": "string", "material_id": "string"}, "retention": "event_log"},
            {"event_id": "robot.pick_request", "kind": "global_event", "source": "scheduler", "payload_schema": {"robot_id": "string"}, "retention": "event_log"},
            {"event_id": "global.workpiece_claimed", "kind": "global_event", "source": "policy", "payload_schema": {"robot_id": "string", "material_id": "string", "source_slot": "string"}, "retention": "event_log"},
            {"event_id": "robot.pick_done", "kind": "device_signal", "source": "robot_arm", "payload_schema": {"robot_id": "string", "material_id": "string", "target_conveyor": "string"}, "retention": "event_log"},
            {"event_id": "output_conveyor.material_arrived", "kind": "device_signal", "source": "output_conveyor", "payload_schema": {"conveyor_id": "string", "material_id": "string"}, "retention": "event_log"},
            {"event_id": "conveyor.blocked", "kind": "device_signal", "source": "conveyor", "payload_schema": {"conveyor_id": "string", "current_load": "integer", "max_capacity": "integer", "reason": "string"}, "retention": "latest_value"},
            {"event_id": "conveyor.capacity_available", "kind": "device_signal", "source": "conveyor", "payload_schema": {"conveyor_id": "string", "current_load": "integer", "resume_threshold": "integer"}, "retention": "event_log"},
            {"event_id": "robot.pause_pick", "kind": "control_event", "source": "scheduler", "payload_schema": {"robot_id": "string", "reason": "string"}, "retention": "latest_value"},
            {"event_id": "robot.resume_pick", "kind": "control_event", "source": "scheduler", "payload_schema": {"robot_id": "string"}, "retention": "event_log"},
            {"event_id": "global.sorting_done", "kind": "global_event", "source": "runtime", "payload_schema": {"scene_id": "string"}, "retention": "event_log"},
            {"event_id": "observation.deadlock_detected", "kind": "observation", "source": "runtime", "payload_schema": {"reason": "string"}, "retention": "event_log"},
        ]
        events.extend(
            {
                "event_id": f"{conveyor_id}.pallet_ready",
                "kind": "device_signal",
                "source": conveyor_id,
                "payload_schema": {"carrier_id": "string", "location": "string", "next_conveyor_id": "string"},
                "retention": "event_log",
            }
            for conveyor_id in pallet_ready_event_ids
        )
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
                    "message_event_id": "conveyor.blocked",
                    "filter": "event.event_id == conveyor.blocked",
                    "payload_template": "source_event.payload",
                },
                {
                    "subscriber_type": "rule",
                    "subscriber_id": "capacity_available_resumes_robot",
                    "message_event_id": "conveyor.capacity_available",
                    "filter": "event.event_id == conveyor.capacity_available",
                    "payload_template": "source_event.payload",
                },
            ],
        }
        routes = [
            {"route_id": "route_sim_start_to_start_pallet_transport_rule", "from": "runtime.sim_start", "to": {"type": "rule", "id": "start_pallet_transport"}, "delivery": "direct"},
            {"route_id": "route_stop_point_occupied_to_advance_rule", "from": "conveyor.stop_point_occupied", "to": {"type": "rule", "id": "advance_material_to_next_stop_point"}, "delivery": "direct"},
            {"route_id": "route_stop_point_released_to_capacity_rule", "from": "conveyor.stop_point_released", "to": {"type": "rule", "id": "emit_capacity_available_when_stop_point_released"}, "delivery": "direct"},
            {"route_id": "route_workpiece_claimed_to_pick_rule", "from": "global.workpiece_claimed", "to": {"type": "rule", "id": "claimed_workpiece_starts_pick"}, "delivery": "direct"},
            {"route_id": "route_pick_done_to_material_arrival_rule", "from": "robot.pick_done", "to": {"type": "rule", "id": "output_conveyor_runs_when_material_arrives"}, "delivery": "direct", "target_resolver": {"type": "payload_field", "path": "payload.target_conveyor"}},
            {"route_id": "route_blocked_to_backpressure_topic", "from": "conveyor.blocked", "to": {"type": "topic", "id": "backpressure"}, "delivery": "broadcast", "target_resolver": {"type": "subscription", "path": "event_bus.subscriptions.backpressure"}},
            {"route_id": "route_capacity_available_to_backpressure_topic", "from": "conveyor.capacity_available", "to": {"type": "topic", "id": "backpressure"}, "delivery": "broadcast", "target_resolver": {"type": "subscription", "path": "event_bus.subscriptions.backpressure"}},
            {"route_id": "route_sorting_done_to_completion_checker", "from": "global.sorting_done", "to": {"type": "runtime", "id": "CompletionChecker"}, "delivery": "internal"},
        ]
        for current_conveyor_id, next_conveyor_id in zip(main_conveyor_ids, main_conveyor_ids[1:]):
            routes.append(
                {
                    "route_id": f"route_{current_conveyor_id}_ready_to_{next_conveyor_id}_transport_rule",
                    "from": f"{current_conveyor_id}.pallet_ready",
                    "to": {"type": "rule", "id": f"transfer_pallet_{current_conveyor_id}_to_{next_conveyor_id}"},
                    "delivery": "direct",
                }
            )
        routes.append(
            {"route_id": "route_pallet_ready_to_robot_pick_topic", "from": f"{main_conveyor}.pallet_ready", "to": {"type": "topic", "id": "robot_pick_request"}, "delivery": "broadcast", "target_resolver": {"type": "subscription", "path": "event_bus.subscriptions.robot_pick_request"}}
        )
        event_bus = {"events": events, "topics": topics, "subscriptions": subscriptions, "routes": routes}
        if output_conveyor_ids and robots:
            event_bus["backpressure_bindings"] = [{"conveyor_id": conveyor_id, "affected_robots": robots} for conveyor_id in output_conveyor_ids]

        material_ids = [material.get("material_id") for material in scene.get("materials", []) if material.get("material_id")]
        state_model = {
            "workpiece_pool": {"remaining_parts": {"initial_items": material_ids, "claimed": {}, "completed": []}},
            "material_claims": {},
            "device_states": {instance.get("instance_id"): "idle" for instance in instances if instance.get("instance_id")},
            "signal_values": {},
            "resource_locks": {},
            "active_actions": {},
            "conveyor_stop_points": {
                conveyor.get("instance_id"): {
                    "generation": "linear_interpolation",
                    "points": self._conveyor_stop_points(conveyor),
                }
                for conveyor in all_conveyors
                if conveyor.get("instance_id")
            },
            "conveyor_occupancy": {
                conveyor.get("instance_id"): {
                    point["point_id"]: None for point in self._conveyor_stop_points(conveyor)
                }
                for conveyor in all_conveyors
                if conveyor.get("instance_id")
            },
            "conveyor_queues": {
                conveyor.get("instance_id"): {"queue_id": f"{conveyor.get('instance_id')}.stop_point_queue", "waiting_materials": []}
                for conveyor in all_conveyors
                if conveyor.get("instance_id")
            },
            "conveyor_loads": {
                conveyor.get("instance_id"): {
                    "current_load": 0,
                    "max_capacity": self._conveyor_runtime_config(conveyor)["capacity"],
                    "resume_threshold": self._conveyor_runtime_config(conveyor)["resume_threshold"],
                    "blocked": False,
                }
                for conveyor in all_conveyors
                if conveyor.get("instance_id")
            },
        }
        return event_bus, state_model

    def model_behavior_rules(self, state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any]]:
        scene = state.get("scene_facts", {})
        main_conveyors, output_conveyors = self._classify_conveyors(scene)
        main_conveyor_ids = [i["instance_id"] for i in main_conveyors if i.get("instance_id")]
        output_conveyor_ids = [i["instance_id"] for i in output_conveyors if i.get("instance_id")]
        robots = [i["instance_id"] for i in scene.get("instances", []) if i.get("device_type") == "robot_arm"]
        main_conveyor = main_conveyor_ids[-1] if main_conveyor_ids else "main_conveyor_1"
        first_main_conveyor = main_conveyor_ids[0] if main_conveyor_ids else main_conveyor
        rules = [
            {
                "rule_id": "start_pallet_transport",
                "module_id": "pallet_transport",
                "description": "仿真开始后，如果主传送带入口停留点可用，则启动托盘的停留点感知运输。",
                "trigger": {"type": "event", "event_id": "runtime.sim_start"},
                "guard": {"all": [f"device_states.{first_main_conveyor} == idle", f"entry_stop_point({first_main_conveyor}).occupied == false"], "any": [], "none": []},
                "policy": {"policy_id": "conveyor_stop_point_selection", "inputs": {"conveyor_id": first_main_conveyor, "material_id": "pallet_1"}},
                "action": {"type": "start_behavior", "instance_id": first_main_conveyor, "behavior_id": "transport_to_exit", "payload": {"carrier_id": "pallet_1", "transport_model": "stop_point_buffered_transport"}},
            },
            *[
                {
                    "rule_id": f"transfer_pallet_{current_conveyor_id}_to_{next_conveyor_id}",
                    "module_id": "pallet_transport",
                    "description": "上一段主传送带托盘到位后，若下一段入口停留点可接收，则启动下一段托盘运输。",
                    "trigger": {"type": "event", "event_id": f"{current_conveyor_id}.pallet_ready"},
                    "guard": {
                        "all": [
                            f"device_states.{next_conveyor_id} == idle",
                            f"entry_stop_point({next_conveyor_id}).occupied == false",
                            f"downstream_available({current_conveyor_id}) == true",
                        ],
                        "any": [],
                        "none": [],
                    },
                    "policy": {"policy_id": "downstream_release", "inputs": {"from_conveyor_id": current_conveyor_id, "to_conveyor_id": next_conveyor_id, "material_id": "pallet_1"}},
                    "action": {"type": "start_behavior", "instance_id": next_conveyor_id, "behavior_id": "transport_to_exit", "payload": {"carrier_id": "pallet_1", "from_conveyor_id": current_conveyor_id, "transport_model": "stop_point_buffered_transport"}},
                }
                for current_conveyor_id, next_conveyor_id in zip(main_conveyor_ids, main_conveyor_ids[1:])
            ],
            {
                "rule_id": "accept_material_to_first_available_stop_point",
                "module_id": "output_conveying",
                "description": "物料进入传送带时，先放入入口侧可用停留点；没有可用点则进入等待队列。",
                "trigger": {"type": "event", "event_id": "output_conveyor.material_arrived"},
                "guard": {"all": ["conveyor_loads[trigger.payload.conveyor_id].current_load < conveyor_loads[trigger.payload.conveyor_id].max_capacity"], "any": [], "none": []},
                "policy": {"policy_id": "conveyor_stop_point_selection", "inputs": {"conveyor_id": "trigger.payload.conveyor_id", "material_id": "trigger.payload.material_id"}, "bind_outputs_to": {"point_id": "action.payload.point_id"}},
                "action": {"type": "start_behavior", "instance_id": "trigger.payload.conveyor_id", "behavior_id": "accept_material", "payload": {"material_id": "trigger.payload.material_id", "point_id": "policy.point_id"}},
            },
            {
                "rule_id": "advance_material_to_next_stop_point",
                "module_id": "output_conveying",
                "description": "停留点被占用后，若下一个停留点可用，则物料继续向出口方向推进。",
                "trigger": {"type": "event", "event_id": "conveyor.stop_point_occupied"},
                "guard": {"all": ["next_stop_point(trigger.payload.conveyor_id, trigger.payload.point_id).occupied == false"], "any": [], "none": ["conveyor_loads[trigger.payload.conveyor_id].blocked == true"]},
                "policy": {"policy_id": "downstream_release", "inputs": {"conveyor_id": "trigger.payload.conveyor_id", "point_id": "trigger.payload.point_id"}},
                "action": {"type": "start_behavior", "instance_id": "trigger.payload.conveyor_id", "behavior_id": "advance_to_next_stop_point", "payload": {"material_id": "trigger.payload.material_id", "from_point_id": "trigger.payload.point_id"}},
            },
            {
                "rule_id": "wait_when_next_stop_point_occupied",
                "module_id": "output_conveying",
                "description": "前方停留点或下游不可用时，物料保持在当前停留点并进入传送带等待队列。",
                "trigger": {"type": "event", "event_id": "conveyor.stop_point_occupied"},
                "guard": {"all": ["next_stop_point(trigger.payload.conveyor_id, trigger.payload.point_id).occupied == true"], "any": ["downstream_available(trigger.payload.conveyor_id) == false"], "none": []},
                "policy": {"policy_id": "conveyor_queue_wait", "inputs": {"conveyor_id": "trigger.payload.conveyor_id", "material_id": "trigger.payload.material_id", "point_id": "trigger.payload.point_id"}},
                "action": {"type": "update_state", "payload": {"append": "conveyor_queues[trigger.payload.conveyor_id].waiting_materials", "material_id": "trigger.payload.material_id"}},
            },
            {
                "rule_id": "release_material_when_downstream_available",
                "module_id": "output_conveying",
                "description": "出口停留点有物料且下游可接收时，从传送带出口释放物料。",
                "trigger": {"type": "scheduler_tick", "state": "exit_stop_point_occupied and downstream_available"},
                "guard": {"all": ["exit_stop_point(trigger.conveyor_id).occupied == true", "downstream_available(trigger.conveyor_id) == true"], "any": [], "none": []},
                "policy": {"policy_id": "downstream_release", "inputs": {"conveyor_id": "trigger.conveyor_id"}},
                "action": {"type": "start_behavior", "instance_id": "trigger.conveyor_id", "behavior_id": "release_material"},
            },
            {
                "rule_id": "emit_blocked_when_no_stop_point_available",
                "module_id": "output_conveying",
                "description": "传送带无可用停留点或达到容量上限时，发出 blocked 事件。",
                "trigger": {"type": "event", "event_id": "output_conveyor.material_arrived"},
                "guard": {"all": [], "any": ["conveyor_loads[trigger.payload.conveyor_id].current_load >= conveyor_loads[trigger.payload.conveyor_id].max_capacity", "no_available_stop_point(trigger.payload.conveyor_id) == true"], "none": []},
                "policy": {"policy_id": "backpressure", "inputs": {"conveyor_id": "trigger.payload.conveyor_id"}},
                "action": {"type": "emit_event", "event_id": "conveyor.blocked", "payload": {"conveyor_id": "trigger.payload.conveyor_id", "reason": "no_stop_point_or_capacity_full"}},
            },
            {
                "rule_id": "emit_capacity_available_when_stop_point_released",
                "module_id": "output_conveying",
                "description": "停留点释放且负载低于恢复阈值时，发出 capacity_available 事件。",
                "trigger": {"type": "event", "event_id": "conveyor.stop_point_released"},
                "guard": {"all": ["conveyor_loads[trigger.payload.conveyor_id].current_load <= conveyor_loads[trigger.payload.conveyor_id].resume_threshold"], "any": [], "none": []},
                "policy": {"policy_id": "backpressure", "inputs": {"conveyor_id": "trigger.payload.conveyor_id"}},
                "action": {"type": "emit_event", "event_id": "conveyor.capacity_available", "payload": {"conveyor_id": "trigger.payload.conveyor_id"}},
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
                "trigger": {"type": "event", "event_id": "conveyor.blocked"},
                "guard": {"all": ["conveyor_loads[trigger.payload.conveyor_id].blocked == true"], "any": [], "none": []},
                "policy": {"policy_id": "backpressure", "inputs": {"conveyor_id": "trigger.payload.conveyor_id"}, "bind_outputs_to": {"target_robots": "action.target"}},
                "action": {"type": "emit_event", "event_id": "robot.pause_pick", "target": "policy.target_robots", "payload": {"reason": "target_conveyor_blocked", "conveyor_id": "trigger.payload.conveyor_id"}},
            },
            {
                "rule_id": "capacity_available_resumes_robot",
                "module_id": "parallel_robot_sorting",
                "description": "出料传送带容量恢复后恢复受影响机械臂。",
                "trigger": {"type": "event", "event_id": "conveyor.capacity_available"},
                "guard": {"all": ["conveyor_loads[trigger.payload.conveyor_id].blocked == false"], "any": [], "none": []},
                "policy": {"policy_id": "backpressure", "inputs": {"conveyor_id": "trigger.payload.conveyor_id"}, "bind_outputs_to": {"target_robots": "action.target"}},
                "action": {"type": "emit_event", "event_id": "robot.resume_pick", "target": "policy.target_robots", "payload": {"conveyor_id": "trigger.payload.conveyor_id"}},
            },
        ]
        main_conveyor_chain = main_conveyor_ids or [main_conveyor]
        transitions = [
            *[
                {"rule_id": f"{conveyor_id}_pallet_transport_start", "on_behavior_start": f"{conveyor_id}.transport_to_exit", "effects": [f"set device_states.{conveyor_id} = moving", f"lock {conveyor_id}.belt_surface", f"set conveyor_occupancy[{conveyor_id}][entry_stop_point] = pallet_1", "emit conveyor.stop_point_occupied"]}
                for conveyor_id in main_conveyor_chain
            ],
            {"rule_id": "conveyor_stop_point_advance", "on_behavior_complete": "*.advance_to_next_stop_point", "effects": ["clear conveyor_occupancy[conveyor_id][from_point_id]", "set conveyor_occupancy[conveyor_id][to_point_id] = material_id", "emit conveyor.stop_point_released", "emit conveyor.stop_point_occupied"]},
            *[
                {"rule_id": f"{conveyor_id}_pallet_transport_complete", "on_behavior_complete": f"{conveyor_id}.transport_to_exit", "effects": [f"move pallet_1 to {conveyor_id}.exit", f"set device_states.{conveyor_id} = idle", f"unlock {conveyor_id}.belt_surface", f"emit {conveyor_id}.pallet_ready with next_conveyor_id={main_conveyor_chain[index + 1] if index + 1 < len(main_conveyor_chain) else ''}"]}
                for index, conveyor_id in enumerate(main_conveyor_chain)
            ],
            {"rule_id": "claim_workpiece", "on_event": "robot.pick_request", "effects": ["PolicyLibrary.claim_workpiece atomically removes next available material from workpiece_pool", "set material_claims[material_id] = robot_id", "emit global.workpiece_claimed"]},
            {"rule_id": "robot_pick_start", "on_behavior_start": "*.pick_and_place", "effects": ["set device_states[robot_id] = busy", "lock robot_id.robot_arm", "lock robot_id.gripper"]},
            {"rule_id": "robot_pick_complete", "on_behavior_complete": "*.pick_and_place", "effects": ["move material_id to target_conveyor.entry", "append material_id to workpiece_pool.completed", "set device_states[robot_id] = idle", "unlock robot_id.gripper", "unlock robot_id.robot_arm", "emit robot.pick_done", "emit output_conveyor.material_arrived"]},
            {"rule_id": "output_material_arrival_updates_load", "on_event": "output_conveyor.material_arrived", "effects": ["increment conveyor_loads[conveyor_id].current_load", "set conveyor_occupancy[conveyor_id][selected_stop_point] = material_id", "emit conveyor.stop_point_occupied", "if current_load >= max_capacity or no_available_stop_point emit conveyor.blocked"]},
            {"rule_id": "conveyor_stop_point_release", "on_behavior_complete": "*.release_material", "effects": ["clear conveyor_occupancy[conveyor_id][exit_stop_point]", "decrement conveyor_loads[conveyor_id].current_load", "emit conveyor.stop_point_released", "if blocked == true and current_load <= resume_threshold emit conveyor.capacity_available"]},
            {"rule_id": "robot_pause", "on_event": "robot.pause_pick", "effects": ["set device_states[robot_id] = waiting_downstream after current safe action boundary"]},
            {"rule_id": "robot_resume", "on_event": "robot.resume_pick", "effects": ["set device_states[robot_id] = idle if robot has no active action"]},
        ]
        completion = [
            "workpiece_pool.remaining_parts.empty == true",
            "active_actions.empty == true",
            "all conveyor_loads current_load == 0",
            "all conveyor_occupancy stop points are empty",
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
