import * as THREE from 'three';
import type { Input } from './input';
import { collide, heightAt } from './world';
import type { CarModel } from './models';

export const MAX_SPEED = 42;
const ACCEL = 26;
const BRAKE = 45;
const REVERSE_MAX = 12;
export const GRAVITY = 30;
const STEER = 2.3;
// The car leaves the ground when the road drops away faster than this (units/s).
const LAUNCH = 4.5;
export const CAR_RADIUS = 1.6;

export interface StepEvents { impact: number; landed: number }

// Arcade physics: grip-based steering on the ground, ballistic in the air.
export class Car {
  pos = new THREE.Vector3();
  vel = new THREE.Vector2(); // x/z
  vy = 0;
  yaw = 0;
  grounded = true;
  airTime = 0;
  steerInput = 0;
  lateral = 0;
  forward = 0;
  private pitch = 0;
  private roll = 0;

  constructor(public model: CarModel) {}

  reset(x: number, z: number, yaw: number) {
    this.pos.set(x, heightAt(x, z), z);
    this.vel.set(0, 0);
    this.vy = 0;
    this.yaw = yaw;
    this.grounded = true;
    this.airTime = 0;
  }

  get speed() { return this.vel.length(); }
  get fwd() { return new THREE.Vector2(Math.sin(this.yaw), Math.cos(this.yaw)); }

  step(dt: number, inp: Input): StepEvents {
    const ev: StepEvents = { impact: 0, landed: 0 };
    const fx = Math.sin(this.yaw), fz = Math.cos(this.yaw);
    const rx = -fz, rz = fx;
    let vf = this.vel.x * fx + this.vel.y * fz;
    let vs = this.vel.x * rx + this.vel.y * rz;
    this.steerInput = inp.steer;

    if (this.grounded) {
      if (inp.throttle > 0 && vf >= -0.5) vf += ACCEL * inp.throttle * Math.max(0, 1 - (vf / MAX_SPEED) ** 2) * dt;
      if (inp.brake > 0) {
        if (vf > 0.5) vf -= BRAKE * inp.brake * dt;
        else vf = Math.max(-REVERSE_MAX, vf - 14 * inp.brake * dt);
      }
      if (inp.throttle > 0 && vf < -0.5) vf += BRAKE * inp.throttle * dt;
      vf -= vf * 0.35 * dt + Math.sign(vf) * Math.min(Math.abs(vf), 1.5 * dt);
      // Hills slow you going up and speed you up going down.
      const slope = (heightAt(this.pos.x + fx, this.pos.z + fz) - heightAt(this.pos.x - fx, this.pos.z - fz)) / 2;
      vf -= 10 * (slope / Math.sqrt(1 + slope * slope)) * dt;

      const grip = inp.handbrake ? 1.3 : 7;
      vs *= Math.exp(-grip * dt);
      if (inp.handbrake) vf -= Math.sign(vf) * Math.min(Math.abs(vf), 5 * dt);

      const s = Math.abs(vf);
      const turn = STEER * Math.min(1, s / 6) * (1 - 0.4 * Math.min(1, s / MAX_SPEED)) * (inp.handbrake ? 1.5 : 1);
      this.yaw -= inp.steer * turn * Math.sign(vf) * dt;
    } else {
      this.yaw -= inp.steer * 0.8 * dt;
    }
    this.forward = vf;
    this.lateral = vs;
    this.vel.set(fx * vf + rx * vs, fz * vf + rz * vs);

    this.pos.x += this.vel.x * dt;
    this.pos.z += this.vel.y * dt;
    ev.impact = collide(this.pos, this.vel, CAR_RADIUS);

    const ground = heightAt(this.pos.x, this.pos.z);
    if (this.grounded) {
      const groundVy = (ground - this.pos.y) / dt;
      if (groundVy < this.vy - GRAVITY * dt - LAUNCH && this.speed > 8) {
        this.grounded = false;
        this.airTime = 0;
        this.vy -= GRAVITY * dt;
        this.pos.y += this.vy * dt;
      } else {
        this.vy = groundVy;
        this.pos.y = ground;
      }
    } else {
      this.vy -= GRAVITY * dt;
      this.pos.y += this.vy * dt;
      this.airTime += dt;
      if (this.pos.y <= ground) {
        this.pos.y = ground;
        this.grounded = true;
        ev.landed = this.airTime;
        this.vel.multiplyScalar(this.airTime > 0.8 ? 0.9 : 0.97);
        this.vy = 0;
      }
    }
    return ev;
  }

  // Called once per rendered frame.
  sync(dt: number) {
    const { root, body, wheels, steer, spinner } = this.model;
    root.position.copy(this.pos);
    root.rotation.y = this.yaw;
    const fx = Math.sin(this.yaw), fz = Math.cos(this.yaw);
    let tp: number, tr: number;
    if (this.grounded) {
      const sf = (heightAt(this.pos.x + fx * 1.6, this.pos.z + fz * 1.6) - heightAt(this.pos.x - fx * 1.6, this.pos.z - fz * 1.6)) / 3.2;
      const sr = (heightAt(this.pos.x - fz, this.pos.z + fx) - heightAt(this.pos.x + fz, this.pos.z - fx)) / 2;
      tp = -Math.atan(sf);
      tr = -Math.atan(sr) + THREE.MathUtils.clamp(this.lateral * 0.012, -0.08, 0.08);
    } else {
      tp = -Math.atan2(this.vy, Math.max(4, this.speed)) * 0.6;
      tr = this.roll * 0.98;
    }
    const k = 1 - Math.exp(-(this.grounded ? 18 : 4) * dt);
    this.pitch += (tp - this.pitch) * k;
    this.roll += (tr - this.roll) * k;
    body.rotation.set(this.pitch, 0, this.roll);
    for (const w of wheels) w.rotation.x += (this.forward * dt) / 0.42;
    for (const p of steer) p.rotation.y = -this.steerInput * 0.45;
    if (spinner) spinner.rotation.y += dt * 12;
  }
}
