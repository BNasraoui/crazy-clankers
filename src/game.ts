import * as THREE from 'three';
import { Car, MAX_SPEED } from './car';
import { readInput, padName, type Input } from './input';
import { makePerson, makeLabel, personFrom, type CarModel, type PersonModel } from './models';
import { Look, SKY, makeSky } from './look';
import { pickPassenger, type PassengerType } from './passengers';
import { QuipDirector } from './quips';
import { Traffic } from './traffic';
import { sfx, setEngine, unlockAudio } from './audio';
import { BLOCKS_SIDES, buildWorld, curb, heightAt, landmarks, N, type Curb, type Landmark } from './world';

const STEP = 1 / 120;
const START_TIME = 75;
const START = { x: 4, z: -30, yaw: Math.PI };
const WAITING_COUNT = 7;

interface Waiting {
  type: PassengerType;
  dest: Landmark;
  curb: Curb;
  person: PersonModel;
  marker: THREE.Group;
  phase: number;
}

interface Ride {
  type: PassengerType;
  dest: Landmark;
  base: number;
  total: number;
  left: number;
  startDist: number;
  tips: number;
  equity: number;
  fareMul: number;
  filmed: boolean;
  firedDone: boolean;
  firedT: number;
  rerouted: boolean;
  incidents: number;
  slowT: number;
  idleT: number;
  timeLowSaid: boolean;
  ejected?: PersonModel;
}

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector(sel) as T;
const flat = (a: THREE.Vector3, b: THREE.Vector3) => Math.hypot(a.x - b.x, a.z - b.z);
const blocks = (a: THREE.Vector3, b: THREE.Vector3) => Math.abs(a.x - b.x) + Math.abs(a.z - b.z);
const money = (n: number) => '$' + Math.round(n).toLocaleString('en-US');

export class Game {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(70, 1, 0.5, 1400);
  car: Car;
  traffic: Traffic;
  quips: QuipDirector;
  state: 'title' | 'play' | 'paused' | 'over' = 'title';

  time = START_TIME;
  cash = 0;
  equity = 0;
  promised = 0;
  fares = 0;
  combo = 0;
  safety = 100;
  clock = 0;
  waiting: Waiting[] = [];
  ride: Ride | null = null;

  private acc = 0;
  private lastIncident = -99;
  private lowWarned = false;
  private driftT = 0;
  private shake = 0;
  private camYaw = START.yaw;
  private sun: THREE.DirectionalLight;
  private look: Look;
  private sky = makeSky();
  private arrow: THREE.Group;
  private arrowMat: THREE.MeshLambertMaterial;
  private destMarker: THREE.Group | null = null;
  private quipTimer = 0;
  private rand = Math.random;

  constructor(public renderer: THREE.WebGLRenderer, cab: CarModel, private people: Partial<Record<string, THREE.Object3D>> = {}) {
    this.look = new Look(renderer);
    this.scene.background = new THREE.Color(SKY.horizon);
    this.scene.fog = new THREE.Fog(SKY.horizon, 170, 560);
    this.scene.add(this.sky);
    this.scene.add(new THREE.HemisphereLight(0xdfeaff, 0x8a7a66, 1.25));
    this.sun = new THREE.DirectionalLight(0xfff1dc, 2.6);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const sc = this.sun.shadow.camera;
    sc.left = sc.bottom = -70;
    sc.right = sc.top = 70;
    sc.near = 1;
    sc.far = 400;
    this.sun.shadow.bias = -0.0005;
    this.scene.add(this.sun, this.sun.target);

    buildWorld(this.scene);
    this.scene.add(cab.root);
    this.car = new Car(cab);
    this.traffic = new Traffic(this.scene, 46);

    // Flat, chunky arrow like the original's.
    this.arrowMat = new THREE.MeshLambertMaterial({ color: 0x7dff6a, emissive: 0x7dff6a, emissiveIntensity: 0.55 });
    const shape = new THREE.Shape();
    shape.moveTo(-0.45, -1.5);
    shape.lineTo(0.45, -1.5);
    shape.lineTo(0.45, 0.2);
    shape.lineTo(1.3, 0.2);
    shape.lineTo(0, 1.8);
    shape.lineTo(-1.3, 0.2);
    shape.lineTo(-0.45, 0.2);
    shape.closePath();
    const arrowGeo = new THREE.ExtrudeGeometry(shape, { depth: 0.35, bevelEnabled: true, bevelSize: 0.08, bevelThickness: 0.08, bevelSegments: 1 });
    arrowGeo.rotateX(Math.PI / 2);
    this.arrow = new THREE.Group();
    const body = new THREE.Mesh(arrowGeo, this.arrowMat);
    body.castShadow = true;
    const outline = new THREE.Mesh(arrowGeo, new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.BackSide }));
    outline.scale.setScalar(1.12);
    this.arrow.add(outline, body);
    this.scene.add(this.arrow);

    this.quips = new QuipDirector((who, color, text, seconds) => {
      const el = $('#quip');
      el.classList.remove('hidden');
      el.style.animation = 'none';
      void el.offsetWidth;
      el.style.animation = '';
      ($('#quip .who').textContent = who), ($('#quip .who').style.color = color);
      $('#quip .text').textContent = text;
      clearTimeout(this.quipTimer);
      this.quipTimer = window.setTimeout(() => el.classList.add('hidden'), seconds * 1000);
    });

    this.reset();
    this.showTitle();
  }

  resize(w: number, h: number) {
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.look.setSize(w, h);
  }

  private reset() {
    this.time = START_TIME;
    this.cash = this.equity = this.promised = this.fares = this.combo = 0;
    this.safety = 100;
    this.lowWarned = false;
    this.clock = 0;
    this.car.reset(START.x, START.z, START.yaw);
    this.camYaw = START.yaw;
    this.camera.position.set(START.x, this.car.pos.y + 4, START.z + 9);
    this.traffic.scatter();
    for (const w of this.waiting) this.scene.remove(w.person.root, w.marker);
    this.waiting = [];
    if (this.ride?.ejected) this.scene.remove(this.ride.ejected.root);
    this.ride = null;
    this.setDest(null);
    this.quips.reset();
    $('#quip').classList.add('hidden');
    $('#popups').replaceChildren();
    while (this.waiting.length < WAITING_COUNT) this.spawnWaiting();
  }

  // ---------- main loop ----------

  frame(dt: number) {
    const inp = readInput(dt);
    if (this.state === 'title') {
      if (inp.confirm) this.start();
      this.titleCamera(dt);
      this.traffic.update(dt, this.car);
      this.idleAnimations(dt);
    } else if (this.state === 'paused') {
      if (inp.confirm || inp.pause) this.setState('play');
      else if (inp.restart) this.start();
    } else if (this.state === 'over') {
      if (inp.confirm) this.start();
      this.idleAnimations(dt);
    } else {
      if (inp.pause) this.setState('paused');
      else this.simulate(dt, inp);
    }
    setEngine(this.car.forward, inp.throttle, this.state === 'play');
    this.car.sync(dt);
    this.traffic.sync(dt);
    if (inp.debug) this.look.togglePanel();
    this.sky.position.copy(this.camera.position);
    const rush = this.state === 'play' ? THREE.MathUtils.clamp((this.car.speed - 28) / 12, 0, 1) : 0;
    this.look.render(this.scene, this.camera, performance.now() / 1000, rush);
  }

  private start() {
    unlockAudio();
    this.reset();
    this.setState('play');
    this.popup('GO!', 'big');
  }

  private setState(s: Game['state']) {
    this.state = s;
    $('#hud').classList.toggle('hidden', s === 'title');
    const ov = $('#overlay');
    ov.className = '';
    if (s === 'play') ov.innerHTML = '';
    if (s === 'paused') {
      ov.className = 'dim';
      ov.innerHTML = `<h2>PAUSED</h2><div class="press">A / ENTER TO RESUME</div><div class="pad">Y / R to restart</div>`;
    }
  }

  private showTitle() {
    this.setState('title');
    $('#overlay').innerHTML = `
      <h1>CRAZY<span>CLANKERS</span></h1>
      <div class="tag">You are the robotaxi. Drive like it.</div>
      <div class="press">PRESS A / ENTER</div>
      <div class="controls">
        <b>Gas</b> RT / W &nbsp; <b>Brake / reverse</b> LT / S &nbsp; <b>Steer</b> stick / A D<br>
        <b>Drift</b> B or RB / Space (hold) &nbsp; <b>Pause</b> Start / Esc<br>
        Stop in a ring to pick up. Stop in the beam to drop off.<br>
        Jumps, near misses and drifts earn tips but cost your <b>DMV permit</b>.
      </div>
      <div class="pad" id="padstatus"></div>`;
  }

  simulate(dt: number, inp: Input) {
    this.clock += dt;
    this.quips.update(this.clock);

    this.acc = Math.min(this.acc + dt, 0.1);
    let impact = 0, landed = 0;
    while (this.acc >= STEP) {
      const ev = this.car.step(STEP, inp);
      impact = Math.max(impact, ev.impact);
      landed = Math.max(landed, ev.landed);
      this.acc -= STEP;
    }
    const tev = this.traffic.update(dt, this.car);
    impact = Math.max(impact, tev.impact);
    if (tev.honk) sfx.honk();

    if (impact > 5) this.onCrash(impact);
    if (landed > 0.45) {
      sfx.land(landed * 4);
      this.safetyHit(landed * 3);
      this.tip('jump', 1 + landed * 4, `AIR ${landed.toFixed(1)}s`);
    }
    for (let k = 0; k < tev.nearMisses; k++) {
      sfx.whoosh();
      this.safetyHit(2);
      this.tip('nearMiss', 2, 'NEAR MISS');
    }
    if (this.car.grounded && Math.abs(this.car.lateral) > 5 && this.car.speed > 12) this.driftT += dt;
    else {
      if (this.driftT > 0.8) this.tip('drift', this.driftT * 2, 'DRIFT');
      this.driftT = 0;
    }

    if (this.clock - this.lastIncident > 3) this.safety = Math.min(100, this.safety + 2 * dt);
    if (this.safety > 50) this.lowWarned = false;

    this.updateWaiting(dt);
    this.updateRide(dt);
    this.time -= dt;
    if (this.time <= 0) { this.time = 0; this.gameOver('TIME UP'); }
    this.driveCamera(dt);
    this.updateArrow();
    this.updateHud();
  }

  // ---------- scoring ----------

  private onCrash(impact: number) {
    sfx.crash(impact);
    this.shake = Math.min(1, impact / 20);
    this.combo = 0;
    this.safetyHit(THREE.MathUtils.clamp(impact * 0.9, 4, 22));
    if (impact > 12) this.popup('CRASH!', 'bad');
    const r = this.ride;
    if (r && r.firedT <= 0) {
      r.incidents++;
      if (!this.quips.say(r.type.id, 'crash')) this.quips.say('cab', 'crash');
    } else this.quips.say('cab', 'crash');
  }

  private safetyHit(n: number) {
    this.safety -= n;
    this.lastIncident = this.clock;
    if (this.safety < 30 && !this.lowWarned) {
      this.lowWarned = true;
      this.quips.say('cab', 'safetyLow', { force: true });
    }
    if (this.safety <= 0) { this.safety = 0; this.gameOver('PERMIT REVOKED'); }
  }

  private tip(kind: 'jump' | 'nearMiss' | 'drift', base: number, label: string) {
    const r = this.ride;
    if (!r || r.firedT > 0) return;
    const t = r.type;
    if (t.id === 'cmo' && kind === 'jump' && !r.filmed) {
      r.filmed = true;
      this.quips.say('cmo', 'jumpFirst', { force: true });
      this.popup('SHE MISSED IT', 'bad');
      return;
    }
    if (t.id === 'safety') {
      r.incidents++;
      this.quips.say('safety', kind, { force: true });
      this.popup('NO TIP. UNSAFE.', 'bad');
      return;
    }
    const amt = Math.max(1, Math.round(base * (kind === 'jump' ? t.jumpMul : 1) * t.tipMul * (1 + this.combo * 0.25)));
    this.combo++;
    if (t.id === 'founder') {
      r.equity += amt * 10;
      this.popup(`+${amt * 10} SHARES  ${label}`);
    } else {
      r.tips += amt;
      this.popup(`+${money(amt)}  ${label}`);
    }
    sfx.tip();
    if (!this.quips.say(t.id, kind) && kind === 'jump') this.quips.say('cab', 'jump');
  }

  // ---------- passengers ----------

  private spawnWaiting() {
    for (let tries = 0; tries < 50; tries++) {
      const bi = Math.floor(this.rand() * N), bj = Math.floor(this.rand() * N);
      const side = BLOCKS_SIDES[Math.floor(this.rand() * 4)];
      const c = curb(bi, bj, side, this.rand());
      if (flat(c.road, this.car.pos) < 60) continue;
      if (this.waiting.some((w) => flat(w.curb.road, c.road) < 45)) continue;
      if (landmarks.some((l) => flat(l.curb.road, c.road) < 12)) continue;
      const type = pickPassenger(this.rand);
      const far = landmarks.filter((l) => blocks(l.curb.road, c.road) > 160);
      const fav = far.filter((l) => type.prefers.includes(l.name));
      const pool = fav.length && this.rand() < 0.7 ? fav : far;
      if (!pool.length) continue;
      const dest = pool[Math.floor(this.rand() * pool.length)];
      const d = blocks(c.road, dest.curb.road);
      const color = d > 420 ? 0x47e05a : d > 270 ? 0xffd23a : 0xff5a3a;

      const person = this.makePassenger(type);
      person.root.position.copy(c.walk);
      person.root.rotation.y = c.facing;
      const marker = new THREE.Group();
      marker.add(groundRing(c.road.x, c.road.z, 5, 6.2, color, 0.85));
      marker.add(beam(c.road, 6, 14, color, 0.16));
      const label = makeLabel(type.label, { bg: type.vip ? '#3a2a00e0' : '#000000c0', fg: type.vip ? '#ffd23a' : '#ffffff', height: 1 });
      label.position.copy(c.walk).add(new THREE.Vector3(0, 3.4, 0));
      marker.add(label);
      this.scene.add(person.root, marker);
      this.waiting.push({ type, dest, curb: c, person, marker, phase: this.rand() * 6 });
      return;
    }
  }

  private makePassenger(type: PassengerType): PersonModel {
    const template = this.people[type.id];
    return template ? personFrom(template) : makePerson(type.person);
  }

  private idleAnimations(dt: number) {
    for (const w of this.waiting) {
      w.phase += dt;
      w.person.armR.rotation.z = 2.6 + Math.sin(w.phase * 8) * 0.4;
      w.person.root.position.y = w.curb.walk.y + Math.abs(Math.sin(w.phase * 4)) * 0.12;
    }
  }

  private updateWaiting(dt: number) {
    this.idleAnimations(dt);
    if (this.ride || this.car.speed > 4) return;
    const w = this.waiting.find((w) => flat(w.curb.road, this.car.pos) < 7);
    if (w) this.pickup(w);
  }

  private pickup(w: Waiting) {
    this.scene.remove(w.person.root, w.marker);
    this.waiting = this.waiting.filter((x) => x !== w);
    const d = blocks(w.curb.road, w.dest.curb.road);
    const total = (d / 19 + 6) * w.type.timeMul;
    this.ride = {
      type: w.type, dest: w.dest, base: 4 + d * 0.05, total, left: total, startDist: d,
      tips: 0, equity: 0, fareMul: w.type.fareMul, filmed: false, firedDone: false, firedT: 0,
      rerouted: false, incidents: 0, slowT: 0, idleT: 7, timeLowSaid: false,
    };
    this.setDest(w.dest);
    sfx.pickup();
    this.popup(w.type.label.replace('★ ', ''), 'big');
    this.quips.say(w.type.id, 'pickup', { force: true });
    if (this.rand() < 0.35) this.quips.say('cab', 'pickup', { delay: 3 });
    while (this.waiting.length < WAITING_COUNT) this.spawnWaiting();
  }

  private updateRide(dt: number) {
    const r = this.ride;
    if (!r) return;
    const id = r.type.id;

    if (r.firedT > 0) {
      r.firedT -= dt;
      if (r.ejected) r.ejected.armR.rotation.z = 2.6 + Math.sin(this.clock * 9) * 0.4;
      if (r.firedT <= 0) {
        if (r.ejected) this.scene.remove(r.ejected.root);
        r.ejected = undefined;
        r.fareMul *= 2;
        this.quips.say('sweater', 'back', { force: true });
        this.popup("HE'S BACK! FARE x2", 'big good');
        sfx.pickup();
      }
      return;
    }

    r.left -= dt;
    if (r.left <= 0) return this.walkout();

    const remaining = blocks(this.car.pos, r.dest.curb.road) / r.startDist;
    if (id === 'sweater' && !r.firedDone && remaining < 0.55) this.fireSweater(r);
    if (id === 'rocket' && !r.rerouted && remaining < 0.5) this.reroute(r);

    if (this.car.speed < 5 && flat(this.car.pos, r.dest.curb.road) > 25) {
      r.slowT += dt;
      if (r.slowT > 3) { this.quips.say(id, 'slow', { force: true }); r.slowT = -6; }
    } else r.slowT = Math.min(0, r.slowT + dt);

    if (r.left < 6 && !r.timeLowSaid) { r.timeLowSaid = true; this.quips.say(id, 'timeLow', { force: true }); }
    r.idleT -= dt;
    if (r.idleT <= 0) {
      r.idleT = 8 + this.rand() * 6;
      if (this.rand() < 0.8) this.quips.say(id, 'idle');
      else this.quips.say('cab', 'idle');
    }

    if (flat(this.car.pos, r.dest.curb.road) < 9 && this.car.speed < 5) this.dropoff(r);
  }

  private fireSweater(r: Ride) {
    r.firedDone = true;
    r.firedT = 5;
    const p = this.makePassenger(r.type);
    const f = this.car.fwd;
    p.root.position.set(this.car.pos.x - f.y * 3.5, 0, this.car.pos.z + f.x * 3.5);
    p.root.position.y = heightAt(p.root.position.x, p.root.position.z);
    p.root.rotation.y = this.car.yaw;
    this.scene.add(p.root);
    r.ejected = p;
    this.quips.say('sweater', 'fired', { force: true });
    this.popup('FIRED BY THE BOARD!', 'big bad');
    sfx.bad();
  }

  private reroute(r: Ride) {
    r.rerouted = true;
    const options = landmarks.filter((l) => l !== r.dest && blocks(l.curb.road, this.car.pos) > 180);
    if (!options.length) return;
    const dest = options[Math.floor(this.rand() * options.length)];
    const d = blocks(this.car.pos, dest.curb.road);
    r.dest = dest;
    r.startDist = d;
    r.base += d * 0.05;
    r.left += (d / 19) * r.type.timeMul;
    r.total = Math.max(r.total, r.left);
    this.setDest(dest);
    this.quips.say('rocket', 'reroute', { force: true, vars: { dest: dest.name } });
    this.popup('REROUTED!', 'big bad');
  }

  private walkout() {
    const r = this.ride!;
    this.quips.say(r.type.id, 'walkout', { force: true });
    if (this.rand() < 0.5) this.quips.say('cab', 'walkout', { delay: 2.6 });
    this.popup('PASSENGER BAILED', 'big bad');
    sfx.bad();
    this.combo = 0;
    this.ride = null;
    this.setDest(null);
  }

  private dropoff(r: Ride) {
    const ratio = r.left / r.total;
    const [rating, bonus, mul] = ratio > 0.45 ? ['SPEEDY!', 10, 1.3] as const : ratio > 0.15 ? ['NICE', 5, 1] as const : ['SLOW...', 2, 0.8] as const;
    const fare = Math.round(r.base * r.fareMul * mul);
    this.cash += fare;
    this.popup(`${rating}  +${bonus}s`, 'big');
    this.popup(`FARE ${money(fare)}`, 'good');
    if (r.type.id === 'rocket') {
      const promise = Math.max(1, r.tips) * 100000;
      this.promised += promise;
      this.popup(`TIP: ${money(promise)} (NEXT YEAR)`, 'bad');
    } else if (r.type.id === 'founder') {
      this.equity += r.equity;
      if (r.equity) this.popup(`${r.equity} SHARES VESTING`, 'good');
    } else if (r.type.id === 'safety') {
      const bonusTip = Math.max(0, 30 - r.incidents * 8);
      this.cash += bonusTip;
      this.popup(bonusTip ? `SAFETY BONUS +${money(bonusTip)}` : 'NO SAFETY BONUS', bonusTip ? 'good' : 'bad');
    } else {
      this.cash += r.tips;
      if (r.tips) this.popup(`TIPS +${money(r.tips)}`, 'good');
    }
    this.time += bonus;
    this.fares++;
    sfx.cash();
    this.quips.say(r.type.id, 'dropoff', { force: true });
    if (this.rand() < 0.3) this.quips.say('cab', 'dropoff', { delay: 3 });
    this.ride = null;
    this.setDest(null);
  }

  private setDest(dest: Landmark | null) {
    if (this.destMarker) this.scene.remove(this.destMarker);
    this.destMarker = null;
    if (!dest) return;
    const g = new THREE.Group();
    const c = dest.curb.road;
    g.add(groundRing(c.x, c.z, 7, 8.5, 0x46e0c4, 0.9));
    g.add(beam(c, 8, 60, 0x46e0c4, 0.22));
    const label = makeLabel(dest.name, { bg: '#0b3d36e0', fg: '#7dfff0', height: 3 });
    label.position.set(c.x, c.y + 16, c.z);
    g.add(label);
    this.destMarker = g;
    this.scene.add(g);
  }

  private gameOver(reason: string) {
    if (this.state !== 'play') return;
    this.state = 'over';
    let equityLine = '';
    if (this.equity > 0) {
      const exit = this.rand() < 0.15;
      if (exit) this.cash += this.equity;
      equityLine = exit
        ? `<div>Founder's startup got acquired! ${this.equity} shares → <b>${money(this.equity)}</b></div>`
        : `<div>Founder's startup folded. ${this.equity} shares → <b>$0</b></div>`;
    }
    const promiseLine = this.promised ? `<div>Tips promised for next year: <b>${money(this.promised)}</b> (received: $0)</div>` : '';
    const sub = reason === 'PERMIT REVOKED' ? 'The DMV has suspended your driverless permit.' : 'Your shift is over.';
    const ov = $('#overlay');
    ov.className = 'dim';
    ov.innerHTML = `
      <h2>${reason}</h2>
      <div class="stats">
        <div>${sub}</div>
        <div>Fares delivered: <b>${this.fares}</b></div>
        ${equityLine}${promiseLine}
        <div class="total">${money(this.cash)}</div>
      </div>
      <div class="press">A / ENTER TO DRIVE AGAIN</div>`;
    sfx.bad();
  }

  // ---------- camera & HUD ----------

  private driveCamera(dt: number) {
    const car = this.car;
    let diff = car.yaw - this.camYaw;
    diff = Math.atan2(Math.sin(diff), Math.cos(diff));
    this.camYaw += diff * (1 - Math.exp(-4 * dt));
    const speedT = Math.min(1, car.speed / MAX_SPEED);
    const back = 8.5 + speedT * 2, up = 3.6 + speedT * 0.6;
    const want = new THREE.Vector3(car.pos.x - Math.sin(this.camYaw) * back, car.pos.y + up, car.pos.z - Math.cos(this.camYaw) * back);
    want.y = Math.max(want.y, heightAt(want.x, want.z) + 1.5);
    this.camera.position.lerp(want, 1 - Math.exp(-10 * dt));
    const cam = this.camera.position;
    cam.y = Math.max(cam.y, heightAt(cam.x, cam.z) + 1.2);
    this.shake *= Math.exp(-6 * dt);
    if (this.shake > 0.01) this.camera.position.add(new THREE.Vector3((this.rand() - 0.5) * this.shake, (this.rand() - 0.5) * this.shake, 0));
    this.camera.lookAt(car.pos.x + Math.sin(this.camYaw) * 4, car.pos.y + 1.6, car.pos.z + Math.cos(this.camYaw) * 4);
    const fov = 68 + speedT * 14;
    if (Math.abs(this.camera.fov - fov) > 0.1) { this.camera.fov = fov; this.camera.updateProjectionMatrix(); }
    this.sun.position.set(car.pos.x + 60, car.pos.y + 110, car.pos.z + 35);
    this.sun.target.position.copy(car.pos);
  }

  private titleCamera(dt: number) {
    this.clock += dt;
    const a = this.clock * 0.25;
    const p = this.car.pos;
    this.camera.position.set(p.x + Math.sin(a) * 14, p.y + 5, p.z + Math.cos(a) * 14);
    this.camera.lookAt(p.x, p.y + 1.5, p.z);
    this.sun.position.set(p.x + 60, p.y + 110, p.z + 35);
    this.sun.target.position.copy(p);
    this.arrow.visible = false;
    const ps = document.getElementById('padstatus');
    if (ps) ps.textContent = padName ? `🎮 ${padName}` : 'Plug in or press a button on a controller to use it.';
  }

  private updateArrow() {
    let target: THREE.Vector3 | null = null;
    if (this.ride) {
      target = this.ride.dest.curb.road;
      const t = this.ride.left / this.ride.total;
      const c = t > 0.45 ? 0x7dff6a : t > 0.15 ? 0xffd23a : 0xff4a3a;
      this.arrowMat.color.set(c);
      this.arrowMat.emissive.set(c);
      this.arrow.scale.setScalar(1);
    } else {
      let best = Infinity;
      for (const w of this.waiting) {
        const d = flat(w.curb.road, this.car.pos);
        if (d < best) { best = d; target = w.curb.road; }
      }
      this.arrowMat.color.set(0xffffff);
      this.arrowMat.emissive.set(0x888888);
      this.arrow.scale.setScalar(0.6);
    }
    this.arrow.visible = !!target && this.state === 'play';
    if (!target) return;
    const p = this.car.pos;
    this.arrow.position.set(p.x, p.y + 3.1 + Math.sin(this.clock * 4) * 0.1, p.z);
    this.arrow.rotation.set(0, Math.atan2(target.x - p.x, target.z - p.z), 0);
  }

  private updateHud() {
    const t = $('#time');
    t.textContent = String(Math.ceil(this.time));
    t.classList.toggle('low', this.time < 10);
    $('#money').textContent = money(this.cash);
    $('#permit .fill').style.width = `${this.safety}%`;
    $('#permit').classList.toggle('low', this.safety < 30);
    $('#speed').innerHTML = `${Math.round(this.car.speed * 2.237)} <small>MPH</small>`;
    $('#combo').textContent = this.combo > 1 ? `COMBO x${this.combo}` : '';
    const fare = $('#fare');
    const r = this.ride;
    fare.classList.toggle('hidden', !r);
    if (r) {
      $('#fare .who').textContent = r.type.label;
      $('#fare .dest').textContent = r.firedT > 0 ? 'Passenger temporarily fired…' : `→ ${r.dest.name}`;
      $('#fare .clock').textContent = r.firedT > 0 ? `${Math.ceil(r.firedT)}` : `${Math.ceil(r.left)}`;
    }
  }

  popup(text: string, cls = '') {
    const el = document.createElement('div');
    el.className = `popup ${cls}`;
    el.textContent = text;
    $('#popups').appendChild(el);
    setTimeout(() => el.remove(), 1600);
  }
}

// A flat ring that hugs the hilly ground.
function groundRing(cx: number, cz: number, r0: number, r1: number, color: number, opacity: number) {
  const seg = 48;
  const pos: number[] = [];
  const idx: number[] = [];
  for (let k = 0; k <= seg; k++) {
    const a = (k / seg) * Math.PI * 2;
    for (const r of [r0, r1]) {
      const x = cx + Math.cos(a) * r, z = cz + Math.sin(a) * r;
      pos.push(x, heightAt(x, z) + 0.15, z);
    }
    if (k < seg) {
      const i = k * 2;
      idx.push(i, i + 1, i + 2, i + 1, i + 3, i + 2);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setIndex(idx);
  return new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false }));
}

function beam(at: THREE.Vector3, r: number, h: number, color: number, opacity: number) {
  const m = new THREE.Mesh(
    new THREE.CylinderGeometry(r, r, h, 24, 1, true),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }),
  );
  m.position.set(at.x, at.y + h / 2, at.z);
  return m;
}
