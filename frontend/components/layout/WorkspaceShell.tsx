"use client";

import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { HeaderBar } from "@/components/layout/HeaderBar";
import { ResizeHandle } from "@/components/layout/ResizeHandle";
import { AssetLibraryPanel } from "@/components/panels/AssetLibraryPanel";
import { PropertiesPanel } from "@/components/panels/PropertiesPanel";
import { SceneViewport } from "@/components/scene/SceneViewport";
import { TerminalPanel } from "@/components/terminal/TerminalPanel";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function WorkspaceShell() {
  const panels = useWorkspaceStore((state) => state.panels);
  const layout = useWorkspaceStore((state) => state.layout);
  const togglePanel = useWorkspaceStore((state) => state.togglePanel);
  const setLayoutSize = useWorkspaceStore((state) => state.setLayoutSize);

  return (
    <div className="workspace-shell">
      {!panels.headerCollapsed && <HeaderBar />}

      {panels.headerCollapsed && (
        <button className="floating-toggle top" data-testid="expand-header" onClick={() => togglePanel("headerCollapsed")} aria-label="展开顶部栏">
          <ChevronDown size={16} />
          Header
        </button>
      )}

      <div className="workspace-body">
        {!panels.leftCollapsed && (
          <aside className="panel panel-left" style={{ width: layout.leftWidth }}>
            <AssetLibraryPanel />
          </aside>
        )}
        {!panels.leftCollapsed && (
          <ResizeHandle
            axis="x"
            ariaLabel="调整左侧资产库宽度"
            onDrag={(event) => setLayoutSize("leftWidth", clamp(event.clientX, 240, 520))}
          />
        )}

        <main className="workspace-center">
          {panels.leftCollapsed && (
            <button className="floating-toggle left" data-testid="expand-left" onClick={() => togglePanel("leftCollapsed")} aria-label="展开左侧资产库">
              <ChevronRight size={16} />
              资产库
            </button>
          )}
          {panels.rightCollapsed && (
            <button className="floating-toggle right" data-testid="expand-right" onClick={() => togglePanel("rightCollapsed")} aria-label="展开右侧属性面板">
              属性
              <ChevronLeft size={16} />
            </button>
          )}
          {panels.footerCollapsed && (
            <button className="floating-toggle bottom" data-testid="expand-footer" onClick={() => togglePanel("footerCollapsed")} aria-label="展开底部终端">
              <ChevronUp size={16} />
              输出
            </button>
          )}
          <SceneViewport />
        </main>

        {!panels.rightCollapsed && (
          <ResizeHandle
            axis="x"
            ariaLabel="调整右侧属性面板宽度"
            onDrag={(event) => setLayoutSize("rightWidth", clamp(window.innerWidth - event.clientX, 280, 540))}
          />
        )}
        {!panels.rightCollapsed && (
          <aside className="panel panel-right" style={{ width: layout.rightWidth }}>
            <PropertiesPanel />
          </aside>
        )}
      </div>

      {!panels.footerCollapsed && (
        <>
          <ResizeHandle
            axis="y"
            ariaLabel="调整底部终端高度"
            onDrag={(event) => setLayoutSize("footerHeight", clamp(window.innerHeight - event.clientY, 110, 360))}
          />
          <div className="terminal-wrap" style={{ height: layout.footerHeight }}>
            <TerminalPanel />
          </div>
        </>
      )}
    </div>
  );
}
