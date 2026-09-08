"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import type { Object3D } from "three";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";
import { frontendApiClient } from "@/lib/api-client";
import { buildGlbRuntimeBindings, createGlbActionRuntime, type GlbActionRuntime, type GlbRuntimeCallbackResult } from "@/lib/glb-runtime";
import type { RuntimeAnimationAction } from "@/types/scene";

export function SceneRuntimeAnimator() {
  const { scene } = useThree();
  const runtimeSceneDocument = useWorkspaceStore((state) => state.runtimeSceneDocument);
  const runtimeGlbLoaded = useWorkspaceStore((state) => state.runtimeGlbLoaded);
  const glbBindings = useMemo(() => buildGlbRuntimeBindings(runtimeSceneDocument), [runtimeSceneDocument]);
  const glbActionRuntimes = useRef(new Map<string, GlbActionRuntime>());
  const waitingForGlbLogged = useRef(new Set<string>());

  useEffect(() => {
    for (const runtime of glbActionRuntimes.current.values()) runtime.dispose();
    glbActionRuntimes.current.clear();
    waitingForGlbLogged.current.clear();
  }, [runtimeSceneDocument, runtimeGlbLoaded]);

  useFrame((_, delta) => {
    const store = useWorkspaceStore.getState();
    const actions = [...store.activeRuntimeActions];
    if (actions.length === 0) return;

    const activeActionIds = new Set(actions.map((action) => action.actionId));
    for (const [actionId, runtime] of glbActionRuntimes.current.entries()) {
      if (!activeActionIds.has(actionId)) {
        runtime.dispose();
        glbActionRuntimes.current.delete(actionId);
      }
    }

    for (const action of actions) {
      if (!runtimeGlbLoaded) {
        if (!waitingForGlbLogged.current.has(action.actionId)) {
          waitingForGlbLogged.current.add(action.actionId);
          store.appendLog("warning", `runtime action waiting for GLB: ${action.instanceId}.${action.behaviorId}`);
        }
        continue;
      }

      const elapsed = Math.min(action.elapsed + delta, action.duration);
      const progress = action.duration <= 0 ? 1 : elapsed / action.duration;
      const glbResult = runGlbRuntimeFrame(action, progress, scene, glbBindings, glbActionRuntimes.current);

      if (glbResult) {
        applyCallbackResult(action, glbResult);
      } else {
        glbActionRuntimes.current.get(action.actionId)?.dispose();
        glbActionRuntimes.current.delete(action.actionId);
        const failed = store.completeRuntimeAction(action.actionId, "failed");
        if (failed) notifyBackendActionComplete(failed, "failed", { reason: "glb_runtime_binding_failed" });
        continue;
      }

      if (progress >= 1) {
        glbActionRuntimes.current.get(action.actionId)?.dispose();
        glbActionRuntimes.current.delete(action.actionId);
        const completed = store.completeRuntimeAction(action.actionId, "done");
        if (completed) notifyBackendActionComplete(completed, "done");
      } else {
        store.updateRuntimeAction(action.actionId, { elapsed });
      }
    }
  });

  return null;
}

function runGlbRuntimeFrame(
  action: RuntimeAnimationAction,
  progress: number,
  scene: Object3D,
  glbBindings: ReturnType<typeof buildGlbRuntimeBindings>,
  runtimes: Map<string, GlbActionRuntime>,
): GlbRuntimeCallbackResult | null {
  if (!glbBindings.assetUrl) return null;
  let runtime = runtimes.get(action.actionId);
  if (!runtime) {
    runtime = createGlbActionRuntime(action, scene, glbBindings) ?? undefined;
    if (!runtime) return null;
    runtimes.set(action.actionId, runtime);
  }
  return runtime.update(progress);
}

function applyCallbackResult(action: RuntimeAnimationAction, result: GlbRuntimeCallbackResult) {
  const store = useWorkspaceStore.getState();
  if (result.subjectTransform) {
    store.applyRuntimeObjectTransform(result.subjectTransform.objectId, result.subjectTransform.transform);
  }
  store.setRuntimeDeviceVisual(action.instanceId, result.deviceVisual);
}

function notifyBackendActionComplete(action: RuntimeAnimationAction, status: "done" | "failed", extraPayload: Record<string, unknown> = {}) {
  const runId = action.runId ?? useWorkspaceStore.getState().runtimeRunId;
  if (!runId) return;

  void frontendApiClient
    .completeRuntimeAction(runId, action.actionId, {
      status,
      payload: {
        task_id: action.taskId,
        behavior_id: action.behaviorId,
        instance_id: action.instanceId,
        status,
        ...extraPayload,
      },
    })
    .catch((error) => {
      useWorkspaceStore.getState().appendLog("warning", `runtime completion callback failed: ${String(error)}`);
    });
}
