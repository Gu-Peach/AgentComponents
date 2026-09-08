import { Object3D, PropertyBinding, Vector3 } from "three";
import { buildIKFromDeviceConfig, type BuiltIKResult } from "@/lib/ik";
import { interpolateWaypoints } from "@/lib/runtime-behavior";
import type {
  DeviceConfig,
  RuntimeAnimationAction,
  RuntimeDeviceVisualState,
  RuntimeVector3,
  SceneDocumentRecord,
  Transform3D,
  UrdfJointConfig,
  Vector3Tuple,
} from "@/types/scene";

export interface GlbRuntimeBindings {
  assetUrl: string | null;
  instances: Map<string, SceneDocumentRecord>;
  materials: Map<string, SceneDocumentRecord>;
  nodeNameByObjectId: Map<string, string>;
  robotConfigByInstanceId: Map<string, DeviceConfig>;
}

export interface GlbRuntimeCallbackResult {
  subjectTransform?: {
    objectId: string;
    transform: Partial<Transform3D>;
  };
  deviceVisual: RuntimeDeviceVisualState;
}

export interface GlbActionRuntime {
  update(progress: number): GlbRuntimeCallbackResult;
  dispose(): void;
}

export function buildGlbRuntimeBindings(document: SceneDocumentRecord | null): GlbRuntimeBindings {
  const instances = new Map<string, SceneDocumentRecord>();
  const materials = new Map<string, SceneDocumentRecord>();
  const nodeNameByObjectId = new Map<string, string>();
  const robotConfigByInstanceId = new Map<string, DeviceConfig>();
  let assetUrl = sceneDocumentAssetUrl(document);

  if (!document) {
    return { assetUrl: null, instances, materials, nodeNameByObjectId, robotConfigByInstanceId };
  }

  for (const instance of readArray(document.instances)) {
    const instanceId = readString(instance.instance_id);
    if (!instanceId) continue;
    instances.set(instanceId, instance);

    const binding = readRecord(instance.asset_binding);
    const nodeName = readString(binding?.glb_node_name);
    if (nodeName) nodeNameByObjectId.set(instanceId, nodeName);
    assetUrl ??= publicUrlFromAssetPath(readString(binding?.asset_path));

    const config = deviceConfigFromSceneInstance(instance);
    if (config) robotConfigByInstanceId.set(instanceId, config);
  }

  for (const material of readArray(document.materials)) {
    const materialId = readString(material.material_id);
    if (!materialId) continue;
    materials.set(materialId, material);

    const binding = readRecord(material.asset_binding);
    const nodeName = readString(binding?.glb_node_name);
    if (nodeName) nodeNameByObjectId.set(materialId, nodeName);
    assetUrl ??= publicUrlFromAssetPath(readString(binding?.asset_path));
  }

  return { assetUrl, instances, materials, nodeNameByObjectId, robotConfigByInstanceId };
}

export function sceneDocumentAssetUrl(document: SceneDocumentRecord | null): string | null {
  const source = readRecord(document?.source);
  return publicUrlFromAssetPath(readString(source?.asset_path));
}

export function findRenderableGlbObjectIds(bindings: GlbRuntimeBindings, scene: Object3D): string[] {
  const ids: string[] = [];
  for (const [objectId, nodeName] of bindings.nodeNameByObjectId.entries()) {
    if (!findObjectByBoundName(scene, nodeName)) continue;

    const robotConfig = bindings.robotConfigByInstanceId.get(objectId);
    if (robotConfig && !canResolveRobotConfig(robotConfig, scene)) continue;

    ids.push(objectId);
  }
  return ids;
}

export function createGlbActionRuntime(
  action: RuntimeAnimationAction,
  scene: Object3D,
  bindings: GlbRuntimeBindings,
): GlbActionRuntime | null {
  if (action.kind === "robot_pick_place") {
    const config = bindings.robotConfigByInstanceId.get(action.instanceId) ?? deviceConfigFromRuntimePayload(action);
    if (!config) return null;
    const built = buildIKFromDeviceConfig(config, scene);
    if (!built) return null;
    const subject = resolveSubjectNode(action, scene, bindings);
    return new RobotGlbActionRuntime(action, scene, built, subject);
  }

  const subject = resolveSubjectNode(action, scene, bindings);
  if (!subject) return null;
  return new ConveyorGlbActionRuntime(action, scene, subject);
}

function deviceConfigFromRuntimePayload(action: RuntimeAnimationAction): DeviceConfig | null {
  const sceneInstance = readRecord(action.payload.scene_instance);
  const instance: SceneDocumentRecord = {
    instance_id: action.instanceId,
    device_type: action.payload.device_type ?? "robot_arm",
    display_name: action.instanceId,
    runtime_kinematics: action.payload.runtime_kinematics,
    asset_binding: sceneInstance?.asset_binding,
  };
  return deviceConfigFromSceneInstance(instance);
}

function deviceConfigFromSceneInstance(instance: SceneDocumentRecord): DeviceConfig | null {
  const instanceId = readString(instance.instance_id);
  const runtimeKinematics = readRecord(instance.runtime_kinematics);
  const chain = readRecord(runtimeKinematics?.kinematic_chain);
  if (!instanceId || !chain) return null;

  const joints = readArray(chain.joints).map(jointConfigFromRecord).filter((joint): joint is UrdfJointConfig => joint !== null);
  if (joints.length === 0) return null;

  const binding = readRecord(instance.asset_binding);
  const rootNodeName = readString(chain.root_node_name) ?? readString(chain.rootNodeName) ?? readString(binding?.glb_node_name);
  if (!rootNodeName) return null;

  const endEffectorNodeName = readString(chain.end_effector_node_name) ?? readString(chain.endEffectorNodeName);

  return {
    id: instanceId,
    type: readString(instance.device_type) ?? "robot_arm",
    displayName: readString(instance.display_name) ?? instanceId,
    description: readString(instance.description) ?? `${instanceId} runtime kinematic chain`,
    rootNodeName,
    urdf: {
      joints,
      endEffectorNodeName: endEffectorNodeName ?? joints[joints.length - 1]?.nodeName,
    },
  };
}

function jointConfigFromRecord(record: SceneDocumentRecord): UrdfJointConfig | null {
  const name = readString(record.name);
  const nodeName = readString(record.nodeName) ?? readString(record.node_name);
  const axis = readAxis(record.axis);
  if (!name || !nodeName || !axis) return null;

  const limit = readRecord(record.limit);
  return {
    name,
    nodeName,
    type: readString(record.type) ?? "revolute",
    axis,
    limit: limit
      ? {
          lower: Number(limit.lower ?? -Math.PI),
          upper: Number(limit.upper ?? Math.PI),
        }
      : undefined,
  };
}

function canResolveRobotConfig(config: DeviceConfig, scene: Object3D): boolean {
  if (!findObjectByBoundName(scene, config.rootNodeName)) return false;
  return (config.urdf?.joints ?? []).every((joint) => Boolean(findObjectByBoundName(scene, joint.nodeName)));
}

class ConveyorGlbActionRuntime implements GlbActionRuntime {
  constructor(
    private readonly action: RuntimeAnimationAction,
    private readonly scene: Object3D,
    private readonly subjectNode: Object3D,
  ) {
    attachToSceneRoot(scene, subjectNode);
  }

  update(progress: number): GlbRuntimeCallbackResult {
    const position = interpolateWaypoints(this.action.waypoints, progress);
    setWorldPosition(this.subjectNode, position);
    return {
      subjectTransform: this.action.subjectId ? { objectId: this.action.subjectId, transform: { position: tuple(position) } } : undefined,
      deviceVisual: {
        activeActionId: this.action.actionId,
        beltOffset: (progress * 6) % 1,
      },
    };
  }

  dispose(): void {
    // Keep the material at its final world pose; the next runtime event becomes the new source of truth.
  }
}

class RobotGlbActionRuntime implements GlbActionRuntime {
  constructor(
    private readonly action: RuntimeAnimationAction,
    private readonly scene: Object3D,
    private readonly built: BuiltIKResult,
    private readonly subjectNode: Object3D | null,
  ) {
    scene.add(built.containerGroup);
    if (subjectNode) attachToSceneRoot(scene, subjectNode);
  }

  update(progress: number): GlbRuntimeCallbackResult {
    const position = interpolateWaypoints(this.action.waypoints, progress);
    this.built.ikTarget.position.set(position.x, position.y, position.z);
    this.built.ikSolver.solve();

    if (this.subjectNode) {
      setWorldPosition(this.subjectNode, position);
    }

    return {
      subjectTransform: this.action.subjectId ? { objectId: this.action.subjectId, transform: { position: tuple(position) } } : undefined,
      deviceVisual: {
        activeActionId: this.action.actionId,
        armPhase: progress < 0.18 ? "approach" : progress < 0.82 ? "execute" : "return",
        gripperClosed: progress >= 0.22 && progress <= 0.78,
      },
    };
  }

  dispose(): void {
    this.scene.remove(this.built.containerGroup);
  }
}

function resolveSubjectNode(action: RuntimeAnimationAction, scene: Object3D, bindings: GlbRuntimeBindings): Object3D | null {
  for (const nodeName of subjectNodeNameCandidates(action, bindings)) {
    const node = findObjectByBoundName(scene, nodeName);
    if (node) return node;
  }
  return null;
}

function subjectNodeNameCandidates(action: RuntimeAnimationAction, bindings: GlbRuntimeBindings): string[] {
  const names: string[] = [];
  for (const directKey of ["subject_node_name", "glb_node_name", "object_node_name", "material_node_name"]) {
    const value = readString(action.payload[directKey]);
    if (value) names.push(...gltfNodeNameCandidates(value));
  }

  for (const objectId of subjectIdCandidates(action)) {
    const nodeName = bindings.nodeNameByObjectId.get(objectId);
    if (nodeName) names.push(...gltfNodeNameCandidates(nodeName));
  }

  return Array.from(new Set(names));
}

function findObjectByBoundName(scene: Object3D, boundName: string): Object3D | null {
  for (const name of gltfNodeNameCandidates(boundName)) {
    const node = scene.getObjectByName(name);
    if (node) return node;
  }
  return null;
}

function gltfNodeNameCandidates(boundName: string): string[] {
  return Array.from(new Set([boundName, PropertyBinding.sanitizeNodeName(boundName)].filter(Boolean)));
}

function subjectIdCandidates(action: RuntimeAnimationAction): string[] {
  const ids = [action.subjectId];
  for (const key of ["subject_id", "object_id", "carrier_id", "workpiece_id", "material_id"]) {
    ids.push(readString(action.payload[key]));
  }
  return Array.from(new Set(ids.filter((id): id is string => Boolean(id))));
}

function attachToSceneRoot(scene: Object3D, node: Object3D): void {
  if (node.parent && node.parent !== scene) {
    scene.attach(node);
  }
}

function setWorldPosition(node: Object3D, position: RuntimeVector3): void {
  const world = new Vector3(position.x, position.y, position.z);
  if (node.parent) {
    node.parent.updateWorldMatrix(true, false);
    node.position.copy(node.parent.worldToLocal(world));
  } else {
    node.position.copy(world);
  }
  node.updateMatrixWorld(true);
}

function tuple(position: RuntimeVector3): Vector3Tuple {
  return [round(position.x), round(position.y), round(position.z)];
}

function round(value: number): number {
  return Number(value.toFixed(4));
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

function readAxis(value: unknown): { x: number; y: number; z: number } | null {
  if (Array.isArray(value) && value.length >= 3) {
    const [x, y, z] = value.map(Number);
    return [x, y, z].every(Number.isFinite) ? { x, y, z } : null;
  }

  const record = readRecord(value);
  if (!record) return null;
  const x = Number(record.x);
  const y = Number(record.y);
  const z = Number(record.z);
  return [x, y, z].every(Number.isFinite) ? { x, y, z } : null;
}

function publicUrlFromAssetPath(path: string | null): string | null {
  if (!path) return null;
  const normalized = path.replace(/\\/g, "/");
  if (normalized.startsWith("/")) return normalized;
  const publicMarker = "frontend/public/";
  const publicIndex = normalized.indexOf(publicMarker);
  if (publicIndex >= 0) return `/${normalized.slice(publicIndex + publicMarker.length)}`;
  return `/${normalized}`;
}
