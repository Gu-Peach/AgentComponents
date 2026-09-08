import { AxesHelper } from 'three';
import IKChain from './IKChain';

export default class IKHelper {
  private ikChain: IKChain;

  constructor(ikChain: IKChain) {
    this.ikChain = ikChain;
  }

  visualizeIKChain() {
    const { ikJoints } = this.ikChain;
    
    ikJoints.forEach((ikJoint) => {
      const axesHelper = new AxesHelper(0.1);
      ikJoint.add(axesHelper);
    });
  }
}
