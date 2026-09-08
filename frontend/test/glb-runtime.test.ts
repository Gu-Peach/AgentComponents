import { describe, expect, it } from "vitest";
import { Object3D } from "three";
import { buildGlbRuntimeBindings, createGlbActionRuntime, findRenderableGlbObjectIds } from "@/lib/glb-runtime";
import type { RuntimeAnimationAction } from "@/types/scene";

describe("glb runtime bindings", () => {
  it("indexes scene instance and material GLB node bindings", () => {
    const bindings = buildGlbRuntimeBindings({
      source: { asset_path: "frontend/public/test/scene1/1.glb" },
      instances: [
        {
          instance_id: "robot_1",
          device_type: "robot_arm",
          asset_binding: { glb_node_name: "robot(center)(1)" },
          runtime_kinematics: {
            kinematic_chain: {
              root_node_name: "Link1_00dn",
              end_effector_node_name: "Axis_6_00kn",
              joints: [
                { name: "joint_1", nodeName: "Axis_1_00fn", type: "revolute", axis: { x: 0, y: 1, z: 0 } },
              ],
            },
          },
        },
      ],
      materials: [
        { material_id: "part_001", asset_binding: { glb_node_name: "Lathe_Comp_3_00On" } },
      ],
    });

    expect(bindings.assetUrl).toBe("/test/scene1/1.glb");
    expect(bindings.nodeNameByObjectId.get("robot_1")).toBe("robot(center)(1)");
    expect(bindings.nodeNameByObjectId.get("part_001")).toBe("Lathe_Comp_3_00On");
    expect(bindings.robotConfigByInstanceId.get("robot_1")?.rootNodeName).toBe("Link1_00dn");
  });

  it("drives a bound GLB subject node for conveyor actions", () => {
    const scene = new Object3D();
    const palletNode = new Object3D();
    palletNode.name = "Euro Pallet [00Mn]";
    scene.add(palletNode);

    const bindings = buildGlbRuntimeBindings({
      source: { asset_path: "frontend/public/test/scene1/1.glb" },
      instances: [
        { instance_id: "pallet_1", asset_binding: { glb_node_name: "Euro Pallet [00Mn]" } },
      ],
    });
    const action: RuntimeAnimationAction = {
      actionId: "task_1",
      instanceId: "main_conveyor_1",
      behaviorId: "transport_to_exit",
      kind: "conveyor_linear",
      subjectId: "pallet_1",
      waypoints: [{ x: 0, y: 0, z: 0 }, { x: 2, y: 0.5, z: -1 }],
      duration: 2,
      elapsed: 0,
      startedAt: 0,
      payload: { carrier_id: "pallet_1" },
      status: "running",
    };

    const runtime = createGlbActionRuntime(action, scene, bindings);
    const result = runtime?.update(0.5);

    expect(runtime).toBeTruthy();
    expect(palletNode.position.toArray()).toEqual([1, 0.25, -0.5]);
    expect(result?.subjectTransform?.transform.position).toEqual([1, 0.25, -0.5]);
  });

  it("only marks objects renderable when their GLB nodes exist", () => {
    const scene = new Object3D();
    const conveyorNode = new Object3D();
    conveyorNode.name = "Conveyor(1)";
    scene.add(conveyorNode);

    const bindings = buildGlbRuntimeBindings({
      source: { asset_path: "frontend/public/test/scene1/1.glb" },
      instances: [
        { instance_id: "main_conveyor_1", asset_binding: { glb_node_name: "Conveyor(1)" } },
        { instance_id: "missing_conveyor", asset_binding: { glb_node_name: "Conveyor(missing)" } },
      ],
    });

    expect(findRenderableGlbObjectIds(bindings, scene)).toEqual(["main_conveyor_1"]);
  });
});
