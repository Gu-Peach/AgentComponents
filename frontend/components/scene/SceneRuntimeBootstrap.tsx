"use client";

import { useEffect, useRef } from "react";
import { frontendApiClient } from "@/lib/api-client";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

const BOOTSTRAP_DISABLED = process.env.NEXT_PUBLIC_BOOTSTRAP_SCENE1_RUNTIME === "false";

export function SceneRuntimeBootstrap() {
  const runId = useWorkspaceStore((state) => state.runtimeRunId);
  const startedRef = useRef(false);

  useEffect(() => {
    if (BOOTSTRAP_DISABLED || runId || startedRef.current) return;
    startedRef.current = true;
    let cancelled = false;

    const store = useWorkspaceStore.getState();
    store.appendLog("info", "bootstrapping scene1 runtime from SceneDocument");

    void frontendApiClient
      .bootstrapScene1Runtime()
      .then((result) => {
        if (cancelled) return;
        const nextStore = useWorkspaceStore.getState();
        nextStore.setRuntimeSceneDocument(result.sceneDocument);
        nextStore.replaceSceneObjects(result.sceneObjects);
        nextStore.setRuntimeRunId(result.runId);
        nextStore.appendLog("success", `runtime run ready: ${result.runId}`);
      })
      .catch((error) => {
        if (cancelled) return;
        useWorkspaceStore.getState().appendLog("warning", `scene1 runtime bootstrap failed: ${String(error)}`);
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  return null;
}
