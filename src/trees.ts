import * as THREE from 'three';
import { brokenTrees, treeRefs, type Circle, type TreeRef } from './world';

// Knocked-over trees: they topple away from the cab, bounce once, lie there,
// then quietly stand back up once you're well away.

interface Falling { ref: TreeRef; axis: THREE.Vector3; t: number; angle: number; spin: number }

const FALL_TIME = 0.7;
const RESPAWN_AFTER = 25; // seconds lying down
const RESPAWN_DISTANCE = 70; // only when the cab is this far away

export interface TreeHit { at: THREE.Vector3; size: number }

export class Trees {
  private falling: Falling[] = [];
  private m = new THREE.Matrix4();
  private pos = new THREE.Vector3();
  private quat = new THREE.Quaternion();
  private scl = new THREE.Vector3();

  // Turn queued hits into falling trees. carVel is the cab's x/z velocity.
  update(dt: number, carPos: THREE.Vector3, carVel: THREE.Vector2): TreeHit[] {
    const hits: TreeHit[] = [];
    while (brokenTrees.length) {
      const c = brokenTrees.pop()!;
      const ref = treeRefs.get(c);
      if (!ref) continue;
      // Topple in the direction the cab was going: rotate about a horizontal axis at the base.
      const dir = new THREE.Vector3(carVel.x, 0, carVel.y).normalize();
      const axis = new THREE.Vector3(0, 1, 0).cross(dir).normalize();
      this.falling.push({ ref, axis, t: 0, angle: 0, spin: (Math.random() - 0.5) * 0.6 });
      ref.base.decompose(this.pos, this.quat, this.scl);
      hits.push({ at: this.pos.clone(), size: this.scl.x });
    }
    for (const f of this.falling) {
      f.t += dt;
      // Accelerate down, land at about 85°, bounce slightly, settle.
      const k = Math.min(1, f.t / FALL_TIME);
      f.angle = k < 1 ? 1.5 * k * k : 1.48 + Math.sin(Math.min(1, (f.t - FALL_TIME) * 4) * Math.PI) * 0.08 * Math.max(0, 1 - (f.t - FALL_TIME) * 2);
      this.draw(f);
    }
    // Stand trees back up when nobody's looking.
    this.falling = this.falling.filter((f) => {
      const c = f.ref.circle;
      if (f.t > RESPAWN_AFTER && Math.hypot(c.x - carPos.x, c.z - carPos.z) > RESPAWN_DISTANCE) {
        this.restore(f.ref);
        return false;
      }
      return true;
    });
    return hits;
  }

  reset() {
    for (const f of this.falling) this.restore(f.ref);
    this.falling = [];
    brokenTrees.length = 0;
  }

  private restore(ref: TreeRef) {
    ref.circle.down = false;
    for (const mesh of ref.meshes) {
      mesh.setMatrixAt(ref.index, ref.base);
      mesh.instanceMatrix.needsUpdate = true;
    }
  }

  private draw(f: Falling) {
    f.ref.base.decompose(this.pos, this.quat, this.scl);
    const tilt = new THREE.Quaternion().setFromAxisAngle(f.axis, f.angle);
    const twist = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), f.spin * f.angle);
    const q = tilt.multiply(twist).multiply(this.quat);
    this.m.compose(this.pos, q, this.scl);
    for (const mesh of f.ref.meshes) {
      mesh.setMatrixAt(f.ref.index, this.m);
      mesh.instanceMatrix.needsUpdate = true;
    }
  }
}

export type { Circle };
