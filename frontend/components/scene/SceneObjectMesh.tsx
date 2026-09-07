"use client";

import { Edges, Html } from "@react-three/drei";
import type { ThreeEvent } from "@react-three/fiber";
import type { SceneObject } from "@/types/scene";

interface SceneObjectMeshProps {
  object: SceneObject;
  selected: boolean;
  onSelect: (objectId: string) => void;
}

function degToRad(value: number) {
  return (value * Math.PI) / 180;
}

function ConveyorMesh({ object, selected }: { object: SceneObject; selected: boolean }) {
  const [length, height, width] = object.dimensions;
  const stopPointCount = object.id.includes("output") ? 5 : 4;

  return (
    <group>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[length, height, width]} />
        <meshStandardMaterial color={object.color} roughness={0.52} metalness={0.18} />
        {selected && <Edges color="#57d9ff" />}
      </mesh>
      <mesh position={[0, height / 2 + 0.015, 0]} receiveShadow>
        <boxGeometry args={[length * 0.92, 0.035, width * 0.72]} />
        <meshStandardMaterial color="#171a1f" roughness={0.8} />
      </mesh>
      {Array.from({ length: stopPointCount }).map((_, index) => {
        const t = index / (stopPointCount - 1);
        return (
          <mesh key={index} position={[-length * 0.38 + length * 0.76 * t, height / 2 + 0.052, 0]}>
            <cylinderGeometry args={[0.045, 0.045, 0.012, 18]} />
            <meshStandardMaterial color={index === stopPointCount - 1 ? "#3abf7a" : "#d1b25f"} />
          </mesh>
        );
      })}
    </group>
  );
}

function RobotArmMesh({ object, selected }: { object: SceneObject; selected: boolean }) {
  return (
    <group>
      <mesh position={[0, 0.1, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.34, 0.4, 0.2, 32]} />
        <meshStandardMaterial color="#2c3239" roughness={0.55} metalness={0.2} />
        {selected && <Edges color="#57d9ff" />}
      </mesh>
      <mesh position={[0, 0.55, 0]} castShadow>
        <cylinderGeometry args={[0.14, 0.16, 0.86, 24]} />
        <meshStandardMaterial color={object.color} roughness={0.45} metalness={0.08} />
      </mesh>
      <mesh position={[0.42, 1.0, 0]} rotation={[0, 0, -0.62]} castShadow>
        <boxGeometry args={[0.84, 0.18, 0.18]} />
        <meshStandardMaterial color="#f6f7f9" roughness={0.36} />
      </mesh>
      <mesh position={[0.96, 0.78, 0]} rotation={[0, 0, 0.52]} castShadow>
        <boxGeometry args={[0.62, 0.14, 0.14]} />
        <meshStandardMaterial color="#f6f7f9" roughness={0.36} />
      </mesh>
      <mesh position={[1.3, 0.65, 0]} castShadow>
        <boxGeometry args={[0.16, 0.08, 0.34]} />
        <meshStandardMaterial color="#20242a" roughness={0.6} />
      </mesh>
      <mesh position={[0.04, 1.02, 0]}>
        <sphereGeometry args={[0.16, 24, 16]} />
        <meshStandardMaterial color="#3abf7a" emissive="#1a6a45" emissiveIntensity={0.22} />
      </mesh>
    </group>
  );
}

function CarrierMesh({ object, selected }: { object: SceneObject; selected: boolean }) {
  const [length, height, width] = object.dimensions;
  return (
    <group>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[length, height, width]} />
        <meshStandardMaterial color={object.color} roughness={0.5} metalness={0.1} />
        {selected && <Edges color="#57d9ff" />}
      </mesh>
      {Array.from({ length: 12 }).map((_, index) => {
        const column = index % 4;
        const row = Math.floor(index / 4);
        return (
          <mesh key={index} position={[-0.36 + column * 0.24, height / 2 + 0.12, -0.23 + row * 0.23]} castShadow>
            <boxGeometry args={[0.15, 0.15, 0.15]} />
            <meshStandardMaterial color="#f0b84f" roughness={0.45} />
          </mesh>
        );
      })}
    </group>
  );
}

function StorageRackMesh({ object, selected }: { object: SceneObject; selected: boolean }) {
  const [length, height, width] = object.dimensions;
  return (
    <group>
      <mesh position={[0, height / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[length, height, width]} />
        <meshStandardMaterial color={object.color} transparent opacity={0.42} roughness={0.55} />
        {selected && <Edges color="#57d9ff" />}
      </mesh>
      {Array.from({ length: 9 }).map((_, index) => {
        const col = index % 3;
        const row = Math.floor(index / 3);
        return (
          <mesh key={index} position={[-0.42 + col * 0.42, 0.35 + row * 0.48, -width / 2 - 0.02]}>
            <boxGeometry args={[0.32, 0.28, 0.035]} />
            <meshStandardMaterial color="#15181d" />
          </mesh>
        );
      })}
    </group>
  );
}

function GenericDeviceMesh({ object, selected }: { object: SceneObject; selected: boolean }) {
  const [length, height, width] = object.dimensions;
  return (
    <mesh castShadow receiveShadow>
      <boxGeometry args={[length, height, width]} />
      <meshStandardMaterial color={object.color} roughness={0.48} metalness={0.08} />
      {selected && <Edges color="#57d9ff" />}
    </mesh>
  );
}

function ShapeForType({ object, selected }: { object: SceneObject; selected: boolean }) {
  if (object.type === "conveyor") return <ConveyorMesh object={object} selected={selected} />;
  if (object.type === "robot_arm") return <RobotArmMesh object={object} selected={selected} />;
  if (object.type === "workpiece_carrier") return <CarrierMesh object={object} selected={selected} />;
  if (object.type === "storage_rack") return <StorageRackMesh object={object} selected={selected} />;
  if (object.type === "rotary_table") {
    return (
      <group>
        <mesh castShadow receiveShadow>
          <cylinderGeometry args={[object.dimensions[0] / 2, object.dimensions[0] / 2, object.dimensions[1], 48]} />
          <meshStandardMaterial color={object.color} roughness={0.4} metalness={0.15} />
          {selected && <Edges color="#57d9ff" />}
        </mesh>
        <mesh position={[0, object.dimensions[1] / 2 + 0.035, 0]}>
          <cylinderGeometry args={[object.dimensions[0] * 0.34, object.dimensions[0] * 0.34, 0.04, 48]} />
          <meshStandardMaterial color="#20242a" />
        </mesh>
      </group>
    );
  }
  if (object.type === "workpiece") {
    return (
      <mesh castShadow receiveShadow>
        <boxGeometry args={object.dimensions} />
        <meshStandardMaterial color={object.color} roughness={0.45} />
        {selected && <Edges color="#57d9ff" />}
      </mesh>
    );
  }
  return <GenericDeviceMesh object={object} selected={selected} />;
}

export function SceneObjectMesh({ object, selected, onSelect }: SceneObjectMeshProps) {
  const { position, rotation, scale } = object.transform;

  function handleClick(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    onSelect(object.id);
  }

  return (
    <group
      position={position}
      rotation={[degToRad(rotation[0]), degToRad(rotation[1]), degToRad(rotation[2])]}
      scale={scale}
      onClick={handleClick}
    >
      <ShapeForType object={object} selected={selected} />
      <Html position={[0, Math.max(object.dimensions[1], 0.35) + 0.34, 0]} center distanceFactor={10}>
        <div
          style={{
            border: selected ? "1px solid #57d9ff" : "1px solid rgba(255,255,255,0.16)",
            borderRadius: 4,
            background: selected ? "rgba(15, 142, 199, 0.88)" : "rgba(18, 21, 25, 0.75)",
            color: "white",
            fontSize: 11,
            padding: "3px 6px",
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          {object.name}
        </div>
      </Html>
    </group>
  );
}
