import { Group, Vector3 } from 'three';

const AXIS_NAMES = {
  X: 'x',
  Y: 'y',
  Z: 'z',
} as const;

export default class IKJoint extends Group {
  public axis: Vector3;
  public isRootJoint: boolean;
  public isHinge: boolean;
  public isFixed: boolean;
  public isIkJoint: boolean;
  public limit: { lower: number; upper: number };
  public urdfJoint: any;

  constructor(urdfJoint?: any) {
    super();
    this.position.set(0, 0, 0);
    this.axis = new Vector3(0, 1, 0);
    this.isRootJoint = true;
    this.isHinge = false;
    this.isFixed = false;
    this.isIkJoint = true;
    this.limit = { lower: 0, upper: 0 };
    this.urdfJoint = urdfJoint;

    if (urdfJoint) {
      this.position.copy(urdfJoint.position);
      this.rotation.copy(urdfJoint.rotation);
      this.isRootJoint = false;
      this.isHinge = urdfJoint.jointType === 'revolute';
      this.isFixed = urdfJoint.jointType === 'fixed';
      this.axis.copy(urdfJoint.axis);
      this.limit = {
        ...urdfJoint.limit,
      };
    }
  }

  get axisArray(): number[] {
    return this.axis.toArray();
  }

  get axisIdx(): number {
    const arr = this.axisArray;
    let maxIdx = -1;
    let maxVal = 0;
    for (let i = 0; i < arr.length; i++) {
      const abs = Math.abs(arr[i]);
      if (abs > maxVal) {
        maxVal = abs;
        maxIdx = i;
      }
    }
    return maxIdx;
  }

  get axisName(): 'x' | 'y' | 'z' | '' {
    switch (this.axisIdx) {
      case 0:
        return AXIS_NAMES.X;
      case 1:
        return AXIS_NAMES.Y;
      case 2:
        return AXIS_NAMES.Z;
      default:
        return '';
    }
  }

  get axisIsNegative(): boolean {
    return this.axisArray[this.axisIdx] < 0;
  }
}
