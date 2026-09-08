import { describe, expect, it } from "vitest";
import { sceneDocumentToSceneObjects } from "@/lib/scene-document";

describe("scene document adapter", () => {
  it("converts scene instances and materials into frontend scene objects", () => {
    const objects = sceneDocumentToSceneObjects({
      instances: [
        {
          instance_id: "robot_1",
          device_type: "robot_arm",
          display_name: "Robot 1",
          transform: { position: [1, 2, 3], rotation_euler: [0, 90, 0], scale: [1, 1, 1] },
        },
      ],
      materials: [
        {
          material_id: "part_001",
          located_at: "pallet_1.slot_01",
          asset_binding: { parsed_glb_y_up_world_position: [4, 5, 6] },
        },
      ],
    });

    expect(objects.map((object) => object.id)).toEqual(["robot_1", "part_001"]);
    expect(objects[0].transform.position).toEqual([1, 2, 3]);
    expect(objects[0].transform.rotation).toEqual([0, 90, 0]);
    expect(objects[1].transform.position).toEqual([4, 5, 6]);
  });
});
