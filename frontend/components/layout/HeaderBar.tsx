"use client";

import { Box, ChevronUp, FolderOpen, GitBranch, Link2, MousePointer2, Save, Search, Settings } from "lucide-react";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

export function HeaderBar() {
  const projectName = useWorkspaceStore((state) => state.projectName);
  const togglePanel = useWorkspaceStore((state) => state.togglePanel);
  const appendLog = useWorkspaceStore((state) => state.appendLog);

  return (
    <header className="topbar" data-testid="header-bar">
      <div className="topbar-title">
        <div className="project-mark">AC</div>
        <div className="project-copy">
          <div className="project-name">{projectName}</div>
          <div className="project-subtitle">基础场景编辑 · mock workspace</div>
        </div>
      </div>

      <nav className="toolbar" aria-label="工作区工具栏">
        <button className="text-button" onClick={() => appendLog("info", "open project action reserved")}> 
          <FolderOpen size={15} />
          项目
        </button>
        <button className="icon-button" aria-label="保存" title="保存占位" onClick={() => appendLog("success", "mock scene saved locally")}> 
          <Save size={16} />
        </button>
        <button className="icon-button" aria-label="选择" title="选择工具" onClick={() => appendLog("info", "selection tool active")}> 
          <MousePointer2 size={16} />
        </button>
        <button className="icon-button" aria-label="模型" title="模型工具占位" onClick={() => appendLog("info", "model tool reserved")}> 
          <Box size={16} />
        </button>
        <button className="icon-button optional" aria-label="连接" title="连接工具占位" onClick={() => appendLog("info", "connector tool reserved")}> 
          <Link2 size={16} />
        </button>
        <button className="icon-button optional" aria-label="拓扑" title="拓扑工具占位" onClick={() => appendLog("info", "topology view reserved")}> 
          <GitBranch size={16} />
        </button>
        <button className="icon-button optional" aria-label="搜索" title="搜索占位" onClick={() => appendLog("info", "workspace search reserved")}> 
          <Search size={16} />
        </button>
      </nav>

      <div className="user-chip">
        <button className="icon-button" aria-label="设置" title="设置占位" onClick={() => appendLog("info", "settings reserved")}> 
          <Settings size={16} />
        </button>
        <div className="avatar" title="登录头像占位">MS</div>
        <button className="collapse-button" data-testid="collapse-header" aria-label="收起顶部栏" onClick={() => togglePanel("headerCollapsed")}> 
          <ChevronUp size={17} />
        </button>
      </div>
    </header>
  );
}
