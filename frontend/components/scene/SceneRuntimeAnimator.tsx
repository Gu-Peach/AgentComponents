"use client";

import { useFrame } from "@react-three/fiber";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";
import { frontendApiClient } from "@/lib/api-client";
import { interpolateWaypoints } from "@/lib/runtime-behavior";
import type { RuntimeAnimationAction, RuntimeVector3, SceneObject, Vector3Tuple } from "@/types/scene";

export function SceneRuntimeAnimator() {
  useFrame((_, delta) => {
    const store = useWorkspaceStore.getState();
    const actions = [...store.activeRuntimeActions];
    if (actions.length === 0) return;

    for (const action of actions) {
      const elapsed = Math.min(action.elapsed + delta, action.duration);
      const progress = action.duration <= 0 ? 1 : elapsed / action.duration;

      if (action.kind === "conveyor_linear") {
        animateConveyor(action, progress);
      } else {
        animateRobotPickPlace(action, progress);
      }

      if (progress >= 1) {
        const completed = store.completeRuntimeAction(action.actionId);
        if (completed) notifyBackendActionComplete(completed);
      } else {
        store.updateRuntimeAction(action.actionId, { elapsed });
      }
    }
  });

  return null;
}

function animateConveyor(action: RuntimeAnimationAction, progress: number) {
  const store = useWorkspaceStore.getState();
  const position = interpolateWaypoints(action.waypoints, progress);
  if (action.subjectId) {
    store.applyRuntimeObjectTransform(action.subjectId, { position: tuple(position) });
  }

  store.setRuntimeDeviceVisual(action.instanceId, {
    activeActionId: action.actionId,
    beltOffset: (progress * 6) % 1,
  });
}

function animateRobotPickPlace(action: RuntimeAnimationAction, progress: number) {
  const store = useWorkspaceStore.getState();
  const position = interpolateWaypoints(action.waypoints, progress);
  if (action.subjectId) {
    store.applyRuntimeObjectTransform(action.subjectId, { position: tuple(position) });
  }

  const sceneObjects = store.sceneObjects;
  const robot = sceneObjects.find((object) => object.id === action.instanceId);
  const target = action.waypoints[Math.min(action.waypoints.length - 1, Math.max(0, Math.floor(progress * action.waypoints.length)))] ?? position;
  const pose = robot ? robotPose(robot, target, progress) : fallbackRobotPose(progress);

  store.setRuntimeDeviceVisual(action.instanceId, {
    activeActionId: action.actionId,
    armPhase: progress < 0.18 ? "approach" : progress < 0.82 ? "execute" : "return",
    ...pose,
    gripperClosed: progress >= 0.22 && progress <= 0.78,
  });
}

function robotPose(robot: SceneObject, target: RuntimeVector3, progress: number) {
  const [rx, , rz] = robot.transform.position;
  const yaw = Math.atan2(target.z - rz, target.x - rx) - degToRad(robot.transform.rotation[1]);
  const reachPulse = Math.sin(Math.PI * progress);
  const dipPulse = Math.sin(Math.PI * Math.min(1, progress * 2));
  return {
    baseYaw: yaw,
    shoulder: -0.25 - reachPulse * 0.42,
    elbow: 0.55 + reachPulse * 0.62,
    wrist: -0.12 - dipPulse * 0.24,
  };
}

function fallbackRobotPose(progress: number) {
  const pulse = Math.sin(Math.PI * progress);
  return {
    baseYaw: 0,
    shoulder: -0.25 - pulse * 0.42,
    elbow: 0.55 + pulse * 0.62,
    wrist: -0.12,
  };
}

function notifyBackendActionComplete(action: RuntimeAnimationAction) {
  const runId = action.runId ?? useWorkspaceStore.getState().runtimeRunId;
  if (!runId) return;

  void frontendApiClient
    .completeRuntimeAction(runId, action.actionId, {
      task_id: action.taskId,
      behavior_id: action.behaviorId,
      instance_id: action.instanceId,
      status: "done",
    })
    .catch((error) => {
      useWorkspaceStore.getState().appendLog("warning", `runtime completion callback failed: ${String(error)}`);
    });
}

function tuple(position: RuntimeVector3): Vector3Tuple {
  return [round(position.x), round(position.y), round(position.z)];
}

function round(value: number): number {
  return Number(value.toFixed(4));
}

function degToRad(value: number): number {
  return (value * Math.PI) / 180;
}
