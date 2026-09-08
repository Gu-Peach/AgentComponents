"use client";

import { Canvas } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";
import { Box, Eye, MousePointer2 } from "lucide-react";
import { useMemo } from "react";
import { RuntimeEventBridge } from "@/components/scene/RuntimeEventBridge";
import { SceneRuntimeAnimator } from "@/components/scene/SceneRuntimeAnimator";
import { SceneObjectMesh } from "@/components/scene/SceneObjectMesh";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";
import type { Vector3Tuple } from "@/types/scene";

function SceneContent() {
  const sceneObjects = useWorkspaceStore((state) => state.sceneObjects);
  const selectedObjectId = useWorkspaceStore((state) => state.selectedObjectId);
  const runtimeDeviceVisuals = useWorkspaceStore((state) => state.runtimeDeviceVisuals);
  const selectSceneObject = useWorkspaceStore((state) => state.selectSceneObject);

  const objectCount = sceneObjects.length;

  return (
    <>
      <color attach="background" args={["#cfd2d5"]} />
      <ambientLight intensity={0.62} />
      <directionalLight castShadow position={[5, 8, 5]} intensity={1.35} shadow-mapSize-width={2048} shadow-mapSize-height={2048} />
      <hemisphereLight args={["#e8f2ff", "#5a5d61", 0.55]} />
      <Grid args={[20, 20]} cellSize={0.5} cellThickness={0.6} sectionSize={2} sectionThickness={1.2} fadeDistance={28} fadeStrength={1.2} position={[0, -0.01, 0]} />
      <axesHelper args={[1.8]} />

      {sceneObjects.map((object) => (
        <SceneObjectMesh
          key={object.id}
          object={object}
          selected={object.id === selectedObjectId}
          visual={runtimeDeviceVisuals[object.id]}
          onSelect={selectSceneObject}
        />
      ))}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.025, 0]} receiveShadow>
        <planeGeometry args={[22, 16]} />
        <meshStandardMaterial color="#c8cacc" roughness={0.74} />
      </mesh>

      <OrbitControls makeDefault enableDamping dampingFactor={0.08} minDistance={3.5} maxDistance={18} />
      <SceneRuntimeAnimator />
      <RuntimeCountBeacon count={objectCount} />
    </>
  );
}

function RuntimeCountBeacon({ count }: { count: number }) {
  return <group userData={{ objectCount: count }} />;
}

function dropPositionFromEvent(event: React.DragEvent<HTMLDivElement>): Vector3Tuple {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width - 0.5) * 10;
  const z = ((event.clientY - rect.top) / rect.height - 0.5) * 7;
  return [Number(x.toFixed(2)), 0.2, Number(z.toFixed(2))];
}

export function SceneViewport() {
  const sceneObjects = useWorkspaceStore((state) => state.sceneObjects);
  const selectedObjectId = useWorkspaceStore((state) => state.selectedObjectId);
  const addAssetToScene = useWorkspaceStore((state) => state.addAssetToScene);
  const selectSceneObject = useWorkspaceStore((state) => state.selectSceneObject);
  const selectedObject = useMemo(
    () => sceneObjects.find((object) => object.id === selectedObjectId),
    [sceneObjects, selectedObjectId],
  );

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const assetId = event.dataTransfer.getData("application/agent-components-asset-id");
    if (!assetId) return;
    addAssetToScene(assetId, dropPositionFromEvent(event));
  }

  return (
    <section
      className="viewport-shell"
      data-testid="scene-viewport"
      aria-label="三维场景渲染区"
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
    >
      <RuntimeEventBridge />
      <div className="viewport-toolbar">
        <MousePointer2 size={15} />
        <span>选择 / Orbit</span>
        <Box size={15} />
        <span>{sceneObjects.length} objects</span>
      </div>

      <Canvas camera={{ position: [6.7, 5.5, 7.4], fov: 48 }} shadows dpr={[1, 1.8]} onPointerMissed={() => selectSceneObject(null)}>
        <SceneContent />
      </Canvas>

      <div className="drop-hint">从左侧拖入模型，或双击资产快速添加</div>
      <div className="scene-status">
        <Eye size={14} />
        {selectedObject ? `选中：${selectedObject.name}` : "未选中对象"}
      </div>
    </section>
  );
}
