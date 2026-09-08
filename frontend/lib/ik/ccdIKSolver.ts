import { Vector3, Quaternion } from 'three';
import IKChain from './IKChain';

const endEffectorWorldPosition = new Vector3();
const endEffectorWorldToLocalPosition = new Vector3();
const targetWorldToLocalPosition = new Vector3();
const fromToQuaternion = new Quaternion();
const inverseQuaternion = new Quaternion();
const jointAxisAfterRotation = new Vector3();

function getIKJointRotationAngle(ikJoint: any): number {
  const { axisName, axis } = ikJoint;
  const sinHalf = ikJoint.quaternion[axisName] / axis[axisName];
  const cosHalf = ikJoint.quaternion.w;
  return Math.atan2(sinHalf, cosHalf) * 2;
}

function clampIKJointRotationAngle(
  ikJointRotationAngle: number,
  limit: { lower: number; upper: number }
): [number, boolean] {
  const { lower, upper } = limit;
  let isClamped = false;
  
  if (ikJointRotationAngle < lower) {
    isClamped = true;
    return [lower, isClamped];
  }

  if (ikJointRotationAngle > upper) {
    isClamped = true;
    return [upper, isClamped];
  }

  return [ikJointRotationAngle, isClamped];
}

export default function ccdIKSolver(
  ikChain: IKChain,
  targetPosition: Vector3,
  tolerance: number,
  maxNumOfIterations: number
) {
  const { ikJoints, endEffector } = ikChain;
  if (!endEffector) return;

  let endEffectorTargetDistance = endEffector
    .worldToLocal(targetWorldToLocalPosition.copy(targetPosition))
    .length();
  let numOfIterations = 0;

  while (
    endEffectorTargetDistance > tolerance &&
    numOfIterations <= maxNumOfIterations
  ) {
    for (let idx = ikJoints.length - 2; idx >= 0; idx--) {
      const ikJoint = ikJoints[idx];
      if (ikJoint.isFixed) {
        ikJoint.updateMatrixWorld();
        continue;
      }

      endEffector.getWorldPosition(endEffectorWorldPosition);

      // Rotate the joint from end effector to goal, so that the end-effector
      // can meet the target.
      // https://sites.google.com/site/auraliusproject/ccd-algorithm

      // Get the direction from current joint to end effector
      const directionToEndEffector = ikJoint
        .worldToLocal(
          endEffectorWorldToLocalPosition.copy(endEffectorWorldPosition)
        )
        .normalize();

      // Get the direction from current joint to target
      const directionToTarget = ikJoint
        .worldToLocal(targetWorldToLocalPosition.copy(targetPosition))
        .normalize();

      fromToQuaternion.setFromUnitVectors(
        directionToEndEffector,
        directionToTarget
      );
      ikJoint.quaternion.multiply(fromToQuaternion);

      // Constrain the joint rotation to its hinge axis
      if (ikJoint.isHinge || ikJoint.isRootJoint) {
        inverseQuaternion.copy(ikJoint.quaternion).invert();
        jointAxisAfterRotation
          .copy(ikJoint.axis)
          .applyQuaternion(inverseQuaternion);

        fromToQuaternion.setFromUnitVectors(
          ikJoint.axis,
          jointAxisAfterRotation
        );
        ikJoint.quaternion.multiply(fromToQuaternion);
      }

      // Apply hinge limits
      if (ikJoint.limit) {
        const ikJointRotationAngle = getIKJointRotationAngle(ikJoint);
        const [clampedIKJointRotationAngle, isClamped] =
          clampIKJointRotationAngle(ikJointRotationAngle, ikJoint.limit);

        if (isClamped) {
          ikJoint.quaternion.setFromAxisAngle(
            ikJoint.axis,
            clampedIKJointRotationAngle
          );
        }
      }

      ikJoint.updateMatrixWorld();
    }

    endEffectorTargetDistance = endEffector
      .worldToLocal(targetWorldToLocalPosition.copy(targetPosition))
      .length();
    numOfIterations++;
  }
}
