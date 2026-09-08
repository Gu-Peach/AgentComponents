"use client";

import { useGLTF } from "@react-three/drei";
import { useEffect, useMemo } from "react";
import type { Object3D } from "three";
import { buildGlbRuntimeBindings, findRenderableGlbObjectIds } from "@/lib/glb-runtime";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

export function SceneGlbLayer() {
  const sceneDocument = useWorkspaceStore((state) => state.runtimeSceneDocument);
  const bindings = useMemo(() => buildGlbRuntimeBindings(sceneDocument), [sceneDocument]);
  const assetUrl = bindings.assetUrl;
  const setRuntimeGlbLoaded = useWorkspaceStore((state) => state.setRuntimeGlbLoaded);
  const setRuntimeGlbObjectIds = useWorkspaceStore((state) => state.setRuntimeGlbObjectIds);

  useEffect(() => {
    setRuntimeGlbLoaded(false);
    setRuntimeGlbObjectIds([]);
  }, [assetUrl, setRuntimeGlbLoaded, setRuntimeGlbObjectIds]);

  if (!assetUrl) return null;
  return <LoadedSceneGlb assetUrl={assetUrl} bindings={bindings} />;
}

function LoadedSceneGlb({ assetUrl, bindings }: { assetUrl: string; bindings: ReturnType<typeof buildGlbRuntimeBindings> }) {
  const gltf = useGLTF(assetUrl) as { scene: Object3D };
  const setRuntimeGlbLoaded = useWorkspaceStore((state) => state.setRuntimeGlbLoaded);
  const setRuntimeGlbObjectIds = useWorkspaceStore((state) => state.setRuntimeGlbObjectIds);
  const appendLog = useWorkspaceStore((state) => state.appendLog);

  const glbScene = useMemo(() => {
    const cloned = gltf.scene.clone(true);
    cloned.name = "SceneDocumentGLB";
    cloned.traverse((node) => {
      node.castShadow = true;
      node.receiveShadow = true;
    });
    return cloned;
  }, [gltf.scene]);

  useEffect(() => {
    const boundObjectIds = findRenderableGlbObjectIds(bindings, glbScene);
    setRuntimeGlbObjectIds(boundObjectIds);
    setRuntimeGlbLoaded(true);
    appendLog("success", `scene GLB loaded: ${assetUrl} (${boundObjectIds.length} bound objects)`);
    return () => {
      setRuntimeGlbLoaded(false);
      setRuntimeGlbObjectIds([]);
    };
  }, [appendLog, assetUrl, bindings, glbScene, setRuntimeGlbLoaded, setRuntimeGlbObjectIds]);

  return <primitive object={glbScene} />;
}

useGLTF.preload("/test/scene1/1.glb");
