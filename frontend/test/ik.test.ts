import { describe, expect, it } from "vitest";
import { Group, Object3D } from "three";
import { buildIKFromDeviceConfig } from "@/lib/ik";
import type { DeviceConfig } from "@/types/scene";

describe("IK migration", () => {
  it("builds an IK solver from device config and scene nodes", () => {
    const scene = new Group();
    const root = new Object3D();
    root.name = "robot_root";

    const joint1 = new Object3D();
    joint1.name = "joint_1";
    joint1.position.set(1, 0, 0);

    const joint2 = new Object3D();
    joint2.name = "joint_2";
    joint2.position.set(2, 0, 0);

    scene.add(root, joint1, joint2);

    const deviceConfig: DeviceConfig = {
      id: "robot_arm_1",
      type: "robot_arm",
      displayName: "Robot Arm 1",
      description: "test robot arm",
      rootNodeName: "robot_root",
      urdf: {
        endEffectorNodeName: "joint_2",
        joints: [
          { name: "joint_1", nodeName: "joint_1", type: "revolute", axis: { x: 0, y: 1, z: 0 } },
          { name: "joint_2", nodeName: "joint_2", type: "revolute", axis: { x: 0, y: 1, z: 0 } },
        ],
      },
    };

    const built = buildIKFromDeviceConfig(deviceConfig, scene);

    expect(built).not.toBeNull();
    expect(built?.ikChain.urdfJoints).toHaveLength(2);
    expect(built?.ikSolver.target).toBe(built?.ikTarget);
    expect(built?.endEffectorNode?.name).toBe("joint_2");
  });
});
