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
