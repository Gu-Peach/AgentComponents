export type AssetCategory = "device_model" | "scene_model";

export type DeviceType =
  | "robot_arm"
  | "conveyor"
  | "workpiece"
  | "workpiece_carrier"
  | "material_source_station"
  | "lift_table"
  | "storage_rack"
  | "rotary_table";

export type Vector3Tuple = [number, number, number];

export interface Transform3D {
  position: Vector3Tuple;
  rotation: Vector3Tuple;
  scale: Vector3Tuple;
}

export interface CatalogAsset {
  id: string;
  name: string;
  category: AssetCategory;
  type: DeviceType;
  description: string;
  tags: string[];
  color: string;
  defaultDimensions: Vector3Tuple;
  source: "mock" | "api";
  apiRef?: string;
}

export interface SceneObject {
  id: string;
  assetId: string;
  name: string;
  type: DeviceType;
  description: string;
  transform: Transform3D;
  dimensions: Vector3Tuple;
  color: string;
  createdFrom: string;
}

export interface UrdfJointConfig {
  name: string;
  nodeName: string;
  type: string;
  axis: RuntimeVector3;
  limit?: { lower: number; upper: number };
}

export interface DeviceConfig {
  id: string;
  type: string;
  displayName: string;
  description: string;
  rootNodeName: string;
  carrierNodeName?: string;
  urdf?: {
    joints: UrdfJointConfig[];
    endEffectorNodeName?: string;
  };
  motion?: {
    rootAxis?: "x" | "y" | "z";
    carrierAxis?: "x" | "y" | "z";
    rootRange?: { min: number; max: number };
    carrierRange?: { min: number; max: number };
  };
  grid?: {
    cells: Array<{
      id: string;
      position: RuntimeVector3;
    }>;
  };
  keyPointsStrategy?: string;
  keyPoints?: {
    name: string;
    auto?: boolean;
    nodeName?: string;
    origin?: RuntimeVector3;
    offset?: RuntimeVector3;
    description?: string;
  }[];
  trajectoryConfig?: {
    liftHeight?: number;
    speed?: number;
  };
}

export interface PanelState {
  headerCollapsed: boolean;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  footerCollapsed: boolean;
}

export interface LayoutSizes {
  leftWidth: number;
  rightWidth: number;
  footerHeight: number;
}

export type LogLevel = "info" | "success" | "warning" | "error";

export interface TerminalLogEntry {
  id: string;
  level: LogLevel;
  message: string;
  timestamp: string;
}

export interface RuntimeVector3 {
  x: number;
  y: number;
  z: number;
}

export type RuntimeBehaviorId =
  | "transport_to_exit"
  | "advance_to_next_stop_point"
  | "accept_material"
  | "release_material"
  | "pick_and_place"
  | string;

export interface RuntimeBehaviorEvent {
  event_id?: string;
  stream_id?: string;
  run_id?: string;
  task_id?: string;
  action_id?: string;
  type: "device_behavior_triggered";
  sequence?: number;
  instance_id: string;
  device_type?: DeviceType | string | null;
  behavior_id: RuntimeBehaviorId;
  payload?: Record<string, unknown>;
  status?: string;
  sim_time_s?: number | null;
}

export type RuntimeActionKind = "conveyor_linear" | "robot_pick_place";

export interface RuntimeAnimationAction {
  actionId: string;
  eventId?: string;
  taskId?: string;
  runId?: string;
  instanceId: string;
  behaviorId: RuntimeBehaviorId;
  kind: RuntimeActionKind;
  subjectId: string | null;
  waypoints: RuntimeVector3[];
  duration: number;
  elapsed: number;
  startedAt: number;
  payload: Record<string, unknown>;
  status: "running" | "done" | "failed";
}

export interface RuntimeDeviceVisualState {
  activeActionId?: string;
  beltOffset?: number;
  armPhase?: "idle" | "approach" | "execute" | "return";
  baseYaw?: number;
  shoulder?: number;
  elbow?: number;
  wrist?: number;
  gripperClosed?: boolean;
}
