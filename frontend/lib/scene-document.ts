import type { DeviceType, SceneAssetBinding, SceneDocumentRecord, SceneObject, Vector3Tuple } from "@/types/scene";

const ASSET_BY_TYPE: Record<string, string> = {
  conveyor: "asset_conveyor",
  robot_arm: "asset_robot_arm",
  workpiece_carrier: "asset_carrier",
  workpiece: "asset_workpiece",
  material_source_station: "asset_source_station",
  lift_table: "asset_lift_table",
  storage_rack: "asset_storage_rack",
  rotary_table: "asset_rotary_table",
};

const COLOR_BY_TYPE: Record<string, string> = {
  conveyor: "#1f87c9",
  robot_arm: "#f2f4f8",
  workpiece_carrier: "#7d8793",
  workpiece: "#f0b84f",
  material_source_station: "#49a971",
  lift_table: "#9c6ade",
  storage_rack: "#6d91b8",
  rotary_table: "#d18d5f",
};

const DIMENSIONS_BY_TYPE: Record<string, Vector3Tuple> = {
  conveyor: [3.2, 0.28, 0.78],
  robot_arm: [0.9, 1.8, 0.9],
  workpiece_carrier: [1.15, 0.18, 0.76],
  workpiece: [0.22, 0.22, 0.22],
  material_source_station: [1.2, 0.8, 1.0],
  lift_table: [1.1, 1.2, 1.1],
  storage_rack: [1.4, 1.8, 0.6],
  rotary_table: [1.25, 0.32, 1.25],
};

export function sceneDocumentToSceneObjects(document: SceneDocumentRecord): SceneObject[] {
  const instances = readArray(document.instances).map(instanceToSceneObject).filter((item): item is SceneObject => item !== null);
  const materials = readArray(document.materials).map(materialToSceneObject).filter((item): item is SceneObject => item !== null);
  return [...instances, ...materials];
}

function instanceToSceneObject(instance: SceneDocumentRecord): SceneObject | null {
  const id = readString(instance.instance_id);
  const type = readString(instance.device_type) ?? "workpiece";
  if (!id) return null;

  const transform = readRecord(instance.transform);
  const assetBinding = readRecord(instance.asset_binding);
  const runtimeGeometry = readRecord(instance.runtime_geometry);
  const runtimeKinematics = readRecord(instance.runtime_kinematics);
  return {
    id,
    assetId: ASSET_BY_TYPE[type] ?? `asset_${type}`,
    name: readString(instance.display_name) ?? id,
    type: toDeviceType(type),
    description: readString(instance.description) ?? `${type} scene instance`,
    transform: {
      position: readVector(transform?.position) ?? [0, 0, 0],
      rotation: readVector(transform?.rotation_euler) ?? readVector(transform?.rotation) ?? [0, 0, 0],
      scale: readVector(transform?.scale) ?? [1, 1, 1],
    },
    dimensions: readVector(readRecord(instance.param_overrides)?.dimensions) ?? DIMENSIONS_BY_TYPE[type] ?? [1, 1, 1],
    color: COLOR_BY_TYPE[type] ?? "#8a94a6",
    createdFrom: "SceneDocument",
    assetBinding: assetBinding ? ({ ...assetBinding } as SceneAssetBinding) : undefined,
    glbNodeName: readString(assetBinding?.glb_node_name) ?? undefined,
    runtimeGeometry: runtimeGeometry ? { ...runtimeGeometry } : undefined,
    runtimeKinematics: runtimeKinematics ? { ...runtimeKinematics } : undefined,
  };
}

function materialToSceneObject(material: SceneDocumentRecord): SceneObject | null {
  const id = readString(material.material_id);
  if (!id) return null;
  const binding = readRecord(material.asset_binding);
  return {
    id,
    assetId: ASSET_BY_TYPE.workpiece,
    name: id,
    type: "workpiece",
    description: readString(material.located_at) ? `located at ${readString(material.located_at)}` : "scene material",
    transform: {
      position: readVector(binding?.parsed_glb_y_up_world_position) ?? readVector(readRecord(binding?.parsed_glb_y_up)?.world_position) ?? [0, 0.35, 0],
      rotation: [0, 0, 0],
      scale: [1, 1, 1],
    },
    dimensions: DIMENSIONS_BY_TYPE.workpiece,
    color: COLOR_BY_TYPE.workpiece,
    createdFrom: "SceneDocument.materials",
    assetBinding: binding ? ({ ...binding } as SceneAssetBinding) : undefined,
    glbNodeName: readString(binding?.glb_node_name) ?? undefined,
  };
}

function toDeviceType(value: string): DeviceType {
  if (["robot_arm", "conveyor", "workpiece", "workpiece_carrier", "material_source_station", "lift_table", "storage_rack", "rotary_table"].includes(value)) {
    return value as DeviceType;
  }
  return "workpiece";
}

function readArray(value: unknown): SceneDocumentRecord[] {
  return Array.isArray(value) ? value.filter((item): item is SceneDocumentRecord => typeof item === "object" && item !== null && !Array.isArray(item)) : [];
}

function readRecord(value: unknown): SceneDocumentRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as SceneDocumentRecord : null;
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function readVector(value: unknown): Vector3Tuple | null {
  if (!Array.isArray(value) || value.length < 3) return null;
  const vector = value.slice(0, 3).map(Number);
  return vector.every(Number.isFinite) ? vector as Vector3Tuple : null;
}
