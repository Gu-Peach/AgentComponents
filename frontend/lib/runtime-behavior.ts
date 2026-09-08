import type {
  RuntimeAnimationAction,
  RuntimeBehaviorEvent,
  RuntimeVector3,
  SceneObject,
  Vector3Tuple,
} from "@/types/scene";

const CONVEYOR_BEHAVIORS = new Set([
  "transport_to_exit",
  "advance_to_next_stop_point",
  "accept_material",
  "release_material",
]);

const DEFAULT_CONVEYOR_SPEED = 0.85;
const DEFAULT_ROBOT_SPEED = 0.9;
const DEFAULT_LIFT_HEIGHT = 0.72;

export function buildRuntimeAnimationAction(
  event: RuntimeBehaviorEvent,
  sceneObjects: SceneObject[],
  now = Date.now(),
): RuntimeAnimationAction | null {
  const instance = sceneObjects.find((object) => object.id === event.instance_id);
  if (!instance) return null;

  const payload = event.payload ?? {};
  const actionId = event.action_id ?? event.task_id ?? event.event_id ?? `runtime_${now}`;
  const subjectId = resolveSubjectId(payload, sceneObjects);

  if (event.behavior_id === "pick_and_place" || instance.type === "robot_arm") {
    const waypoints = resolveRobotWaypoints(instance, payload, sceneObjects, subjectId);
    if (waypoints.length < 2) return null;
    return {
      actionId,
      eventId: event.event_id,
      taskId: event.task_id,
      runId: event.run_id,
      instanceId: event.instance_id,
      behaviorId: event.behavior_id,
      kind: "robot_pick_place",
      subjectId,
      waypoints,
      duration: resolveDuration(payload, pathLength(waypoints), DEFAULT_ROBOT_SPEED, 2.2),
      elapsed: 0,
      startedAt: now,
      payload,
      status: "running",
    };
  }

  if (CONVEYOR_BEHAVIORS.has(event.behavior_id) || instance.type === "conveyor") {
    const waypoints = resolveConveyorWaypoints(instance, payload, sceneObjects, subjectId);
    if (waypoints.length < 2) return null;
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
      duration: resolveDuration(payload, pathLength(waypoints), DEFAULT_CONVEYOR_SPEED, 1.4),
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

function resolveConveyorWaypoints(
  conveyor: SceneObject,
  payload: Record<string, unknown>,
  sceneObjects: SceneObject[],
  subjectId: string | null,
): RuntimeVector3[] {
  const explicit = readWaypoints(payload);
  if (explicit.length >= 2) return explicit;

  const transportPath = readRecord(readRecord(payload.runtime_geometry)?.transport_path);

  const from = readPosition(payload, ["from_position", "source_position", "entry_position"]) ??
    readPosition(transportPath, ["start_position"]);
  const to = readPosition(payload, ["to_position", "target_position", "exit_position"]) ??
    readPosition(transportPath, ["end_position"]);
  if (from && to) return [from, to];

  const subject = subjectId ? sceneObjects.find((object) => object.id === subjectId) : null;
  const entry = conveyorSurfacePoint(conveyor, -0.4, subject);
  const exit = conveyorSurfacePoint(conveyor, 0.4, subject);

  if (from) return [from, exit];
  if (to) return [entry, to];
  return [entry, exit];
}

function resolveRobotWaypoints(
  robot: SceneObject,
  payload: Record<string, unknown>,
  sceneObjects: SceneObject[],
  subjectId: string | null,
): RuntimeVector3[] {
  const explicit = readWaypoints(payload);
  if (explicit.length >= 2) return explicit;

  const pickPlacePath = readRecord(readRecord(payload.runtime_geometry)?.pick_place_path);

  const subject = subjectId ? sceneObjects.find((object) => object.id === subjectId) : null;
  const pick =
    readPosition(payload, ["pick_position", "from_position", "source_position"]) ??
    readPosition(pickPlacePath, ["pick_position", "from_position", "source_position"]) ??
    vectorFromTuple(subject?.transform.position) ??
    offsetPoint(robot, [0.95, 0.45, 0]);

  const place =
    readPosition(payload, ["place_position", "to_position", "target_position", "destination_position"]) ??
    readPosition(pickPlacePath, ["place_position", "to_position", "target_position", "destination_position"]) ??
    resolveTargetObjectPosition(payload, sceneObjects, robot) ??
    offsetPoint(robot, [1.75, 0.48, robot.id.endsWith("2") ? 0.45 : -0.45]);

  const liftHeight = numberFrom(payload.lift_height) ??
    numberFrom(payload.liftHeight) ??
    numberFrom(pickPlacePath?.lift_height) ??
    numberFrom(pickPlacePath?.approach_height) ??
    DEFAULT_LIFT_HEIGHT;
  const pickAbove = { ...pick, y: pick.y + liftHeight };
  const placeAbove = { ...place, y: place.y + liftHeight };
  return [pickAbove, pick, pickAbove, placeAbove, place, placeAbove];
}

function resolveSubjectId(payload: Record<string, unknown>, sceneObjects: SceneObject[]): string | null {
  for (const key of ["subject_id", "object_id", "carrier_id", "workpiece_id", "material_id"]) {
    const value = payload[key];
    if (typeof value === "string" && sceneObjects.some((object) => object.id === value)) return value;
  }

  return (
    sceneObjects.find((object) => object.type === "workpiece_carrier")?.id ??
    sceneObjects.find((object) => object.type === "workpiece")?.id ??
    null
  );
}

function resolveTargetObjectPosition(
  payload: Record<string, unknown>,
  sceneObjects: SceneObject[],
  robot: SceneObject,
): RuntimeVector3 | null {
  for (const key of ["target_object_id", "target_conveyor_id", "target_conveyor", "to_instance_id", "destination_id"]) {
    const value = payload[key];
    if (typeof value !== "string") continue;
    const target = sceneObjects.find((object) => object.id === value);
    if (target) return surfaceCenter(target);
  }

  const preferredOutput = robot.id.endsWith("2") ? "output_conveyor_bottom" : "output_conveyor_top";
  const target = sceneObjects.find((object) => object.id === preferredOutput);
  return target ? surfaceCenter(target) : null;
}

function readWaypoints(payload: Record<string, unknown>): RuntimeVector3[] {
  for (const source of [
    payload,
    readRecord(readRecord(payload.runtime_geometry)?.transport_path),
    readRecord(readRecord(payload.runtime_geometry)?.pick_place_path),
  ]) {
    const raw = source?.waypoints;
    if (!Array.isArray(raw)) continue;
    const waypoints = raw.map(readVector).filter((item): item is RuntimeVector3 => item !== null);
    if (waypoints.length > 0) return waypoints;
  }

  return [];
}

function readPosition(payload: Record<string, unknown> | null | undefined, keys: string[]): RuntimeVector3 | null {
  if (!payload) return null;
  for (const key of keys) {
    const position = readVector(payload[key]);
    if (position) return position;
  }
  return null;
}

function readVector(value: unknown): RuntimeVector3 | null {
  if (Array.isArray(value) && value.length >= 3) {
    const [x, y, z] = value.map(Number);
    if ([x, y, z].every(Number.isFinite)) return { x, y, z };
  }

  if (typeof value === "object" && value !== null) {
    const record = value as Record<string, unknown>;
    const x = Number(record.x);
    const y = Number(record.y);
    const z = Number(record.z);
    if ([x, y, z].every(Number.isFinite)) return { x, y, z };
  }

  return null;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function resolveDuration(payload: Record<string, unknown>, length: number, speed: number, minDuration: number): number {
  const explicit = numberFrom(payload.duration_s) ?? numberFrom(payload.duration);
  if (explicit && explicit > 0) return explicit;
  return Math.max(minDuration, length / speed);
}

function conveyorSurfacePoint(conveyor: SceneObject, localXRatio: number, subject?: SceneObject | null): RuntimeVector3 {
  const [length, height] = conveyor.dimensions;
  const subjectHeight = subject?.dimensions[1] ?? 0.18;
  return localToWorld(conveyor, [length * localXRatio, height / 2 + subjectHeight / 2 + 0.06, 0]);
}

function surfaceCenter(object: SceneObject): RuntimeVector3 {
  const [, height] = object.dimensions;
  return localToWorld(object, [0, height / 2 + 0.18, 0]);
}

function offsetPoint(object: SceneObject, offset: Vector3Tuple): RuntimeVector3 {
  return localToWorld(object, offset);
}

function localToWorld(object: SceneObject, local: Vector3Tuple): RuntimeVector3 {
  const [px, py, pz] = object.transform.position;
  const yaw = (object.transform.rotation[1] * Math.PI) / 180;
  const cos = Math.cos(yaw);
  const sin = Math.sin(yaw);
  return {
    x: px + local[0] * cos - local[2] * sin,
    y: py + local[1],
    z: pz + local[0] * sin + local[2] * cos,
  };
}

function vectorFromTuple(tuple?: Vector3Tuple): RuntimeVector3 | null {
  if (!tuple) return null;
  return { x: tuple[0], y: tuple[1], z: tuple[2] };
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
