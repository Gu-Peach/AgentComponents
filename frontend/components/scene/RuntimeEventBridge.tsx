"use client";

import { useEffect, useRef } from "react";
import { frontendApiClient } from "@/lib/api-client";
import { actionRefFromEvent, buildRuntimeAnimationAction } from "@/lib/runtime-behavior";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

const POLL_INTERVAL_MS = 650;

export function RuntimeEventBridge() {
  const runId = useWorkspaceStore((state) => state.runtimeRunId);
  const failureLoggedRef = useRef(false);

  useEffect(() => {
    if (!runId) return;
    const activeRunId = runId;

    let cancelled = false;
    let polling = false;

    async function poll() {
      if (polling || cancelled) return;
      polling = true;
      try {
        const events = await frontendApiClient.listFrontendEvents(activeRunId);
        const store = useWorkspaceStore.getState();
        for (const event of events) {
          if (event.type !== "device_behavior_triggered") continue;
          const eventRef = actionRefFromEvent(event) ?? `${event.sequence ?? "unknown"}`;
          if (store.hasSeenRuntimeEvent(eventRef)) continue;

          const action = buildRuntimeAnimationAction(event, store.sceneObjects);
          store.markRuntimeEventSeen(eventRef);
          if (action) {
            store.startRuntimeAction(action);
          } else {
            store.appendLog("warning", `runtime event skipped: ${event.instance_id}.${event.behavior_id}`);
          }
        }
        failureLoggedRef.current = false;
      } catch (error) {
        if (!failureLoggedRef.current) {
          useWorkspaceStore.getState().appendLog("warning", `runtime event polling failed: ${String(error)}`);
          failureLoggedRef.current = true;
        }
      } finally {
        polling = false;
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runId]);

  return null;
}
