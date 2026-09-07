"use client";

import { ChevronRight, Info, SlidersHorizontal } from "lucide-react";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";
import type { SceneObject, Vector3Tuple } from "@/types/scene";

function formatNumber(value: number) {
  return Number.isFinite(value) ? Number(value.toFixed(3)) : 0;
}

function updateTuple(tuple: Vector3Tuple, index: number, value: number): Vector3Tuple {
  const next: Vector3Tuple = [...tuple];
  next[index] = Number.isFinite(value) ? value : 0;
  return next;
}

function AxisInputs({ label, value, onChange }: { label: string; value: Vector3Tuple; onChange: (value: Vector3Tuple) => void }) {
  const axes = ["X", "Y", "Z"] as const;
  return (
    <div className="field-grid">
      <div className="axis-grid" aria-label={label}>
        {axes.map((axis, index) => (
          <div key={axis} className={`axis-field ${axis.toLowerCase()}`}>
            <label>{axis}</label>
            <input
              data-testid={`${label === "坐标位置" ? "position" : "rotation"}-${axis.toLowerCase()}`}
              type="number"
              step="0.1"
              value={formatNumber(value[index])}
              onChange={(event) => onChange(updateTuple(value, index, Number(event.target.value)))}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function PropertyTextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="field-row">
      <label>{label}</label>
      <input data-testid="property-name" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function PropertyTextarea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="field-row">
      <label>{label}</label>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function SelectedObjectEditor({ object }: { object: SceneObject }) {
  const updateSceneObject = useWorkspaceStore((state) => state.updateSceneObject);
  const updateSceneObjectTransform = useWorkspaceStore((state) => state.updateSceneObjectTransform);

  return (
    <div className="properties-content">
      <div className="property-section">
        <h3>基础属性</h3>
        <div className="field-grid">
          <PropertyTextField label="设备名称" value={object.name} onChange={(name) => updateSceneObject(object.id, { name })} />
          <div className="field-row">
            <label>设备类型</label>
            <select value={object.type} disabled>
              <option>{object.type}</option>
            </select>
          </div>
          <PropertyTextarea
            label="属性描述"
            value={object.description}
            onChange={(description) => updateSceneObject(object.id, { description })}
          />
        </div>
      </div>

      <div className="property-section">
        <h3>坐标位置</h3>
        <AxisInputs
          label="坐标位置"
          value={object.transform.position}
          onChange={(position) => updateSceneObjectTransform(object.id, { position })}
        />
      </div>

      <div className="property-section">
        <h3>旋转角度</h3>
        <AxisInputs
          label="旋转角度"
          value={object.transform.rotation}
          onChange={(rotation) => updateSceneObjectTransform(object.id, { rotation })}
        />
      </div>

      <div className="property-section">
        <h3>模型信息</h3>
        <div className="field-grid">
          <div className="field-row">
            <label>来源</label>
            <input value={object.createdFrom} readOnly />
          </div>
          <div className="field-row">
            <label>实例 ID</label>
            <input value={object.id} readOnly />
          </div>
        </div>
      </div>
    </div>
  );
}

export function PropertiesPanel() {
  const selectedObjectId = useWorkspaceStore((state) => state.selectedObjectId);
  const sceneObjects = useWorkspaceStore((state) => state.sceneObjects);
  const togglePanel = useWorkspaceStore((state) => state.togglePanel);
  const object = sceneObjects.find((item) => item.id === selectedObjectId);

  return (
    <section className="panel" data-testid="properties-panel" aria-label="属性面板">
      <div className="panel-heading">
        <div>
          <div className="panel-title">
            <SlidersHorizontal size={16} />
            组件属性
          </div>
          <div className="panel-subtitle">基础字段与 transform 联动</div>
        </div>
        <button className="collapse-button" data-testid="collapse-right" aria-label="收起属性面板" onClick={() => togglePanel("rightCollapsed")}>
          <ChevronRight size={16} />
        </button>
      </div>

      {object ? (
        <SelectedObjectEditor object={object} />
      ) : (
        <div className="empty-panel">
          <div>
            <Info size={30} />
            <p>选择三维场景中的对象后，这里会显示名称、坐标、旋转、类型和描述。</p>
          </div>
        </div>
      )}
    </section>
  );
}
