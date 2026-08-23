// ============================================================
// 属性面板更新方案
// 基于四类设备规范：conveyor / robot / lift / storage
// 面板结构：坐标区 + [默认 Tab | 仿真 Tab]
// ============================================================

// ─────────────────────────────────────────────────────────────
// 1. 类型定义（对应 JSON 规范）
// ─────────────────────────────────────────────────────────────

// types/device.ts

export type DeviceType = "conveyor" | "robot" | "lift" | "storage";

// ── Conveyor ──
export interface ConveyorDefault {
  id: string;
  type: "conveyor";
  nodeName: string;
  ConveyorLength: number;   // mm
  ConveyorWidth: number;    // mm
  ConveyorHeight: number;   // mm
  ConveyorSpeed: number;    // mm/s
  liftoffset: number;       // mm
}
export interface ConveyorSimulation {
  conveyorStartOffset: number;  // mm
  conveyorEndOffset: number;    // mm
}

// ── Robot ──
export interface JointDef {
  name: string;
  nodeName: string;
  type: "revolute" | "prismatic" | "fixed";
  axis: { x: number; y: number; z: number };
  limit: { lower: number; upper: number };   // rad
}
export interface RobotDefault {
  id: string;
  type: "robot";
  nodeName: string;
}
export interface RobotSimulation {
  joints: JointDef[];
  speed: number;   // rad/s（末端速度）
}

// ── Lift ──
export interface LiftMotion {
  rootAxis: "x" | "y" | "z";
  carrierAxis: "x" | "y" | "z";
  rootRange: { min: number; max: number };      // m
  carrierRange: { min: number; max: number };   // m
}
export interface LiftDefault {
  id: string;
  type: "lift";
  nodeName: string;
  carrierNodeName: string;
}
export interface LiftSimulation {
  motion: LiftMotion;
  speed: number;   // m/s
}

// ── Storage ──
export interface StorageCell {
  id: string;   // 'A1', 'A2' ...
  position: { x: number; y: number; z: number };
}
export interface StorageDefault {
  id: string;
  type: "storage";
  nodeName: string;
}
export interface StorageSimulation {
  cells: StorageCell[];
}

// 联合类型
export type DeviceDefaultParams =
  | ConveyorDefault
  | RobotDefault
  | LiftDefault
  | StorageDefault;

export type DeviceSimulationParams =
  | ConveyorSimulation
  | RobotSimulation
  | LiftSimulation
  | StorageSimulation;

export interface DeviceInstance {
  instanceId: string;
  catalogId: string;
  modelUrl: string;
  transform: Transform;
  defaultParams: DeviceDefaultParams;
  simulationParams: DeviceSimulationParams;
}


// ─────────────────────────────────────────────────────────────
// 2. 属性面板容器
// ─────────────────────────────────────────────────────────────

// components/properties/PropertiesPanel.tsx
"use client";
import * as Tabs from "@radix-ui/react-tabs";
import { CoordinateWidget } from "./CoordinateWidget";
import { DefaultTab } from "./tabs/DefaultTab";
import { SimulationTab } from "./tabs/SimulationTab";
import { useSceneStore } from "@/stores/sceneStore";

export function PropertiesPanel() {
  const { selectedId, devices, updateTransform, updateDeviceParams } = useSceneStore();
  const device = devices.find((d) => d.instanceId === selectedId);

  if (!device) {
    return (
      <div className="flex flex-col h-full bg-[#252526] border-l border-[#1e1e1e]
        items-center justify-center text-[#555] text-xs gap-2">
        <span className="text-2xl opacity-30">⚙</span>
        <p>选择场景中的设备<br />查看组件属性</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#252526] border-l border-[#1e1e1e] select-none">

      {/* ── 设备标题栏 ── */}
      <div className="px-3 py-2 border-b border-[#1e1e1e] bg-[#2d2d2d] shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-[#4ec9b0] text-sm font-medium truncate">
            {device.defaultParams.nodeName}
          </span>
          <div className="flex gap-1">
            {/* 标签/锁定按钮（对标 VC 右上角图标） */}
            <button className="text-[#555] hover:text-[#aaa] transition-colors text-xs">🏷</button>
            <button className="text-[#555] hover:text-[#aaa] transition-colors text-xs">🔓</button>
          </div>
        </div>
        <span className="text-[10px] text-[#666] mt-0.5 block">
          {device.defaultParams.type.toUpperCase()}
        </span>
      </div>

      {/* ── 坐标区域（固定，不随 Tab 切换） ── */}
      <CoordinateWidget
        transform={device.transform}
        onChange={(t) => updateTransform(device.instanceId, t)}
      />

      {/* ── 参数 Tabs ── */}
      <Tabs.Root defaultValue="default" className="flex flex-col flex-1 min-h-0">
        <Tabs.List className="flex border-b border-[#1e1e1e] shrink-0 bg-[#2d2d2d]">
          {[
            { value: "default", label: "默认" },
            { value: "simulation", label: "仿真" },
          ].map((tab) => (
            <Tabs.Trigger
              key={tab.value}
              value={tab.value}
              className="flex-1 py-2 text-xs text-[#888] border-b-2 border-transparent
                data-[state=active]:text-[#ddd] data-[state=active]:border-[#0078d4]
                hover:text-[#aaa] transition-colors"
            >
              {tab.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        {/* 默认 Tab */}
        <Tabs.Content value="default" className="flex-1 overflow-y-auto min-h-0">
          <DefaultTab
            device={device}
            onChange={(params) => updateDeviceParams(device.instanceId, "default", params)}
          />
        </Tabs.Content>

        {/* 仿真 Tab */}
        <Tabs.Content value="simulation" className="flex-1 overflow-y-auto min-h-0">
          <SimulationTab
            device={device}
            onChange={(params) => updateDeviceParams(device.instanceId, "simulation", params)}
          />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────
// 3. 默认 Tab（各类型通用字段 + 类型特有字段）
// ─────────────────────────────────────────────────────────────

// components/properties/tabs/DefaultTab.tsx
import { PropRow, PropRowNumber, PropRowText } from "../fields/PropRow";
import type { DeviceInstance } from "@/types/device";

export function DefaultTab({ device, onChange }: {
  device: DeviceInstance;
  onChange: (params: any) => void;
}) {
  const p = device.defaultParams;
  const set = (key: string, val: any) => onChange({ ...p, [key]: val });

  return (
    <div className="py-1">
      {/* 所有类型共有字段 */}
      <SectionHeader label="基本信息" />
      <PropRowText  label="名称"   value={p.nodeName}  onChange={(v) => set("nodeName", v)} />
      <PropRowText  label="类别"   value={p.type}      readonly />
      <PropRowText  label="ID"     value={p.id}        readonly />

      {/* 类型特有字段 */}
      {p.type === "conveyor" && <ConveyorDefaultFields p={p as any} set={set} />}
      {p.type === "lift"     && <LiftDefaultFields     p={p as any} set={set} />}
      {/* robot / storage 默认字段较少，共有字段已足够 */}
    </div>
  );
}

function ConveyorDefaultFields({ p, set }: any) {
  return (
    <>
      <SectionHeader label="尺寸参数" />
      <PropRowNumber label="ConveyorLength"  value={p.ConveyorLength}  unit="mm"   onChange={(v) => set("ConveyorLength", v)} />
      <PropRowNumber label="ConveyorWidth"   value={p.ConveyorWidth}   unit="mm"   onChange={(v) => set("ConveyorWidth", v)} />
      <PropRowNumber label="ConveyorHeight"  value={p.ConveyorHeight}  unit="mm"   onChange={(v) => set("ConveyorHeight", v)} />
      <SectionHeader label="运行参数" />
      <PropRowNumber label="ConveyorSpeed"   value={p.ConveyorSpeed}   unit="mm/s" onChange={(v) => set("ConveyorSpeed", v)} />
      <PropRowNumber label="LiftOffset"      value={p.liftoffset}      unit="mm"   onChange={(v) => set("liftoffset", v)} />
    </>
  );
}

function LiftDefaultFields({ p, set }: any) {
  return (
    <>
      <SectionHeader label="节点配置" />
      <PropRowText label="NodeName"        value={p.nodeName}        onChange={(v) => set("nodeName", v)} />
      <PropRowText label="CarrierNodeName" value={p.carrierNodeName} onChange={(v) => set("carrierNodeName", v)} />
    </>
  );
}


// ─────────────────────────────────────────────────────────────
// 4. 仿真 Tab（各类型差异最大）
// ─────────────────────────────────────────────────────────────

// components/properties/tabs/SimulationTab.tsx
import { useState } from "react";
import { PropRowNumber, PropRowText, PropRowSelect } from "../fields/PropRow";
import { ChevronRight, Plus, Trash2 } from "lucide-react";

export function SimulationTab({ device, onChange }: {
  device: DeviceInstance;
  onChange: (params: any) => void;
}) {
  const { type } = device.defaultParams;
  const p = device.simulationParams as any;
  const set = (key: string, val: any) => onChange({ ...p, [key]: val });

  if (type === "conveyor")  return <ConveyorSimFields  p={p} set={set} />;
  if (type === "robot")     return <RobotSimFields     p={p} set={set} onChange={onChange} />;
  if (type === "lift")      return <LiftSimFields      p={p} set={set} />;
  if (type === "storage")   return <StorageSimFields   p={p} set={set} onChange={onChange} />;
  return null;
}

// ── Conveyor 仿真 ──
function ConveyorSimFields({ p, set }: any) {
  return (
    <div className="py-1">
      <SectionHeader label="路径偏移" />
      <PropRowNumber label="StartOffset" value={p.conveyorStartOffset} unit="mm"
        onChange={(v) => set("conveyorStartOffset", v)} />
      <PropRowNumber label="EndOffset"   value={p.conveyorEndOffset}   unit="mm"
        onChange={(v) => set("conveyorEndOffset", v)} />
    </div>
  );
}

// ── Robot 仿真（关节列表 + 速度）──
function RobotSimFields({ p, set, onChange }: any) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="py-1">
      <SectionHeader label="运行速度" />
      <PropRowNumber label="Speed" value={p.speed} unit="rad/s"
        onChange={(v) => set("speed", v)} />

      <SectionHeader label={`关节配置（${p.joints?.length ?? 0} 轴）`} />

      {(p.joints ?? []).map((joint: any, idx: number) => (
        <div key={joint.name} className="border-b border-[#2a2a2a]">
          {/* 关节折叠头 */}
          <button
            onClick={() => setExpanded(expanded === joint.name ? null : joint.name)}
            className="flex items-center w-full px-3 py-2 gap-2
              hover:bg-[#2a2d2e] transition-colors text-left"
          >
            <ChevronRight size={12}
              className={`text-[#555] transition-transform shrink-0
                ${expanded === joint.name ? "rotate-90" : ""}`}
            />
            {/* 关节轴颜色指示 */}
            <span className={`w-2 h-2 rounded-full shrink-0
              ${joint.axis.y === 1 ? "bg-[#98c379]" :
                joint.axis.z === 1 ? "bg-[#61afef]" : "bg-[#e06c75]"}`}
            />
            <span className="text-xs text-[#ccc] flex-1">{joint.name}</span>
            <span className="text-[10px] text-[#555]">{joint.type}</span>
          </button>

          {/* 关节展开详情 */}
          {expanded === joint.name && (
            <div className="bg-[#1e1e1e] pb-2">
              <PropRowText   label="NodeName" value={joint.nodeName}  readonly />
              <PropRowText   label="Type"     value={joint.type}      readonly />
              <PropRowText   label="Axis"
                value={`X:${joint.axis.x} Y:${joint.axis.y} Z:${joint.axis.z}`}
                readonly />
              <PropRowNumber label="Lower"    value={joint.limit.lower} unit="rad"
                onChange={(v) => {
                  const joints = [...p.joints];
                  joints[idx] = { ...joint, limit: { ...joint.limit, lower: v } };
                  onChange({ ...p, joints });
                }} />
              <PropRowNumber label="Upper"    value={joint.limit.upper} unit="rad"
                onChange={(v) => {
                  const joints = [...p.joints];
                  joints[idx] = { ...joint, limit: { ...joint.limit, upper: v } };
                  onChange({ ...p, joints });
                }} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Lift 仿真（运动范围配置）──
function LiftSimFields({ p, set }: any) {
  const m = p.motion ?? {};
  const setMotion = (key: string, val: any) => set("motion", { ...m, [key]: val });

  return (
    <div className="py-1">
      <SectionHeader label="运动轴" />
      <PropRowSelect label="RootAxis"    value={m.rootAxis}    options={["x","y","z"]}
        onChange={(v) => setMotion("rootAxis", v)} />
      <PropRowSelect label="CarrierAxis" value={m.carrierAxis} options={["x","y","z"]}
        onChange={(v) => setMotion("carrierAxis", v)} />

      <SectionHeader label="主轴范围（Root）" />
      <PropRowNumber label="Min" value={m.rootRange?.min ?? 0} unit="m"
        onChange={(v) => setMotion("rootRange", { ...m.rootRange, min: v })} />
      <PropRowNumber label="Max" value={m.rootRange?.max ?? 0} unit="m"
        onChange={(v) => setMotion("rootRange", { ...m.rootRange, max: v })} />

      <SectionHeader label="载台范围（Carrier）" />
      <PropRowNumber label="Min" value={m.carrierRange?.min ?? 0} unit="m"
        onChange={(v) => setMotion("carrierRange", { ...m.carrierRange, min: v })} />
      <PropRowNumber label="Max" value={m.carrierRange?.max ?? 0} unit="m"
        onChange={(v) => setMotion("carrierRange", { ...m.carrierRange, max: v })} />

      <SectionHeader label="速度" />
      <PropRowNumber label="Speed" value={p.speed ?? 0} unit="m/s"
        onChange={(v) => set("speed", v)} />
    </div>
  );
}

// ── Storage 仿真（货格列表）──
function StorageSimFields({ p, set, onChange }: any) {
  const cells: StorageCell[] = p.cells ?? [];

  const updateCell = (idx: number, field: string, val: any) => {
    const next = [...cells];
    if (field === "id") {
      next[idx] = { ...next[idx], id: val };
    } else {
      const [, axis] = field.split(".");
      next[idx] = { ...next[idx], position: { ...next[idx].position, [axis]: val } };
    }
    onChange({ ...p, cells: next });
  };

  const addCell = () => {
    onChange({
      ...p,
      cells: [...cells, { id: `NEW_${cells.length + 1}`, position: { x: 0, y: 0, z: 0 } }],
    });
  };

  const removeCell = (idx: number) => {
    onChange({ ...p, cells: cells.filter((_, i) => i !== idx) });
  };

  return (
    <div className="py-1">
      <div className="flex items-center justify-between px-3 py-1.5">
        <SectionLabel label={`货格（${cells.length}）`} />
        <button onClick={addCell}
          className="flex items-center gap-1 text-[10px] text-[#0078d4]
            hover:text-[#1184db] transition-colors">
          <Plus size={11} /> 添加
        </button>
      </div>

      {cells.map((cell, idx) => (
        <div key={idx} className="mx-3 mb-2 border border-[#3a3a3a] rounded bg-[#1e1e1e]">
          {/* 货格头部 */}
          <div className="flex items-center justify-between px-2 py-1.5
            border-b border-[#2a2a2a]">
            <span className="text-xs text-[#e8c56d] font-mono">{cell.id}</span>
            <button onClick={() => removeCell(idx)}
              className="text-[#555] hover:text-[#e06c75] transition-colors">
              <Trash2 size={11} />
            </button>
          </div>
          {/* 货格位置 */}
          <div className="grid grid-cols-3 gap-1 p-2">
            {(["x", "y", "z"] as const).map((axis) => (
              <div key={axis} className="flex flex-col gap-0.5">
                <span className={`text-[10px] font-bold text-center
                  ${axis === "x" ? "text-[#e06c75]" :
                    axis === "y" ? "text-[#98c379]" : "text-[#61afef]"}`}>
                  {axis.toUpperCase()}
                </span>
                <input
                  type="number"
                  value={cell.position[axis]}
                  step="0.001"
                  onChange={(e) => updateCell(idx, `position.${axis}`, parseFloat(e.target.value))}
                  className="w-full bg-[#2a2a2a] border border-[#444] rounded px-1 py-0.5
                    text-[10px] text-[#ddd] text-center outline-none focus:border-[#0078d4]"
                />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────
// 5. 通用字段组件
// ─────────────────────────────────────────────────────────────

// components/properties/fields/PropRow.tsx

// 段落标题
export function SectionHeader({ label }: { label: string }) {
  return (
    <div className="px-3 pt-3 pb-1">
      <span className="text-[10px] text-[#555] font-medium uppercase tracking-wider">
        {label}
      </span>
    </div>
  );
}
function SectionLabel({ label }: { label: string }) {
  return (
    <span className="text-[10px] text-[#555] font-medium uppercase tracking-wider">
      {label}
    </span>
  );
}

// 文本行
export function PropRowText({ label, value, onChange, readonly = false }: {
  label: string; value: string;
  onChange?: (v: string) => void; readonly?: boolean;
}) {
  return (
    <div className="flex items-center px-3 py-[5px] border-b border-[#1e1e1e]
      hover:bg-[#2a2d2e] transition-colors group">
      <span className="text-xs text-[#888] w-[130px] shrink-0 truncate">{label}</span>
      <input
        type="text"
        value={value ?? ""}
        readOnly={readonly}
        onChange={(e) => onChange?.(e.target.value)}
        className={`flex-1 bg-transparent text-xs outline-none border-b border-transparent
          ${readonly
            ? "text-[#666] cursor-default"
            : "text-[#ddd] focus:border-[#0078d4] cursor-text group-hover:border-[#3a3a3a]"
          }`}
      />
    </div>
  );
}

// 数字行（带单位）
export function PropRowNumber({ label, value, unit, onChange, step = 0.001 }: {
  label: string; value: number; unit?: string;
  onChange: (v: number) => void; step?: number;
}) {
  return (
    <div className="flex items-center px-3 py-[5px] border-b border-[#1e1e1e]
      hover:bg-[#2a2d2e] transition-colors">
      <span className="text-xs text-[#888] w-[130px] shrink-0 truncate">{label}</span>
      <input
        type="number"
        value={value ?? 0}
        step={step}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        className="flex-1 bg-transparent text-xs text-[#ddd] text-right
          outline-none border-b border-transparent focus:border-[#0078d4]"
      />
      {unit && (
        <span className="text-[10px] text-[#555] ml-1.5 w-8 shrink-0">{unit}</span>
      )}
    </div>
  );
}

// 下拉选择行
export function PropRowSelect({ label, value, options, onChange }: {
  label: string; value: string;
  options: string[]; onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center px-3 py-[5px] border-b border-[#1e1e1e]
      hover:bg-[#2a2d2e] transition-colors">
      <span className="text-xs text-[#888] w-[130px] shrink-0 truncate">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 bg-[#1a1a1a] border border-[#3a3a3a] rounded px-1 py-0.5
          text-xs text-[#ddd] outline-none focus:border-[#0078d4] cursor-pointer"
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
