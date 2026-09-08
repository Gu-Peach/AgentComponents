import type {
  RuntimeAnimationAction,
  RuntimeBehaviorEvent,
  RuntimeVector3,
  SceneDocumentRecord,
} from "@/types/scene";

const CONVEYOR_BEHAVIORS = new Set([
  "transport_to_exit",
  "advance_to_next_stop_point",
  "accept_material",
  "release_material",
]);
const ROBOT_BEHAVIORS = new Set(["pick_and_place"]);
const MIN_CONVEYOR_DURATION = 1.4;
const MIN_ROBOT_DURATION = 2.2;

export function buildRuntimeAnimationAction(
  event: RuntimeBehaviorEvent,
  sceneDocument: SceneDocumentRecord | null,
  now = Date.now(),
): RuntimeAnimationAction | null {
  if (!sceneDocument) return null;

  const instance = findInstance(sceneDocument, event.instance_id);
  if (!instance) return null;

  const payload = enrichPayloadWithSceneInstance(event.payload ?? {}, instance);
  const actionId = actionRefFromEvent(event) ?? `runtime_${now}`;

  if (ROBOT_BEHAVIORS.has(event.behavior_id)) {
    const waypoints = resolveRobotWaypoints(instance, payload);
    const duration = resolveDuration(payload, instance, waypoints, ["speed", "speed_mps"], MIN_ROBOT_DURATION);
    if (waypoints.length < 2 || duration === null) return null;
    return {
      actionId,
      eventId: event.event_id,
      taskId: event.task_id,
      runId: event.run_id,
      instanceId: event.instance_id,
      behaviorId: event.behavior_id,
      kind: "robot_pick_place",
      subjectId: resolveSubjectId(payload, sceneDocument),
      waypoints,
      duration,
      elapsed: 0,
      startedAt: now,
      payload,
      status: "running",
    };
  }

  if (CONVEYOR_BEHAVIORS.has(event.behavior_id)) {
    const subjectId = resolveSubjectId(payload, sceneDocument);
    if (!subjectId) return null;

    const waypoints = resolveConveyorWaypoints(instance, payload, event.behavior_id);
    const duration = resolveDuration(payload, instance, waypoints, ["speed_mps", "speed"], MIN_CONVEYOR_DURATION);
    if (waypoints.length < 2 || duration === null) return null;
    return {
      actionId,
      eventId: event.event_id,
      taskId: event.task_id,
      runId: event.run_id,
      instanceId: event.instance_id,
      behaviorId: event.behavior_id,
      kind: "conveyor_linear",
      subjectId,
      waypoints,
      duration,
      elapsed: 0,
      startedAt: now,
      payload,
      status: "running",
    };
  }

  return null;
}

export function interpolateWaypoints(waypoints: RuntimeVector3[], progress: number): RuntimeVector3 {
  if (waypoints.length === 0) return { x: 0, y: 0, z: 0 };
  if (waypoints.length === 1) return waypoints[0];

  const total = pathLength(waypoints);
  if (total <= 0) return waypoints[waypoints.length - 1];

  let remaining = total * clamp01(progress);
  for (let index = 0; index < waypoints.length - 1; index += 1) {
    const start = waypoints[index];
    const end = waypoints[index + 1];
    const length = distance(start, end);
    if (remaining <= length || index === waypoints.length - 2) {
      const t = length <= 0 ? 1 : remaining / length;
      return lerp(start, end, t);
    }
    remaining -= length;
  }

  return waypoints[waypoints.length - 1];
}

export function actionRefFromEvent(event: RuntimeBehaviorEvent): string | null {
  return event.action_id ?? event.task_id ?? event.event_id ?? null;
}

function resolveConveyorWaypoints(instance: SceneDocumentRecord, payload: Record<string, unknown>, behaviorId: string): RuntimeVector3[] {
  const transportPath = runtimeGeometryPath(instance, payload, "transport_path");
  const stopPointWaypoints = resolveStopPointWaypoints(transportPath, payload, behaviorId);
  if (stopPointWaypoints.length >= 2) return stopPointWaypoints;

  const waypoints = readWaypoints(transportPath);
  if (waypoints.length >= 2) return waypoints;

  const start = readVector(transportPath?.start_position);
  const end = readVector(transportPath?.end_position);
  return start && end ? [start, end] : [];
}

function resolveStopPointWaypoints(
  transportPath: SceneDocumentRecord | null,
  payload: Record<string, unknown>,
  behaviorId: string,
): RuntimeVector3[] {
  if (!transportPath) return [];

  const fromPointId = readFirstString(payload, ["from_point_id", "from_stop_point_id"]);
  const toPointId = readFirstString(payload, ["to_point_id", "to_stop_point_id", "target_stop_point_id"]);
  const pointId = readString(payload.point_id);
  const from = fromPointId ? readStopPointPosition(transportPath, fromPointId) : null;
  const to = toPointId ? readStopPointPosition(transportPath, toPointId) : null;
  if (from && to) return [from, to];

  if (behaviorId === "accept_material" && to) {
    const start = readVector(transportPath.start_position) ?? to;
    return [start, to];
  }

  if (behaviorId === "release_material") {
    const releaseFrom = from ?? (pointId ? readStopPointPosition(transportPath, pointId) : null);
    if (releaseFrom) {
      const end = readVector(transportPath.end_position) ?? releaseFrom;
      return [releaseFrom, end];
    }
  }

  return [];
}

function resolveRobotWaypoints(instance: SceneDocumentRecord, payload: Record<string, unknown>): RuntimeVector3[] {
  const pickPlacePath = runtimeGeometryPath(instance, payload, "pick_place_path");
  const waypoints = readWaypoints(pickPlacePath);
  if (waypoints.length >= 2) return waypoints;

  const pick = readFirstVector(pickPlacePath, ["pick_position", "from_position", "source_position"]);
  const place = readFirstVector(pickPlacePath, ["place_position", "to_position", "target_position", "destination_position"]);
  if (!pick || !place) return [];

  const liftHeight = numberFrom(pickPlacePath?.approach_height) ?? numberFrom(pickPlacePath?.lift_height) ?? 0;
  const pickAbove = { ...pick, y: pick.y + liftHeight };
  const placeAbove = { ...place, y: place.y + liftHeight };
  return [pickAbove, pick, pickAbove, placeAbove, place, placeAbove];
}

function runtimeGeometryPath(
  instance: SceneDocumentRecord,
  payload: Record<string, unknown>,
  pathKey: "transport_path" | "pick_place_path",
): SceneDocumentRecord | null {
  const instancePath = readRecord(readRecord(instance.runtime_geometry)?.[pathKey]);
  if (instancePath) return instancePath;
  return readRecord(readRecord(payload.runtime_geometry)?.[pathKey]);
}

function resolveSubjectId(payload: Record<string, unknown>, sceneDocument: SceneDocumentRecord): string | null {
  for (const key of ["subject_id", "object_id", "carrier_id", "workpiece_id", "material_id"]) {
    const value = readString(payload[key]);
    if (!value) continue;

    const sceneObject = findInstance(sceneDocument, value) ?? findMaterial(sceneDocument, value);
    if (sceneObject && hasGlbBinding(sceneObject)) return value;
  }

  return null;
}

function enrichPayloadWithSceneInstance(
  rawPayload: Record<string, unknown>,
  instance: SceneDocumentRecord,
): Record<string, unknown> {
  const payload = { ...rawPayload };
  const paramOverrides = readRecord(instance.param_overrides);
  if (paramOverrides) {
    for (const [key, value] of Object.entries(paramOverrides)) {
      payload[key] ??= cloneJsonValue(value);
    }
  }

  if (instance.runtime_geometry) payload.runtime_geometry = cloneJsonValue(instance.runtime_geometry);
  if (instance.runtime_kinematics) payload.runtime_kinematics = cloneJsonValue(instance.runtime_kinematics);
  payload.scene_instance = {
    instance_id: instance.instance_id,
    spec_id: instance.spec_id,
    device_type: instance.device_type,
    transform: cloneJsonValue(instance.transform),
    asset_binding: cloneJsonValue(instance.asset_binding),
  };
  return payload;
}

function findInstance(sceneDocument: SceneDocumentRecord, instanceId: string): SceneDocumentRecord | null {
  return readArray(sceneDocument.instances).find((item) => item.instance_id === instanceId) ?? null;
}

function findMaterial(sceneDocument: SceneDocumentRecord, materialId: string): SceneDocumentRecord | null {
  return readArray(sceneDocument.materials).find((item) => item.material_id === materialId) ?? null;
}

function hasGlbBinding(record: SceneDocumentRecord): boolean {
  return Boolean(readString(readRecord(record.asset_binding)?.glb_node_name));
}

function readWaypoints(source: SceneDocumentRecord | null): RuntimeVector3[] {
  const raw = source?.waypoints;
  if (!Array.isArray(raw)) return [];
  return raw.map(readVector).filter((item): item is RuntimeVector3 => item !== null);
}

function readFirstVector(source: SceneDocumentRecord | null, keys: string[]): RuntimeVector3 | null {
  if (!source) return null;
  for (const key of keys) {
    const value = readVector(source[key]);
    if (value) return value;
  }
  return null;
}

function readFirstString(source: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = readString(source[key]);
    if (value) return value;
  }
  return null;
}

function readStopPointPosition(transportPath: SceneDocumentRecord, pointId: string): RuntimeVector3 | null {
  for (const point of readArray(transportPath.stop_points)) {
    const candidateId = readString(point.point_id) ?? readString(point.id);
    if (candidateId !== pointId) continue;
    return readVector(point.position);
  }
  return null;
}

function readVector(value: unknown): RuntimeVector3 | null {
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

function resolveDuration(
  payload: Record<string, unknown>,
  instance: SceneDocumentRecord,
  waypoints: RuntimeVector3[],
  speedKeys: string[],
  minDuration: number,
): number | null {
  const paramOverrides = readRecord(instance.param_overrides);
  const explicit = numberFrom(payload.duration_s) ?? numberFrom(payload.duration) ?? numberFrom(paramOverrides?.duration_s) ?? numberFrom(paramOverrides?.duration);
  if (explicit && explicit > 0) return explicit;

  const speed = firstNumber(payload, speedKeys) ?? firstNumber(paramOverrides, speedKeys);
  if (!speed || speed <= 0) return null;
  return Math.max(minDuration, pathLength(waypoints) / speed);
}

function firstNumber(source: Record<string, unknown> | null, keys: string[]): number | null {
  if (!source) return null;
  for (const key of keys) {
    const value = numberFrom(source[key]);
    if (value !== null) return value;
  }
  return null;
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

export function pathLength(waypoints: RuntimeVector3[]): number {
  let total = 0;
  for (let index = 0; index < waypoints.length - 1; index += 1) {
    total += distance(waypoints[index], waypoints[index + 1]);
  }
  return total;
}

function distance(a: RuntimeVector3, b: RuntimeVector3): number {
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2);
}

function lerp(a: RuntimeVector3, b: RuntimeVector3, t: number): RuntimeVector3 {
  const p = clamp01(t);
  return {
    x: a.x + (b.x - a.x) * p,
    y: a.y + (b.y - a.y) * p,
    z: a.z + (b.z - a.z) * p,
  };
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function numberFrom(value: unknown): number | null {
  if (typeof value !== "number") return null;
  return Number.isFinite(value) ? value : null;
}

function cloneJsonValue(value: unknown): unknown {
  if (value === undefined) return undefined;
  return JSON.parse(JSON.stringify(value)) as unknown;
}
