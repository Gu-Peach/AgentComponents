"use client";

import { Canvas } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";
import { Box, Eye, MousePointer2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { ACESFilmicToneMapping, PMREMGenerator, SRGBColorSpace } from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { useThree } from "@react-three/fiber";
import { RuntimeEventBridge } from "@/components/scene/RuntimeEventBridge";
import { SceneGlbLayer } from "@/components/scene/SceneGlbLayer";
import { SceneRuntimeBootstrap } from "@/components/scene/SceneRuntimeBootstrap";
import { SceneRuntimeAnimator } from "@/components/scene/SceneRuntimeAnimator";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";
import type { Vector3Tuple } from "@/types/scene";

function SceneContent() {
  const sceneObjects = useWorkspaceStore((state) => state.sceneObjects);

  const objectCount = sceneObjects.length;

  return (
    <>
      <SceneEnvironment />
      <color attach="background" args={["#cfd2d5"]} />
      <ambientLight intensity={0.86} />
      <directionalLight castShadow position={[5, 8, 5]} intensity={1.2} shadow-mapSize-width={2048} shadow-mapSize-height={2048} />
      <hemisphereLight args={["#f3f7ff", "#6b6d70", 0.75]} />
      <Grid args={[20, 20]} cellSize={0.5} cellThickness={0.6} sectionSize={2} sectionThickness={1.2} fadeDistance={28} fadeStrength={1.2} position={[0, -0.01, 0]} />
      <axesHelper args={[1.8]} />

      <SceneGlbLayer />

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

function SceneEnvironment() {
  const { gl, scene } = useThree();

  useEffect(() => {
    gl.outputColorSpace = SRGBColorSpace;
    gl.toneMapping = ACESFilmicToneMapping;
    gl.toneMappingExposure = 1.15;

    const pmrem = new PMREMGenerator(gl);
    const environmentScene = new RoomEnvironment();
    const environmentMap = pmrem.fromScene(environmentScene, 0.04).texture;
    const previousEnvironment = scene.environment;

    scene.environment = environmentMap;

    return () => {
      scene.environment = previousEnvironment;
      environmentMap.dispose();
      environmentScene.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);

  return null;
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
      <SceneRuntimeBootstrap />
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
