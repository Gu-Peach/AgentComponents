import IKJoint from "./IKJoint";
import { Euler, Group, Object3D, Quaternion, Vector3 } from "three";

export interface JointConfig {
  type: string;
  axis: { x: number; y: number; z: number };
  limit?: { lower: number; upper: number };
  origin?: { x: number; y: number; z: number };
}

export default class IKChain {
  private _ikJoints: IKJoint[] = [];
  private _urdfJoints: any[] = [];
  private _restQuaternions: Quaternion[] = [];
  private _restWorldQuaternions: Quaternion[] = [];
  private _rootJoint: IKJoint | null = null;
  private _urdfBaseJointId: string = "";
  private _endEffector: IKJoint | null = null;

  addJoint(parent: IKJoint | Group, ikJoint: IKJoint) {
    parent.add(ikJoint);
    this._ikJoints.push(ikJoint);
  }

  get ikJoints() {
    return this._ikJoints;
  }

  get rootJoint() {
    return this._rootJoint;
  }

  get endEffector() {
    return this._endEffector;
  }

  get urdfJoints() {
    return this._urdfJoints;
  }

  get restQuaternions() {
    return this._restQuaternions;
  }

  get restWorldQuaternions() {
    return this._restWorldQuaternions;
  }

  createFromURDFRobot(urdfRobot: any, rootJointParent: Group) {
    this._rootJoint = new IKJoint();
    this.addJoint(rootJointParent, this._rootJoint);

    const urdfRobotBaseJoint = this._findURDFBaseJoint(urdfRobot);
    this._urdfBaseJointId = urdfRobotBaseJoint.id;

    this._traverseURDFJoints(this._rootJoint, urdfRobotBaseJoint);

    return this;
  }

  createFromConfig(
    jointConfigs: JointConfig[],
    glbNodes: Object3D[],
    rootParent: Group
  ) {
    this._rootJoint = new IKJoint();
    this.addJoint(rootParent, this._rootJoint);

    let parentIkJoint: IKJoint = this._rootJoint;

    for (let i = 0; i < jointConfigs.length; i++) {
      const cfg = jointConfigs[i];
      const glbNode = glbNodes[i];

      this._restQuaternions.push(glbNode.quaternion.clone());

      const worldQuat = new Quaternion();
      glbNode.getWorldQuaternion(worldQuat);
      this._restWorldQuaternions.push(worldQuat);

      const worldAxis = new Vector3(cfg.axis.x, cfg.axis.y, cfg.axis.z)
        .applyQuaternion(worldQuat)
        .normalize();

      const proxy = {
        position: new Vector3(cfg.origin?.x ?? 0, cfg.origin?.y ?? 0, cfg.origin?.z ?? 0),
        rotation: new Euler(0, 0, 0),
        jointType: cfg.type,
        axis: worldAxis,
        limit: cfg.limit || { lower: -Math.PI, upper: Math.PI },
      };

      this._urdfJoints.push(glbNode);
      const ikJoint = new IKJoint(proxy);
      this.addJoint(parentIkJoint, ikJoint);
      parentIkJoint = ikJoint;
    }

    this._endEffector = parentIkJoint;
    return this;
  }

  private _findURDFBaseJoint({ children }: any) {
    let baseJoint = null;
    for (const child of children) {
      if (!child.isURDFJoint) continue;

      const [urdfLink] = child.children;
      const hasNextURDFJoint = urdfLink.children.some(
        (child: any) => child.isURDFJoint,
      );
      if (hasNextURDFJoint) {
        baseJoint = child;
        break;
      }
    }

    return baseJoint;
  }

  private _traverseURDFJoints(parentIkJoint: IKJoint, urdfJoint: any) {
    this._urdfJoints.push(urdfJoint);

    const ikJoint = new IKJoint(urdfJoint);
    this.addJoint(parentIkJoint, ikJoint);
    parentIkJoint = ikJoint;

    const [urdfLink] = urdfJoint.children;
    const { children } = urdfLink;
    const nextUrdfJoint = children.find((child: any) => child.isURDFJoint);
    const isEndEffector =
      ikJoint.isFixed && urdfJoint.id !== this._urdfBaseJointId;

    if (!nextUrdfJoint || isEndEffector) {
      this._endEffector = ikJoint;
      return;
    }

    this._traverseURDFJoints(parentIkJoint, nextUrdfJoint);
  }
}
