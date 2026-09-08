import { describe, expect, it } from "vitest";
import { mockInitialSceneObjects } from "@/mocks/catalog";
import { buildRuntimeAnimationAction, interpolateWaypoints } from "@/lib/runtime-behavior";
import type { RuntimeBehaviorEvent } from "@/types/scene";

describe("runtime behavior mapping", () => {
  it("maps a conveyor behavior event to a linear animation action", () => {
    const event: RuntimeBehaviorEvent = {
      type: "device_behavior_triggered",
      run_id: "run_1",
      task_id: "task_1",
      instance_id: "main_conveyor_1",
      behavior_id: "transport_to_exit",
      payload: { carrier_id: "carrier_tray_1" },
    };

    const action = buildRuntimeAnimationAction(event, mockInitialSceneObjects, 1000);

    expect(action?.actionId).toBe("task_1");
    expect(action?.kind).toBe("conveyor_linear");
    expect(action?.subjectId).toBe("carrier_tray_1");
    expect(action?.waypoints).toHaveLength(2);
    expect(action?.duration).toBeGreaterThan(1);
  });

  it("maps a robot behavior event to a pick-and-place animation action", () => {
    const event: RuntimeBehaviorEvent = {
      type: "device_behavior_triggered",
      run_id: "run_1",
      action_id: "act_1",
      instance_id: "robot_arm_1",
      behavior_id: "pick_and_place",
      payload: {
        material_id: "carrier_tray_1",
        target_conveyor_id: "output_conveyor_top",
      },
    };

    const action = buildRuntimeAnimationAction(event, mockInitialSceneObjects, 1000);

    expect(action?.actionId).toBe("act_1");
    expect(action?.kind).toBe("robot_pick_place");
    expect(action?.subjectId).toBe("carrier_tray_1");
    expect(action?.waypoints.length).toBeGreaterThanOrEqual(4);
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
