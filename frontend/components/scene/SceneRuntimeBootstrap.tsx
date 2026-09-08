"use client";

import { useEffect, useRef } from "react";
import { frontendApiClient } from "@/lib/api-client";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

const BOOTSTRAP_DISABLED = process.env.NEXT_PUBLIC_BOOTSTRAP_SCENE1_RUNTIME === "false";

export function SceneRuntimeBootstrap() {
  const runId = useWorkspaceStore((state) => state.runtimeRunId);
  const completedRef = useRef(false);
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (BOOTSTRAP_DISABLED || runId || completedRef.current || inFlightRef.current) return;
    inFlightRef.current = true;

    const store = useWorkspaceStore.getState();
    store.appendLog("info", "bootstrapping scene1 runtime from SceneDocument");

    void frontendApiClient
      .bootstrapScene1Runtime()
      .then((result) => {
        completedRef.current = true;
        const nextStore = useWorkspaceStore.getState();
        nextStore.setRuntimeSceneDocument(result.sceneDocument);
        nextStore.replaceSceneObjects(result.sceneObjects);
        nextStore.setRuntimeRunId(result.runId);
        nextStore.appendLog("success", `runtime run ready: ${result.runId}`);
      })
      .catch((error) => {
        useWorkspaceStore.getState().appendLog("warning", `scene1 runtime bootstrap failed: ${String(error)}`);
      })
      .finally(() => {
        inFlightRef.current = false;
      });
  }, [runId]);

  return null;
}
