import { Group, Object3D, Quaternion, Vector3 } from 'three';
import IKChain from './IKChain';
import IKSolver from './IKSolver';
import type { DeviceConfig, UrdfJointConfig } from '@/types/scene';

export interface BuiltIKResult {
  ikChain: IKChain;
  ikSolver: IKSolver;
  ikTarget: Object3D;
  endEffectorNode: Object3D | null;
  containerGroup: Group;
}

function computeOrigins(
  rootNode: Object3D,
  glbNodes: Object3D[]
): Vector3[] {
  rootNode.updateWorldMatrix(true, true);
  for (const node of glbNodes) {
    node.updateWorldMatrix(true, false);
  }

  const rootWorldPos = new Vector3();
  rootNode.getWorldPosition(rootWorldPos);

  const origins: Vector3[] = [];
  let prevWorldPos = rootWorldPos.clone();

  for (const glbNode of glbNodes) {
    const nodeWorldPos = new Vector3();
    glbNode.getWorldPosition(nodeWorldPos);
    origins.push(new Vector3().subVectors(nodeWorldPos, prevWorldPos));
    prevWorldPos.copy(nodeWorldPos);
  }

  return origins;
}

function printIKDiagnostics(
  rootNode: Object3D,
  glbNodes: Object3D[],
  origins: Vector3[],
  jointConfigs: UrdfJointConfig[]
) {
  console.group('[IK 诊断] 关节详细信息');

  const rootWorldPos = new Vector3();
  rootNode.getWorldPosition(rootWorldPos);
  console.log(
    `Root "${rootNode.name}": worldPos=(${rootWorldPos.x.toFixed(4)}, ${rootWorldPos.y.toFixed(4)}, ${rootWorldPos.z.toFixed(4)})`
  );

  const cumulativeOrigin = rootWorldPos.clone();

  for (let i = 0; i < glbNodes.length; i++) {
    const node = glbNodes[i];
    const cfg = jointConfigs[i];
    const origin = origins[i];
    const nodeWorldPos = new Vector3();
    node.getWorldPosition(nodeWorldPos);
    cumulativeOrigin.add(origin);

    console.log(`Joint[${i}] "${cfg.name}" (node: "${node.name}"):`);
    console.log(
      `  worldPos=(${nodeWorldPos.x.toFixed(4)}, ${nodeWorldPos.y.toFixed(4)}, ${nodeWorldPos.z.toFixed(4)})  origin=(${origin.x.toFixed(4)}, ${origin.y.toFixed(4)}, ${origin.z.toFixed(4)})`
    );
    console.log(
      `  restQuat=(${node.quaternion.x.toFixed(4)}, ${node.quaternion.y.toFixed(4)}, ${node.quaternion.z.toFixed(4)}, ${node.quaternion.w.toFixed(4)})  axis=(${cfg.axis.x}, ${cfg.axis.y}, ${cfg.axis.z})`
    );

    if (Math.abs(node.quaternion.w - 1) > 0.001) {
      const wq = new Quaternion();
      node.getWorldQuaternion(wq);
      const transformed = new Vector3(cfg.axis.x, cfg.axis.y, cfg.axis.z)
        .applyQuaternion(wq)
        .normalize();
      console.log(
        `  ⚠️ restQuat非单位! 轴变换后=(${transformed.x.toFixed(4)}, ${transformed.y.toFixed(4)}, ${transformed.z.toFixed(4)})`
      );
    }
  }

  console.groupEnd();
}

/**
 * 从 DeviceConfig 中的 URDF 信息构建 IK 链。
 * 自动从 GLB 节点世界坐标计算关节偏移（忽略 JSON origin）。
 */
export function buildIKFromDeviceConfig(
  deviceConfig: DeviceConfig,
  glbScene: Object3D
): BuiltIKResult | null {
  const urdf = deviceConfig.urdf;
  if (!urdf?.joints?.length) return null;

  const rootNode = glbScene.getObjectByName(deviceConfig.rootNodeName);
  if (!rootNode) {
    console.warn(`[buildIK] rootNodeName "${deviceConfig.rootNodeName}" not found`);
    return null;
  }

  const glbNodes: Object3D[] = [];
  for (const joint of urdf.joints) {
    const node = glbScene.getObjectByName(joint.nodeName);
    if (!node) {
      console.warn(`[buildIK] joint nodeName "${joint.nodeName}" not found`);
      return null;
    }
    glbNodes.push(node);
  }

  const origins = computeOrigins(rootNode, glbNodes);
  printIKDiagnostics(rootNode, glbNodes, origins, urdf.joints);

  const rootWorldPos = new Vector3();
  rootNode.getWorldPosition(rootWorldPos);

  const container = new Group();
  container.name = `ik_container_${deviceConfig.id}`;
  container.position.copy(rootWorldPos);
  container.visible = false;

  const ikChain = new IKChain();
  ikChain.createFromConfig(
    urdf.joints.map((j, i) => ({
      type: j.type,
      axis: j.axis,
      limit: j.limit,
      origin: { x: origins[i].x, y: origins[i].y, z: origins[i].z },
    })),
    glbNodes,
    container
  );

  const ikSolver = new IKSolver({
    shouldUpdateGLB: true,
    tolerance: 0.001,
    maxNumOfIterations: 50,
  });
  ikSolver.ikChain = ikChain;

  const ikTarget = new Object3D();
  ikTarget.name = `ik_target_${deviceConfig.id}`;

  if (ikChain.endEffector) {
    container.updateMatrixWorld(true);
    const eePos = new Vector3();
    ikChain.endEffector.getWorldPosition(eePos);
    ikTarget.position.copy(eePos);
  }

  ikSolver.target = ikTarget;

  const eeNodeName = urdf.endEffectorNodeName
    || urdf.joints[urdf.joints.length - 1].nodeName;
  const endEffectorNode = glbScene.getObjectByName(eeNodeName) ?? null;

  return {
    ikChain,
    ikSolver,
    ikTarget,
    endEffectorNode,
    containerGroup: container,
  };
}
