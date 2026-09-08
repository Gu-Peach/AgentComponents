import { Object3D, Quaternion } from 'three';
import IKChain from './IKChain';
import ccdIKSolver from './ccdIKSolver';

export default class IKSolver {
  private _ikChain: IKChain | null = null;
  private _target: Object3D | null = null;
  
  public isHybrid: boolean;
  public tolerance: number;
  public maxNumOfIterations: number;
  public shouldUpdateURDFRobot: boolean;
  public shouldUpdateGLB: boolean;

  constructor(config: {
    isHybrid?: boolean;
    tolerance?: number;
    maxNumOfIterations?: number;
    shouldUpdateURDFRobot?: boolean;
    shouldUpdateGLB?: boolean;
  } = {}) {
    this.isHybrid = config.isHybrid || false;
    this.tolerance = config.tolerance || 0.01;
    this.maxNumOfIterations = config.maxNumOfIterations || 10;
    this.shouldUpdateURDFRobot = config.shouldUpdateURDFRobot || false;
    this.shouldUpdateGLB = config.shouldUpdateGLB ?? false;
  }

  get ikChain() {
    return this._ikChain;
  }

  set ikChain(newIkChain: IKChain | null) {
    this._ikChain = newIkChain;
  }

  get target() {
    return this._target;
  }

  set target(newTarget: Object3D | null) {
    this._target = newTarget;
  }

  setConfig(config: Partial<IKSolver>) {
    Object.assign(this, config);
  }

  solve() {
    if (!this.ikChain || !this.target) return;

    ccdIKSolver(
      this.ikChain,
      this.target.position,
      this.tolerance,
      this.maxNumOfIterations
    );

    if (this.shouldUpdateGLB) {
      this._updateGLBNodes();
    } else if (this.shouldUpdateURDFRobot) {
      this._updateURDFRobot();
    }
  }

  private _updateURDFRobot() {
    if (!this.ikChain) return;
    
    const { ikJoints, urdfJoints } = this.ikChain;
    for (let idx = 0; idx < urdfJoints.length; idx++) {
      const ikJoint = ikJoints[idx + 1];
      const urdfJoint = urdfJoints[idx];

      urdfJoint.rotation.copy(ikJoint.rotation);
    }
  }

  private _tempQuat = new Quaternion();
  private _parentWorldQuat = new Quaternion();

  /**
   * 世界四元数匹配法：将 IK 链的求解结果回写到 GLB 节点。
   *
   * desired_world = W_ik * restWorldQuat
   * glbNode.quat  = parentWorld⁻¹ * desired_world
   */
  private _updateGLBNodes() {
    if (!this.ikChain) return;

    const { ikJoints, urdfJoints, restWorldQuaternions } = this.ikChain;
    const useWorldMatch = restWorldQuaternions.length === urdfJoints.length;

    for (let idx = 0; idx < urdfJoints.length; idx++) {
      const ikJoint = ikJoints[idx + 1];
      const glbNode = urdfJoints[idx];

      if (useWorldMatch) {
        ikJoint.getWorldQuaternion(this._tempQuat);

        if (glbNode.parent) {
          glbNode.parent.getWorldQuaternion(this._parentWorldQuat);
        } else {
          this._parentWorldQuat.identity();
        }

        glbNode.quaternion
          .copy(this._parentWorldQuat)
          .invert()
          .multiply(this._tempQuat)
          .multiply(restWorldQuaternions[idx]);
      } else {
        glbNode.rotation.copy(ikJoint.rotation);
      }
    }
  }
}
