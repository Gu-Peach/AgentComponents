import { describe, expect, it } from "vitest";
import { buildRuntimeAnimationAction, interpolateWaypoints } from "@/lib/runtime-behavior";
import type { RuntimeBehaviorEvent, SceneDocumentRecord } from "@/types/scene";

const sceneDocument: SceneDocumentRecord = {
  source: { asset_path: "frontend/public/test/scene1/1.glb" },
  instances: [
    {
      instance_id: "main_conveyor_1",
      device_type: "conveyor",
      param_overrides: { speed_mps: 0.25 },
      asset_binding: { glb_node_name: "Conveyor(1)" },
      runtime_geometry: {
        transport_path: {
          waypoints: [
            [2.619, 0.15, -1.197],
            [0.719, 0.15, -1.197],
          ],
          stop_points: [
            { point_id: "main_conveyor_1.sp_01", role: "entry", position: [2.619, 0.15, -1.197] },
            { point_id: "main_conveyor_1.sp_02", role: "middle", position: [1.9857, 0.15, -1.197] },
            { point_id: "main_conveyor_1.sp_03", role: "middle", position: [1.3523, 0.15, -1.197] },
            { point_id: "main_conveyor_1.sp_04", role: "exit", position: [0.719, 0.15, -1.197] },
          ],
        },
      },
    },
    {
      instance_id: "robot_1",
      device_type: "robot_arm",
      param_overrides: { speed: 1.0 },
      asset_binding: { glb_node_name: "robot(center)(1)" },
      runtime_geometry: {
        pick_place_path: {
          waypoints: [
            [-0.649, 0.45, -1.197],
            [-0.649, 0.15, -1.197],
            [-1.093, 0.7, -0.173],
          ],
        },
      },
    },
    {
      instance_id: "pallet_1",
      device_type: "workpiece_carrier",
      asset_binding: { glb_node_name: "Euro Pallet [00Mn]" },
    },
  ],
  materials: [
    { material_id: "part_001", asset_binding: { glb_node_name: "Lathe_Comp_3_00On" } },
  ],
};

describe("runtime behavior mapping", () => {
  it("maps a conveyor behavior event from SceneDocument transport geometry", () => {
    const event: RuntimeBehaviorEvent = {
      type: "device_behavior_triggered",
      run_id: "run_1",
      task_id: "task_1",
      instance_id: "main_conveyor_1",
      behavior_id: "transport_to_exit",
      payload: { carrier_id: "pallet_1" },
    };

    const action = buildRuntimeAnimationAction(event, sceneDocument, 1000);

    expect(action?.actionId).toBe("task_1");
    expect(action?.kind).toBe("conveyor_linear");
    expect(action?.subjectId).toBe("pallet_1");
    expect(action?.waypoints).toEqual([
      { x: 2.619, y: 0.15, z: -1.197 },
      { x: 0.719, y: 0.15, z: -1.197 },
    ]);
    expect(action?.duration).toBeCloseTo(7.6);
  });

  it("maps conveyor stop-point actions to the requested segment", () => {
    const event: RuntimeBehaviorEvent = {
      type: "device_behavior_triggered",
      run_id: "run_1",
      action_id: "act_1",
      instance_id: "main_conveyor_1",
      behavior_id: "advance_to_next_stop_point",
      payload: {
        carrier_id: "pallet_1",
        from_point_id: "main_conveyor_1.sp_02",
        to_point_id: "main_conveyor_1.sp_03",
      },
    };

    const action = buildRuntimeAnimationAction(event, sceneDocument, 1000);

    expect(action?.actionId).toBe("act_1");
    expect(action?.waypoints).toEqual([
      { x: 1.9857, y: 0.15, z: -1.197 },
      { x: 1.3523, y: 0.15, z: -1.197 },
    ]);
    expect(action?.duration).toBeCloseTo(2.5336);
  });

  it("maps a robot behavior event from SceneDocument pick-place geometry", () => {
    const event: RuntimeBehaviorEvent = {
      type: "device_behavior_triggered",
      run_id: "run_1",
      action_id: "act_1",
      instance_id: "robot_1",
      behavior_id: "pick_and_place",
      payload: { material_id: "part_001" },
    };

    const action = buildRuntimeAnimationAction(event, sceneDocument, 1000);

    expect(action?.actionId).toBe("act_1");
    expect(action?.kind).toBe("robot_pick_place");
    expect(action?.subjectId).toBe("part_001");
    expect(action?.waypoints).toEqual([
      { x: -0.649, y: 0.45, z: -1.197 },
      { x: -0.649, y: 0.15, z: -1.197 },
      { x: -1.093, y: 0.7, z: -0.173 },
    ]);
    expect(action?.payload.runtime_geometry).toBeTruthy();
  });

  it("does not create a runtime action when SceneDocument runtime geometry is missing", () => {
    const event: RuntimeBehaviorEvent = {
      type: "device_behavior_triggered",
      instance_id: "robot_1",
      behavior_id: "pick_and_place",
      payload: { material_id: "part_001" },
    };

    const action = buildRuntimeAnimationAction(event, {
      instances: [{ instance_id: "robot_1", device_type: "robot_arm", asset_binding: { glb_node_name: "robot(center)(1)" } }],
      materials: [{ material_id: "part_001", asset_binding: { glb_node_name: "Lathe_Comp_3_00On" } }],
    });

    expect(action).toBeNull();
  });

  it("does not turn robot control signals into animation actions", () => {
    const event: RuntimeBehaviorEvent = {
      type: "device_behavior_triggered",
      instance_id: "robot_1",
      behavior_id: "pause_pick",
      payload: { reason: "output blocked" },
    };

    expect(buildRuntimeAnimationAction(event, sceneDocument)).toBeNull();
  });

  it("interpolates multi-point paths by path length", () => {
    const position = interpolateWaypoints(
      [
        { x: 0, y: 0, z: 0 },
        { x: 2, y: 0, z: 0 },
        { x: 2, y: 0, z: 2 },
      ],
      0.75,
    );

    expect(position).toEqual({ x: 2, y: 0, z: 1 });
  });
});
