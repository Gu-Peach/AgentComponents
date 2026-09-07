"use client";

import { ChevronDown, Plus, Terminal, Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

export function TerminalPanel() {
  const logs = useWorkspaceStore((state) => state.logs);
  const clearLogs = useWorkspaceStore((state) => state.clearLogs);
  const appendLog = useWorkspaceStore((state) => state.appendLog);
  const togglePanel = useWorkspaceStore((state) => state.togglePanel);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [logs.length]);

  return (
    <section className="terminal" data-testid="terminal-panel" aria-label="终端输出区">
      <div className="terminal-heading">
        <div className="terminal-title">
          <Terminal size={15} />
          输出
        </div>
        <div className="terminal-actions">
          <button className="terminal-button" onClick={() => appendLog("info", "mock backend response: 200 OK")}>
            <Plus size={13} />
            mock
          </button>
          <button className="terminal-button" onClick={clearLogs}>
            <Trash2 size={13} />
            清除
          </button>
          <button className="terminal-button" data-testid="collapse-footer" aria-label="收起终端" onClick={() => togglePanel("footerCollapsed")}>
            <ChevronDown size={14} />
          </button>
        </div>
      </div>
      <div className="terminal-lines">
        {logs.map((log) => (
          <div key={log.id} className="terminal-line">
            <span className="time">{log.timestamp}</span>
            <span className={`level ${log.level}`}>{log.level}</span>
            <span>{log.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </section>
  );
}
