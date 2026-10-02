import * as THREE from 'three';
import { Radio } from './radio';
import { Car, MAX_SPEED, handlingOf } from './car';
import { readInput, padName, padDebug, type Input } from './input';
import { CABS, EXTRA_CARS, makeCar, makePerson, makeLabel, personFrom, type PersonModel } from './models';
import { Look, SKY, makeSky } from './look';
import { paintSky, updateSky } from './sky';
import { CHARACTER_LAYER, makeCharacter, sunDir } from './anime';
import { pickPassenger, roleOf, type PassengerType } from './passengers';
import { QuipDirector, SPEAKERS, askLine, type QuipEvent } from './quips';
import { allZhNames, fullName, nameCount, shortName } from './names';
import { lang, onLang, place, setLang, t } from './i18n';
import { Traffic } from './traffic';
import { sfx, setEngine, unlockAudio } from './audio';
import { bump, crunch, splash as splashLayers } from './sfx';
import { Tyres } from './skids';
import { Voices } from './voices';
import { BLOCKS_SIDES, CELL, HALF, WATER, buildWorld, curb, landmarks, N, waterAt, type Curb, type Landmark } from './world';
import { buildFeatures, groundAt } from './features';
import { Moments } from './manga';
import { Want, WANTS, type Feed, type WantId } from './wants';
import { Geysers, Particles, Props, type PropKind } from './props';
import type { Pedestrians } from './pedestrians';
import { SpritePerson, type SpriteSet } from './spritepeople';
import { Trees } from './trees';
import { CableCars } from './cablecar';
import { BAY, Rank, snapshotCabs } from './rank';
import { btn, burst, howToHTML, pickerHTML, tapButton, titleHTML } from './menus';
import { key } from './prompts';
import { buzz } from './touch';

const STEP = 1 / 120;
const START_TIME = 90; // with SURGE below, aimed at a 3-5 minute shift
const START = BAY; // every shift starts by pulling out of the robotaxi rank
const WAITING_COUNT = 40;
const CARPOOL_MAX = 3; // the Zoombox carries up to this many fares at once
// Surge pricing is the difficulty: every 5 deliveries it climbs a level, up to 4.
// [time added at pickup (share of the fare's limit), fare limit, want targets, fare pay]
const SURGE: [number, number, number, number][] = [
  [0.5, 1, 1, 1],
  [0.42, 0.92, 1.1, 1.25],
  [0.35, 0.85, 1.2, 1.5],
  [0.28, 0.78, 1.3, 1.75],
  [0.22, 0.72, 1.4, 2],
];

interface Waiting {
  type: PassengerType;
  dest: Landmark;
  curb: Curb;
  person: PersonModel;
  marker: THREE.Group;
  label: THREE.Object3D;
  want: WantId; // chosen as they arrive at the curb, so the Wayfarer can see it
  name: number; // their parody name, as a place in their type's pool (names.ts)
  phase: number;
}

interface Ride {
  type: PassengerType;
  name: number;
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
  want: Want; // what this passenger wants from the ride, rated 1-5 stars
  marker?: THREE.Group; // a carpool rider's own destination beam (the lead's is destMarker)
  moodT: number; // countdown to the next word on how the want is going
}

// "Brayden Seedround · Tech Bro", with a star for the VIPs.
const nameTag = (type: PassengerType, name: number) => `${type.vip ? '★ ' : ''}${fullName(type.id, name)} · ${roleOf(type)}`;

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector(sel) as T;
const flat = (a: THREE.Vector3, b: THREE.Vector3) => Math.hypot(a.x - b.x, a.z - b.z);
const blocks = (a: THREE.Vector3, b: THREE.Vector3) => Math.abs(a.x - b.x) + Math.abs(a.z - b.z);
const money = (n: number) => '$' + Math.round(n).toLocaleString('en-US');
const secs = (n: number) => t('unit.s', { n: n.toFixed(1) });

export class Game {
  private radio = new Radio();
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(70, 1, 0.5, 1400);
  car: Car;
  traffic: Traffic;
  quips: QuipDirector;
  state: 'title' | 'picker' | 'play' | 'paused' | 'over' = 'title';

  time = START_TIME;
  private shiftTime = 0; // how long this shift has lasted
  cash = 0;
  equity = 0;
  promised = 0;
  private starsGiven: number[] = []; // each passenger's rating this shift
  private pool: Ride[] = []; // the Zoombox's other riders; this.ride is the one whose stop is nearest
  private get carpool() { return CABS[this.cabIndex].id === 'zoox'; }
  private get aboard() { return (this.ride ? 1 : 0) + this.pool.length; }
  private get surge() { return Math.min(SURGE.length - 1, Math.floor(this.fares / 5)); }
  private stampTimer = 0;
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
  private moments = new Moments();
  private rising = false; // the cab was still climbing last frame
  private apexDone = true; // this jump has had its slow motion
  private camYaw = START.yaw;
  private sun: THREE.DirectionalLight;
  private look: Look;
  private props: Props;
  private particles: Particles;
  private geysers: Geysers;
  private trees = new Trees();
  private tyres = new Tyres(this.scene);
  private voices = new Voices(this.scene);
  private cableCars!: CableCars;
  peds: Pedestrians | null = null;
  paxSprites: Record<string, SpriteSet> = {};
  private maxAir = 0;
  private underwaterView = false;
  private sky = makeSky();
  private arrow: THREE.Group;
  private arrowMat: THREE.MeshLambertMaterial;
  private destMarker: THREE.Group | null = null;
  private quipTimer = 0;
  private rand = Math.random;

  private cabIndex = (() => {
    try { return Math.max(0, CABS.findIndex((c) => c.id === localStorage.getItem('clankers.cab'))); } catch { return 0; }
  })();
  private rank!: Rank;
  private thumbs: Record<string, string> = {};
  private howTo = false;

  constructor(public renderer: THREE.WebGLRenderer, private people: Partial<Record<string, THREE.Object3D>> = {}) {
    const cab = makeCar(CABS[this.cabIndex].id);
    this.look = new Look(renderer);
    this.look.onChange = () => this.refreshPassengers();
    this.scene.background = new THREE.Color(SKY.horizon);
    this.scene.fog = new THREE.Fog(SKY.horizon, 320, 900); // crisp air, haze only far away
    paintSky(this.sky);
    this.scene.add(this.sky);
    const sky = new THREE.HemisphereLight(0xd8e8ff, 0x8f7f9a, 1.2);
    sky.layers.enable(CHARACTER_LAYER);
    this.scene.add(sky);
    this.sun = new THREE.DirectionalLight(0xffecd0, 2.9);
    this.sun.layers.enable(CHARACTER_LAYER);
    this.sun.shadow.camera.layers.enable(CHARACTER_LAYER);
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
    buildFeatures(this.scene);
    this.props = new Props(this.scene);
    this.particles = new Particles(this.scene);
    this.geysers = new Geysers(this.scene, this.particles);
    this.scene.add(cab.root);
    this.car = new Car(cab);
    this.car.h = handlingOf(CABS[this.cabIndex].id);
    this.traffic = new Traffic(this.scene, 46, this.rivals());
    this.traffic.rammer = CABS[this.cabIndex].id === 'apollo'; // the Artemis Go bulldozes traffic
    this.rank = new Rank(this.scene, this.cabIndex);
    this.cableCars = new CableCars(this.scene);
    this.thumbs = snapshotCabs(renderer);

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
    arrowGeo.translate(0, 0, 1.5); // pivot at the tail
    this.arrow = new THREE.Group();
    const body = new THREE.Mesh(arrowGeo, this.arrowMat);
    body.castShadow = true;
    const outline = new THREE.Mesh(arrowGeo, new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.BackSide }));
    outline.scale.setScalar(1.12);
    this.arrow.add(outline, body);
    this.scene.add(this.arrow);

    this.quips = new QuipDirector((speaker, color, text, seconds, who) => {
      const el = $('#quip');
      const face = $<HTMLImageElement>('#quip .face');
      face.hidden = speaker === 'cab';
      if (speaker !== 'cab') face.src = `/portraits/${speaker}.avif`;
      el.classList.remove('hidden');
      el.style.animation = 'none';
      void el.offsetWidth;
      el.style.animation = '';
      ($('#quip .who').textContent = speaker === 'cab' ? t('speaker.cab') : who ?? this.tagFor(speaker)), ($('#quip .who').style.color = color);
      $('#quip .text').textContent = text;
      clearTimeout(this.quipTimer);
      this.quipTimer = window.setTimeout(() => el.classList.add('hidden'), seconds * 1000);
    });

    this.reset();
    this.showTitle();
    onLang(() => this.relanguage());
    this.labelFont();
    // The EN / 中文 switch on the title screen: click it, or press L.
    const flip = () => setLang(lang() === 'zh' ? 'en' : 'zh');
    addEventListener('click', (e) => { if ((e.target as Element).closest?.('[data-lang]')) flip(); });
    addEventListener('keydown', (e) => { if (e.code === 'KeyL' && this.state === 'title' && !this.howTo) flip(); });
  }

  // The language changed (title screen switch): redraw whatever is showing.
  private relanguage() {
    if (this.state === 'title') this.showTitle();
    else if (this.state === 'picker') this.renderCabPicker();
    else if (this.state === 'paused') this.setState('paused');
    this.relabels();
    this.labelFont();
  }

  // The 3D tags (fares, drop-offs) are drawn once onto canvases.
  private relabels() {
    this.relabelFares();
    this.setDest(this.ride?.dest ?? null);
    for (const p of this.pool) if (p.marker) { this.scene.remove(p.marker); p.marker = this.poolMarker(p.dest); }
  }

  // A canvas can't wait for a web font, so in Chinese fetch the glyphs the tags use, then redraw them.
  private labelFont() {
    if (lang() !== 'zh' || !document.fonts) return;
    const text = [...this.waiting.map((w) => this.labelText(w.type, w.name, w.want, w.curb, w.dest)), ...landmarks.map((l) => place(l.name)), allZhNames()].join('');
    document.fonts.load('700 56px "Noto Sans SC"', text).then(() => this.relabels(), () => {});
  }

  // A speaker's name tag: the rider of that type aboard (the lead first), else just the role.
  private tagFor(speaker: string) {
    const r = [this.ride, ...this.pool].find((x) => x?.type.id === speaker);
    return r ? nameTag(r.type, r.name) : t(`role.${speaker}` as 'role.techbro');
  }

  resize(w: number, h: number) {
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.look.setSize(w, h);
  }

  private reset() {
    this.time = START_TIME;
    this.shiftTime = 0;
    this.cash = this.equity = this.promised = this.fares = this.combo = 0;
    this.starsGiven = [];
    this.safety = 100;
    this.lowWarned = false;
    this.clock = 0;
    const st = this.rank?.start ?? START;
    this.car.reset(st.x, st.z, st.yaw);
    this.camYaw = st.yaw;
    this.camera.position.set(st.x - Math.sin(st.yaw) * 9, this.car.pos.y + 4, st.z - Math.cos(st.yaw) * 9);
    this.traffic.scatter();
    this.props.reset();
    this.geysers.reset();
    this.trees.reset();
    this.peds?.reset();
    this.tyres.reset();
    this.maxAir = 0;
    for (const w of this.waiting) this.scene.remove(w.person.root, w.marker);
    this.waiting = [];
    if (this.ride?.ejected) this.scene.remove(this.ride.ejected.root);
    this.ride = null;
    for (const p of this.pool) if (p.marker) this.scene.remove(p.marker);
    this.pool = [];
    this.setDest(null);
    this.quips.reset();
    $('#quip').classList.add('hidden');
    $('#popups').replaceChildren();
    while (this.waiting.length < WAITING_COUNT) this.spawnWaiting();
  }

  // ---------- main loop ----------

  frame(dt: number) {
    const inp = readInput(dt);
    if (this.radio.frame(inp, this.state)) { setEngine(0, 0, false); return; }
    if (this.state === 'title' || this.state === 'picker') {
      this.menuFrame(dt, inp);
      this.traffic.update(dt, this.car);
      this.cableCars.update(dt, this.car);
      this.peds?.update(dt, this.car, this.camera);
      this.idleAnimations(dt);
    } else if (this.state === 'paused') {
      if (inp.confirm || inp.pause) this.setState('play');
      else if (inp.restart) this.start();
      else if (inp.back) this.showTitle(); // Backspace or B: back to the title screen
    } else if (this.state === 'over') {
      if (inp.confirm) this.start();
      else if (inp.back) this.showPicker();
      this.idleAnimations(dt);
    } else {
      if (inp.pause) this.setState('paused');
      else this.simulate(dt * this.moments.timeScale(dt) * (this.radio.wheelOpen ? 0.3 : 1), inp);
    }
    setEngine(this.car.forward, inp.throttle, this.state === 'play');
    this.car.sync(dt);
    this.tyres.update(dt, this.car, inp, this.state === 'play');
    this.voices.update(dt, this.camera, this.peds);
    this.traffic.sync(dt);
    if (inp.debug) this.look.togglePanel();
    this.look.setPadDebug(padDebug);
    this.sky.position.copy(this.camera.position);
    updateSky(performance.now() / 1000, this.camera.position.y);
    const under = this.camera.position.y < WATER;
    if (under !== this.underwaterView) {
      this.underwaterView = under;
      const fog = this.scene.fog as THREE.Fog;
      fog.color.set(under ? 0x1d6a86 : SKY.horizon);
      fog.near = under ? 4 : 320;
      fog.far = under ? 110 : 900;
      (this.scene.background as THREE.Color).set(under ? 0x1d6a86 : SKY.horizon);
      this.sky.visible = !under;
    }
    const rush = this.state === 'play' ? THREE.MathUtils.clamp((this.car.speed - 28) / 12, 0, 1) : 0;
    this.look.render(this.scene, this.camera, performance.now() / 1000, rush);
  }

  private start() {
    unlockAudio();
    burst();
    this.reset();
    this.rank.setCarsVisible(false);
    this.car.model.root.visible = true;
    this.setState('play');
    this.popup(t('pop.go'), 'big');
  }

  // Title screen and cab picker, staged at the taxi rank.
  private menuFrame(dt: number, inp: Input) {
    this.clock += dt;
    this.rank.update(dt, this.state === 'picker' ? inp.lookX : 0);
    this.rank.frame(this.camera, this.state === 'picker' ? 'picker' : 'wide', dt);
    const p = this.rank.bayY;
    this.sun.position.set(BAY.x + 60, p + 110, BAY.z + 35);
    this.sun.target.position.set(BAY.x, p, BAY.z);
    sunDir.value.copy(this.sun.position).sub(this.sun.target.position).normalize();
    this.arrow.visible = false;
    if (this.state === 'title') {
      if (this.howTo) {
        if (inp.confirm || inp.back || inp.alt) this.toggleHowTo();
        return;
      }
      if (inp.confirm) { unlockAudio(); this.showPicker(); }
      else if (inp.alt) this.toggleHowTo();
      else if (inp.back) this.look.togglePanel();
    } else {
      const move = inp.navY || inp.navX;
      if (move || (inp.select >= 0 && inp.select !== this.cabIndex)) {
        this.chooseCab(move ? this.cabIndex + move : inp.select);
        sfx.tip();
      }
      if (inp.confirm) this.start();
      else if (inp.back) this.showTitle();
    }
  }

  private toggleHowTo() {
    this.howTo = !this.howTo;
    document.querySelector('.howto')?.remove();
    if (this.howTo) document.getElementById('overlay')!.insertAdjacentHTML('beforeend', howToHTML());
  }

  private showPicker() {
    this.setState('picker');
    this.rank.setCarsVisible(true);
    this.car.model.root.visible = false;
    this.renderCabPicker();
  }

  private setState(s: Game['state']) {
    this.state = s;
    document.body.dataset.state = s;
    $('#hud').classList.toggle('hidden', s === 'title' || s === 'picker');
    const ov = $('#overlay');
    ov.className = '';
    if (s === 'play') ov.innerHTML = '';
    if (s === 'paused') {
      ov.className = 'dim';
      ov.innerHTML = `<h2>${t('pause.title')}</h2><div class="press pad-only">${btn('confirm', t('pause.resume'))}</div><div class="pad pad-only">${btn('restart', t('pause.restart'))}${btn('menu', t('pause.menu'))}</div>
        <div class="tap-row touch-only">${tapButton('confirm', t('pause.resume'), 'go')}${tapButton('restart', t('pause.restart'))}${tapButton('back', t('pause.menu'))}</div>
        <button class="radio-menu-button" data-radio-open>${key('radio')} ${t('menu.radio')}</button>`;
    }
  }

  private rivals() {
    return [...CABS.map((c) => c.id).filter((id) => id !== CABS[this.cabIndex].id), ...EXTRA_CARS];
  }

  private chooseCab(i: number) {
    this.cabIndex = (i + CABS.length) % CABS.length;
    try { localStorage.setItem('clankers.cab', CABS[this.cabIndex].id); } catch { /* storage unavailable */ }
    this.scene.remove(this.car.model.root);
    this.car.model = makeCar(CABS[this.cabIndex].id);
    this.car.h = handlingOf(CABS[this.cabIndex].id);
    this.relabelFares();
    this.traffic.rammer = CABS[this.cabIndex].id === 'apollo';
    this.scene.add(this.car.model.root);
    this.traffic.setRivals(this.scene, this.rivals());
    this.car.model.root.visible = this.state === 'play';
    this.rank.select(this.cabIndex);
    this.renderCabPicker();
  }

  private renderCabPicker() {
    if (this.state !== 'picker') return;
    $('#overlay').innerHTML = pickerHTML(this.cabIndex, this.thumbs);
  }

  private showTitle() {
    this.setState('title');
    this.howTo = false;
    this.rank?.setCarsVisible(true);
    this.car.model.root.visible = false;
    $('#overlay').innerHTML = titleHTML(padName);
  }

  simulate(dt: number, inp: Input) {
    this.clock += dt;
    this.quips.update(this.clock);

    this.acc = Math.min(this.acc + dt, 0.1);
    let impact = 0, landed = 0, hop = false, launch = -1, armed = false, splash = false;
    let first = true;
    while (this.acc >= STEP) {
      // Edge-triggered buttons only count on the first physics step of the frame.
      const ev = this.car.step(STEP, first ? inp : { ...inp, hop: false });
      first = false;
      impact = Math.max(impact, ev.impact);
      landed = Math.max(landed, ev.landed);
      hop ||= ev.hop;
      if (ev.launch >= 0) launch = ev.launch;
      armed ||= ev.armed;
      splash ||= ev.splash;
      this.acc -= STEP;
    }
    if (hop) { sfx.hop(); this.ride?.want.feed('hop'); for (const p of this.pool) p.want.feed('hop'); }
    if (armed) {
      sfx.armed();
      this.popup(t('pop.launchMode'));
    }
    if (launch >= 0) {
      sfx.dash();
      this.popup(launch > 0.95 ? t('pop.fullLaunch') : t('pop.launch'), launch > 0.95 ? 'big' : '');
      this.quips.say('cab', 'dash');
    }
    if (splash) {
      sfx.splash();
      splashLayers();
      this.particles.emit(this.car.pos.clone().setY(waterAt(this.car.pos.x, this.car.pos.z)), 50, 0xe6f6ff, 9, 12, 0.45);
      this.popup(t('pop.seabed'), 'big');
      this.quips.say('cab', 'underwater', { force: true });
    }
    for (const hit of this.props.update(dt, this.car)) this.onSmash(hit.kind, hit.pos);
    if (this.geysers.update(dt, this.car)) {
      this.car.launch(17);
      sfx.geyser();
      this.popup(t('pop.geyser'), 'big');
    }
    for (const hit of this.trees.update(dt, this.car.pos, this.car.vel)) {
      this.shake = Math.max(this.shake, 0.4);
      if (hit.kind === 'tree') {
        sfx.timber();
        this.particles.emit(hit.at.clone().setY(hit.at.y + 3 * hit.size), 22, 0x4f8f45, 6, 6, 0.4);
        this.particles.emit(hit.at.clone().setY(hit.at.y + 0.5), 8, 0x6b4a2f, 4, 5, 0.25);
        this.popup(t('pop.timber'), 'big');
        if (Math.random() < 0.4) this.quips.say('cab', 'timber');
      } else {
        sfx.smash();
        this.particles.emit(hit.at.clone().setY(hit.at.y + 1), 12, 0x2f4f45, 5, 6, 0.25);
        this.popup(hit.kind === 'lamp' ? t('pop.lightsOut') : t('pop.poleDown'));
      }
      this.tip('smash', 1, hit.kind === 'tree' ? t('tip.timber') : t('tip.smash'));
    }
    this.particles.update(dt);
    if (this.peds) {
      this.peds.size = this.look.settings.people;
      const pev = this.peds.update(dt, this.car, this.camera);
      if (pev.dives.length) {
        sfx.yelp();
        if (Math.random() < 0.3) this.quips.say('cab', 'pedDive');
      }
      for (let k = 0; k < pev.closeCalls; k++) this.tip('nearMiss', 1, t('tip.closeCall'));
    }
    const tev = this.traffic.update(dt, this.car, this.peds?.inRoad() ?? []);
    impact = Math.max(impact, this.cableCars.update(dt, this.car));
    impact = Math.max(impact, tev.impact);
    if (tev.honk) sfx.honk();
    // The Artemis Go bulldozes traffic: the car flies, the cab barely notices.
    for (const at of tev.rams) {
      crunch(14);
      this.shake = Math.max(this.shake, 0.35);
      this.particles.emit(at, 18, 0x2a2730, 7, 6, 0.3);
      this.moments.panel('crash', 0.5, false); // the art without the freeze: rams are frequent
      this.popup(t('pop.bulldozed'), 'big');
      this.tip('smash', 1, t('tip.ram'));
      if (this.ride && this.rand() < 0.5) this.say(this.ride, 'ram');
      else this.quips.say('cab', 'ram', { force: this.rand() < 0.3 });
    }

    if (impact > 5) this.onCrash(impact);
    else if (impact > 1.5) bump(impact);
    // Slow motion at the top of a big jump.
    if (this.car.grounded) this.apexDone = false;
    else {
      const height = this.car.pos.y - groundAt(this.car.pos.x, this.car.pos.z);
      if (this.rising && this.car.vy <= 0 && height > 7 && !this.apexDone) this.moments.slowMotion(0.9);
      if (this.car.vy <= 0) this.apexDone = true;
    }
    this.rising = !this.car.grounded && this.car.vy > 0;
    if (landed > 0.6) {
      // Dust kicked up by the landing.
      this.particles.emit(this.car.pos.clone().setY(this.car.pos.y + 0.3), Math.round(10 + landed * 10), 0xd9cfbd, 4 + landed * 3, 1.5, 0.45);
    }
    // A plain hop is about 0.7 s of air, so it takes a real jump to earn a tip.
    if (landed > 0.85) {
      sfx.land(landed * 4);
      this.maxAir = Math.max(this.maxAir, landed);
      if (landed > 1.8) {
        this.moments.panel('land', landed / 3);
        this.popup(t('pop.crazyAir'), 'big');
        if (!this.ride) this.quips.say('cab', 'bigAir', { force: true });
      }
      this.tip('jump', landed, t('tip.air', { s: secs(landed) }));
    } else if (landed > 0.3) sfx.land(landed * 2);
    for (let k = 0; k < tev.nearMisses; k++) {
      sfx.whoosh();
      this.tip('nearMiss', 1, t('tip.nearMiss'));
    }
    if (this.car.grounded && Math.abs(this.car.lateral) > 5 && this.car.speed > 12) this.driftT += dt;
    else {
      if (this.driftT > 0.8) this.tip('drift', this.driftT, t('tip.drift', { s: secs(this.driftT) }));
      this.driftT = 0;
    }

    if (this.clock - this.lastIncident > 3) this.safety = Math.min(100, this.safety + 2 * dt);
    if (this.safety > 50) this.lowWarned = false;

    this.updateWaiting(dt);
    this.updateRide(dt);
    this.time -= dt;
    this.shiftTime += dt;
    if (this.time <= 0) { this.time = 0; this.gameOver('time'); }
    this.driveCamera(dt);
    this.updateArrow();
    this.updateHud();
  }

  // ---------- scoring ----------

  private onCrash(impact: number) {
    sfx.crash(impact);
    crunch(impact);
    buzz(impact);
    this.shake = Math.min(1, impact / 20);
    this.combo = 0;
    this.safetyHit(THREE.MathUtils.clamp(impact * 0.9, 4, 22));
    if (impact > 16) this.moments.panel('crash', impact / 30);
    if (impact > 12) this.popup(t('pop.crash'), 'bad');
    const r = this.ride;
    if (r && r.firedT <= 0) {
      r.incidents++;
      r.want.feed('crash', impact);
      for (const p of this.pool) p.want.feed('crash', impact);
      if (!this.say(r, 'crash')) this.quips.say('cab', 'crash');
    } else this.quips.say('cab', 'crash');
  }

  private onSmash(kind: PropKind, at: THREE.Vector3) {
    const colors: Record<PropKind, number> = { hydrant: 0xd23b2e, cone: 0xf26a1b, newsbox: 0x2d6fd2, trash: 0x3b7d4a, table: 0xf4f1e8, fruit: 0xf39c2b, sawhorse: 0xf4f1e8, placard: 0xf4f1e8 };
    sfx.smash();
    this.particles.emit(at.clone().setY(at.y + 0.6), 10, colors[kind], 5, 7, 0.22);
    if (kind === 'hydrant') {
      this.geysers.spawn(at);
      this.quips.say('cab', 'geyser', { force: true });
    } else this.quips.say('cab', 'smash');
    this.tip('smash', 1, kind === 'cone' ? t('tip.cone') : t('tip.smash'));
  }

  // The rating is the safety meter shown Uber-style: 5.00 at full, deactivated at 4.00.
  get rating() { return 4 + this.safety / 100; }

  private safetyHit(n: number) {
    this.safety -= n;
    if (n >= 3) {
      const el = $('#rating');
      el.classList.remove('hit');
      void el.offsetWidth;
      el.classList.add('hit');
    }
    this.lastIncident = this.clock;
    if (this.safety < 30 && !this.lowWarned) {
      this.lowWarned = true;
      this.quips.say('cab', 'safetyLow', { force: true });
    }
    if (this.safety <= 0) { this.safety = 0; this.gameOver('deactivated'); }
  }

  // A stunt during a ride counts towards the passenger's want, if they care about it.
  private tip(kind: Feed, amount: number, label: string) {
    const r = this.ride;
    if (!r || r.firedT > 0) return;
    if (r.type.id === 'cmo' && kind === 'jump' && !r.filmed) {
      r.filmed = true;
      this.say(r, 'jumpFirst', { force: true });
      this.popup(t('pop.missedIt'), 'bad');
      return;
    }
    for (const p of this.pool) p.want.feed(kind, amount); // carpool riders count it too
    const before = r.want.stars;
    if (!r.want.feed(kind, amount)) return; // they don't care
    if (r.want.id === 'smooth') {
      r.incidents++;
      if (!this.say(r, 'bad.smooth', { force: this.rand() < 0.5 })) this.say(r, kind === 'smash' ? 'smash' : kind === 'drift' ? 'drift' : kind === 'nearMiss' ? 'nearMiss' : 'jump', { force: true });
      this.popup(`-1★  ${label}`, 'bad');
      sfx.bad();
      return;
    }
    this.combo++;
    const after = r.want.stars;
    this.popup(after > before ? `${'★'.repeat(after)}  ${label}` : `+ ${label}`, after > before ? 'good' : '');
    if (after > before) sfx.tip();
    if (after > before && this.rand() < 0.45 && this.say(r, `good.${r.want.id}`)) return;
    if (!this.say(r, kind as 'jump') && kind === 'jump') this.quips.say('cab', 'jump');
  }

  // The want panel under the timer pops when a new passenger says what they want.
  private showWantCard(_r: Ride) {
    const el = $('#want');
    el.classList.remove('new'); void el.offsetWidth; el.classList.add('new');
  }

  // The passenger's rating at the drop-off: a big star stamp.
  private stamp(stars: number, line: string) {
    const el = $('#stamp');
    el.innerHTML = `<div class="stars">${'★'.repeat(stars)}<s>${'★'.repeat(5 - stars)}</s></div><div class="line">${line}</div>`;
    el.classList.remove('show'); void el.offsetWidth; el.classList.add('show');
    clearTimeout(this.stampTimer);
    this.stampTimer = window.setTimeout(() => el.classList.remove('show'), 2900);
  }

  // ---------- passengers ----------

  private spawnWaiting() {
    // Keep about half the fares within a short drive of the cab, so one is usually in view.
    const near = this.waiting.filter((w) => flat(w.curb.road, this.car.pos) < 220).length < WAITING_COUNT * 0.6;
    for (let tries = 0; tries < 50; tries++) {
      let bi = Math.floor(this.rand() * N), bj = Math.floor(this.rand() * N);
      if (near) {
        const ci = Math.floor((this.car.pos.x + HALF) / CELL), cj = Math.floor((this.car.pos.z + HALF) / CELL);
        bi = Math.min(N - 1, Math.max(0, ci + Math.floor(this.rand() * 7) - 3));
        bj = Math.min(N - 1, Math.max(0, cj + Math.floor(this.rand() * 7) - 3));
      }
      const side = BLOCKS_SIDES[Math.floor(this.rand() * 4)];
      const c = curb(bi, bj, side, this.rand());
      if (flat(c.road, this.car.pos) < 40) continue;
      if (this.waiting.some((w) => flat(w.curb.road, c.road) < 18)) continue;
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
      const want = type.wants[Math.floor(this.rand() * type.wants.length)];
      const name = Math.floor(this.rand() * nameCount(type.id));
      const label = this.fareLabel(type, name, want, c, dest);
      marker.add(label);
      this.scene.add(person.root, marker);
      this.waiting.push({ type, dest, curb: c, person, marker, label, want, name, phase: this.rand() * 6 });
      return;
    }
  }

  private makePassenger(type: PassengerType): PersonModel {
    const sprite = this.paxSprites[type.id];
    if (sprite && this.look.settings.paxSprites) return new SpritePerson(sprite);
    const template = this.people[type.id];
    if (template) return personFrom(template);
    const person = makePerson(type.person);
    makeCharacter(person.root);
    return person;
  }

  private idleAnimations(dt: number) {
    for (const w of this.waiting) {
      w.phase += dt;
      const p = w.person;
      p.armR.rotation.z = p.raise + Math.sin(w.phase * 8) * p.raise * 0.15;
      w.person.root.position.y = w.curb.walk.y + Math.abs(Math.sin(w.phase * 4)) * 0.12;
      if (p instanceof SpritePerson) {
        // Hail the cab when it's close enough to matter.
        p.hailing = !this.ride && Math.hypot(w.curb.walk.x - this.car.pos.x, w.curb.walk.z - this.car.pos.z) < 80;
        p.tick(this.camera, this.clock, this.look.settings.people);
      }
    }
  }

  // Swap waiting passengers between sprites and 3D models (look panel toggle).
  private get premium() { return CABS[this.cabIndex].id === 'wayfarer'; } // Waymo's perk: sees every fare, pays 1.3×

  // The tag over a waiting passenger. In the Wayfarer it also shows what they want and roughly what they'll pay.
  private labelText(type: PassengerType, name: number, want: WantId, c: Curb, dest: Landmark) {
    let text = nameTag(type, name);
    if (this.premium) {
      const pay = (4 + blocks(c.road, dest.curb.road) * 0.05) * type.fareMul * SURGE[this.surge][3] * 1.3;
      text += ` · ${WANTS[want].icon} ${WANTS[want].title} · $${Math.round(pay)}`;
    }
    return text;
  }

  private fareLabel(type: PassengerType, name: number, want: WantId, c: Curb, dest: Landmark) {
    const label = makeLabel(this.labelText(type, name, want, c, dest), { bg: type.vip ? '#3a2a00e0' : '#000000c0', fg: type.vip ? '#ffd23a' : '#ffffff', height: 1 });
    label.position.copy(c.walk).add(new THREE.Vector3(0, 3.4, 0));
    return label;
  }

  // Redraw every waiting fare's tag (after switching cab, or as the surge changes).
  private relabelFares() {
    for (const w of this.waiting) {
      w.marker.remove(w.label);
      const old = (w.label as THREE.Sprite).material; // sprites share one geometry: free only the texture and material
      old.map?.dispose();
      old.dispose();
      w.label = this.fareLabel(w.type, w.name, w.want, w.curb, w.dest);
      w.marker.add(w.label);
    }
  }

  refreshPassengers() {
    for (const w of this.waiting) {
      this.scene.remove(w.person.root);
      w.person = this.makePassenger(w.type);
      w.person.root.position.copy(w.curb.walk);
      w.person.root.rotation.y = w.curb.facing;
      this.scene.add(w.person.root);
    }
  }

  private updateWaiting(dt: number) {
    this.idleAnimations(dt);
    // With a passenger aboard, the others' rings and beams are just noise: hide them (they still wait).
    const room = !this.ride || (this.carpool && this.aboard < CARPOOL_MAX);
    for (const w of this.waiting) w.marker.visible = room;
    if (!room || this.car.speed > 4) return;
    const w = this.waiting.find((w) => flat(w.curb.road, this.car.pos) < 7);
    if (w) this.pickup(w);
  }

  private pickup(w: Waiting) {
    this.scene.remove(w.person.root, w.marker);
    this.waiting = this.waiting.filter((x) => x !== w);
    const d = blocks(w.curb.road, w.dest.curb.road);
    const [give, limit, hard] = SURGE[this.surge];
    const total = (d / 19 + 6) * w.type.timeMul * limit;
    const want = new Want(w.want, askLine(w.type.id, w.want), total, hard);
    const ride: Ride = {
      type: w.type, name: w.name, moodT: 9, dest: w.dest, base: 4 + d * 0.05, total, left: total, startDist: d,
      tips: 0, equity: 0, fareMul: w.type.fareMul, filmed: false, firedDone: false, firedT: 0,
      rerouted: false, incidents: 0, slowT: 0, idleT: 7, timeLowSaid: false, want,
    };
    if (this.ride) {
      // Zoombox carpool: they ride along with their own stop, timer and want.
      ride.marker = this.poolMarker(ride.dest);
      this.pool.push(ride);
      this.popup(t('pop.carpool', { n: this.aboard }), 'big good');
      this.relead();
    } else {
      this.ride = ride;
      this.showWantCard(this.ride);
    }
    // Part of the fare's time limit goes on the shift clock (less as the surge climbs): deliver fast and keep the change.
    this.time += total * give;
    this.popup(t('pop.time', { n: Math.round(total * give) }), 'big good');
    if (this.ride === ride) this.setDest(w.dest);
    sfx.pickup();
    this.popup(fullName(w.type.id, w.name), 'big');
    this.quips.line(w.type.id, ride.want.ask, nameTag(w.type, w.name)); // they say what they want
    if (this.pool.includes(ride)) {
      const host = [this.ride, ...this.pool].find((x) => x && x !== ride)!;
      if (this.rand() < 0.6) this.say(host, 'carpool', { delay: 3.2 });
      else this.quips.say('cab', 'carpool', { delay: 3.2 });
    } else if (this.premium && this.rand() < 0.4) {
      if (this.rand() < 0.6) this.say(ride, 'premium', { delay: 3.2 });
      else this.quips.say('cab', 'premium', { delay: 3.2 });
    } else if (this.rand() < 0.35) this.quips.say('cab', 'pickup', { delay: 3 });
    while (this.waiting.length < WAITING_COUNT) this.spawnWaiting();
  }

  // A carpool rider's destination: a smaller orange beam (the lead's is the big teal one).
  private poolMarker(dest: Landmark) {
    const g = new THREE.Group();
    const c = dest.curb.road;
    g.add(groundRing(c.x, c.z, 6, 7.2, 0xff9a3a, 0.85));
    g.add(beam(c, 6, 40, 0xff9a3a, 0.2));
    const label = makeLabel(place(dest.name), { bg: '#4a2a0ae0', fg: '#ffd2a0', height: 2.2 });
    label.position.set(c.x, c.y + 12, c.z);
    g.add(label);
    this.scene.add(g);
    return g;
  }

  // The lead ride is the one whose stop is nearest: the arrow, fare panel and want panel follow it.
  private relead() {
    const lead = this.ride;
    if (!lead || !this.pool.length || lead.firedT > 0) return;
    const dist = (r: Ride) => blocks(this.car.pos, r.dest.curb.road);
    const best = this.pool.reduce((a, b) => (dist(b) < dist(a) ? b : a));
    if (dist(best) >= dist(lead) - 20) return; // a margin, so the lead doesn't flicker
    this.pool = this.pool.filter((p) => p !== best);
    if (best.marker) this.scene.remove(best.marker);
    best.marker = undefined;
    lead.marker = this.poolMarker(lead.dest);
    this.pool.push(lead);
    this.ride = best;
    this.setDest(best.dest);
    this.showWantCard(best);
  }

  // The Zoombox's other riders: their clocks run, their wants fill, and any of them can be dropped off.
  private updatePool(dt: number) {
    if (!this.pool.length) return;
    const airborne = !this.car.grounded, sliding = this.car.grounded && Math.abs(this.car.lateral) > 3 && this.car.speed > 8;
    for (const p of [...this.pool]) {
      p.left -= dt;
      if (p.left <= 0) { this.walkout(p); continue; }
      p.want.tick(dt, this.car.speed, p.left / p.total, airborne && (p.type.id !== 'cmo' || p.filmed), sliding);
      if (flat(this.car.pos, p.dest.curb.road) < 9 && this.car.speed < 5) this.dropoff(p);
    }
    if (Math.floor(this.clock * 2) !== Math.floor((this.clock - dt) * 2)) this.relead();
  }

  private updateRide(dt: number) {
    this.updatePool(dt);
    const r = this.ride;
    if (!r) return;
    const id = r.type.id;

    if (r.firedT > 0) {
      r.firedT -= dt;
      if (r.ejected) r.ejected.armR.rotation.z = r.ejected.raise + Math.sin(this.clock * 9) * r.ejected.raise * 0.15;
      if (r.ejected instanceof SpritePerson) r.ejected.tick(this.camera, this.clock, this.look.settings.people);
      if (r.firedT <= 0) {
        if (r.ejected) this.scene.remove(r.ejected.root);
        r.ejected = undefined;
        r.fareMul *= 2;
        this.say(r, 'back', { force: true });
        this.popup(t('pop.back'), 'big good');
        sfx.pickup();
      }
      return;
    }

    r.left -= dt;
    if (r.left <= 0) return this.walkout(r);
    // The CMO's air only counts once her phone is up (after the first jump).
    const airborne = !this.car.grounded && (r.type.id !== 'cmo' || r.filmed);
    const sliding = this.car.grounded && Math.abs(this.car.lateral) > 3 && this.car.speed > 8;
    const before = r.want.stars;
    r.want.tick(dt, this.car.speed, r.left / r.total, airborne, sliding);
    if (r.want.id !== 'ontime' && r.want.stars > before) {
      this.popup('★'.repeat(r.want.stars), 'good');
      sfx.tip();
      if (this.rand() < 0.3) this.say(r, `good.${r.want.id}`);
    }
    this.wantMood(r, dt);

    const remaining = blocks(this.car.pos, r.dest.curb.road) / r.startDist;
    if (id === 'sweater' && !r.firedDone && remaining < 0.55) this.fireSweater(r);
    if (id === 'rocket' && !r.rerouted && remaining < 0.5) this.reroute(r);

    if (this.car.speed < 5 && flat(this.car.pos, r.dest.curb.road) > 25) {
      r.slowT += dt;
      if (r.slowT > 3) { this.say(r, 'slow', { force: true }); r.slowT = -6; }
    } else r.slowT = Math.min(0, r.slowT + dt);

    if (r.left < 6 && !r.timeLowSaid) { r.timeLowSaid = true; this.say(r, 'timeLow', { force: true }); }
    r.idleT -= dt;
    if (r.idleT <= 0) {
      r.idleT = 8 + this.rand() * 6;
      if (this.rand() < 0.8) this.say(r, 'idle');
      else this.quips.say('cab', 'idle');
    }

    if (flat(this.car.pos, r.dest.curb.road) < 9 && this.car.speed < 5) this.dropoff(r);
  }

  // A rider speaks, with their own name tag on the bubble.
  private say(r: Ride, event: QuipEvent, opts: { delay?: number; vars?: Record<string, string>; force?: boolean } = {}) {
    return this.quips.say(r.type.id, event, { ...opts, who: nameTag(r.type, r.name) });
  }

  // Every so often a rider says how their want is going: pleased when the stars are ahead
  // of the clock, fed up when they're behind it.
  private wantMood(r: Ride, dt: number) {
    r.moodT -= dt;
    if (r.moodT > 0) return;
    r.moodT = 9 + this.rand() * 7;
    const w = r.want;
    if (w.id === 'smooth') { if (w.stars >= 4) this.say(r, 'good.smooth'); return; }
    const elapsed = 1 - r.left / r.total;
    const due = w.id === 'ontime' ? 5 * (1 - elapsed) : 1 + elapsed * 4; // the stars they'd expect by now
    if (w.stars >= due) this.say(r, `good.${w.id}`);
    else if (w.stars < due - 1.5) this.say(r, `bad.${w.id}`);
  }

  private fireSweater(r: Ride) {
    r.firedDone = true;
    r.firedT = 5;
    const p = this.makePassenger(r.type);
    const f = this.car.fwd;
    p.root.position.set(this.car.pos.x - f.y * 3.5, 0, this.car.pos.z + f.x * 3.5);
    p.root.position.y = groundAt(p.root.position.x, p.root.position.z);
    p.root.rotation.y = this.car.yaw;
    this.scene.add(p.root);
    r.ejected = p;
    this.say(r, 'fired', { force: true });
    this.popup(t('pop.fired'), 'big bad');
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
    this.say(r, 'reroute', { force: true, vars: { dest: place(dest.name) } });
    this.popup(t('pop.rerouted'), 'big bad');
  }

  private walkout(r: Ride = this.ride!) {
    this.say(r, 'walkout', { force: true });
    if (this.rand() < 0.5) this.quips.say('cab', 'walkout', { delay: 2.6 });
    this.popup(t('pop.bailed'), 'big bad');
    sfx.bad();
    this.combo = 0;
    this.leave(r);
  }

  // A passenger gets out (delivered or bailed): the next nearest carpool rider becomes the lead.
  private leave(r: Ride) {
    if (r !== this.ride) {
      this.pool = this.pool.filter((p) => p !== r);
      if (r.marker) this.scene.remove(r.marker);
      return;
    }
    this.ride = null;
    this.setDest(null);
    if (!this.pool.length) return;
    const dist = (p: Ride) => blocks(this.car.pos, p.dest.curb.road);
    const next = this.pool.reduce((a, b) => (dist(b) < dist(a) ? b : a));
    this.pool = this.pool.filter((p) => p !== next);
    if (next.marker) this.scene.remove(next.marker);
    next.marker = undefined;
    this.ride = next;
    this.setDest(next.dest);
    this.showWantCard(next);
  }

  private dropoff(r: Ride) {
    const ratio = r.left / r.total;
    const [grade, mul] = ratio > 0.45 ? [t('grade.speedy'), 1.3] as const : ratio > 0.15 ? [t('grade.nice'), 1] as const : [t('grade.slow'), 0.8] as const;
    const others = this.aboard - 1; // Zoombox carpool: +25% for every other rider still aboard
    const fare = Math.round(r.base * r.fareMul * mul * SURGE[this.surge][3] * (this.premium ? 1.3 : 1) * (1 + 0.25 * others));
    if (others > 0) this.popup(t('pop.carpoolBonus', { n: 1 + 0.25 * others }), 'good');
    this.cash += fare;
    this.popup(t('pop.saved', { grade, n: Math.ceil(r.left) }), 'big');
    this.popup(t('pop.fare', { money: money(fare) }), 'good');
    // The passenger rates the ride on what they wanted: the stars set the tip and move the driver rating.
    if (r.want.id === 'ontime') r.want.tick(0, 0, ratio, false, false);
    const stars = Math.max(1, r.want.stars);
    this.starsGiven.push(stars);
    this.safety = Math.min(100, Math.max(0, this.safety + [0, -15, -8, -2, 2, 6][stars]));
    if (this.safety <= 0) this.gameOver('deactivated');
    const tip = Math.round(r.base * [0, 0, 0.25, 0.6, 1, 1.6][stars] * r.type.tipMul);
    let line = tip ? t('stamp.tip', { money: money(tip) }) : t('stamp.noTip');
    if (r.type.id === 'rocket') {
      const promise = Math.max(1, tip) * 100000;
      this.promised += promise;
      line = t('stamp.tipNextYear', { money: money(promise) });
    } else if (r.type.id === 'founder') {
      this.equity += tip * 10;
      line = tip ? t('stamp.shares', { n: tip * 10 }) : t('stamp.noShares');
    } else this.cash += tip;
    this.stamp(stars, `${r.want.def.title} ${r.want.shown} · ${line}`);
    const surgeBefore = this.surge;
    this.fares++;
    if (this.surge > surgeBefore) {
      this.relabelFares(); // prices went up
      this.popup(t('pop.surge', { n: SURGE[this.surge][3] }), 'big bad');
      sfx.armed();
      this.quips.say('cab', 'surge', { delay: 3.5 });
    }
    sfx.cash();
    this.say(r, 'dropoff', { force: true });
    if (this.rand() < 0.3) this.quips.say('cab', 'dropoff', { delay: 3 });
    this.leave(r);
  }

  private setDest(dest: Landmark | null) {
    if (this.destMarker) this.scene.remove(this.destMarker);
    this.destMarker = null;
    if (!dest) return;
    const g = new THREE.Group();
    const c = dest.curb.road;
    g.add(groundRing(c.x, c.z, 7, 8.5, 0x46e0c4, 0.9));
    g.add(beam(c, 8, 60, 0x46e0c4, 0.22));
    const label = makeLabel(place(dest.name), { bg: '#0b3d36e0', fg: '#7dfff0', height: 3 });
    label.position.set(c.x, c.y + 16, c.z);
    g.add(label);
    this.destMarker = g;
    this.scene.add(g);
  }

  private gameOver(reason: 'time' | 'deactivated') {
    if (this.state !== 'play') return;
    this.state = 'over';
    document.body.dataset.state = 'over';
    try { localStorage.setItem('clankers.rating', this.rating.toFixed(2)); } catch { /* storage unavailable */ }
    let equityLine = '';
    if (this.equity > 0) {
      const exit = this.rand() < 0.15;
      if (exit) this.cash += this.equity;
      equityLine = `<div>${t(exit ? 'over.acquired' : 'over.folded', { n: this.equity, money: money(exit ? this.equity : 0) })}</div>`;
    }
    const given = this.starsGiven;
    const starLine = given.length ? `<div>${t('over.stars', { avg: (given.reduce((a, b) => a + b, 0) / given.length).toFixed(1), n: given.filter((n) => n === 5).length })}</div>` : '';
    const airLine = this.maxAir > 0.85 ? `<div>${t('over.air', { s: secs(this.maxAir) })}</div>` : '';
    const promiseLine = this.promised ? `<div>${t('over.promised', { money: money(this.promised) })}</div>` : '';
    const shift = `${Math.floor(this.shiftTime / 60)}:${String(Math.floor(this.shiftTime % 60)).padStart(2, '0')}`;
    const ov = $('#overlay');
    ov.className = 'dim';
    ov.innerHTML = `
      <h2>${t(reason === 'deactivated' ? 'over.deactivated' : 'over.timeUp')}</h2>
      <div class="stats">
        <div>${t(reason === 'deactivated' ? 'over.deactivatedSub' : 'over.timeUpSub')}</div>
        <div>${t('over.summary', { shift, fares: this.fares, rating: this.rating.toFixed(2) })}</div>
        ${starLine}${airLine}${equityLine}${promiseLine}
        <div class="total">${money(this.cash)}</div>
      </div>
      <div class="press pad-only">${btn('confirm', t('over.again'))}</div><div class="pad pad-only">${btn('back', t('over.change'))}</div>
      <div class="tap-row touch-only">${tapButton('confirm', t('over.again'), 'go')}${tapButton('back', t('over.change'))}</div>`;
    sfx.bad();
  }

  // ---------- camera & HUD ----------

  private driveCamera(dt: number) {
    const car = this.car;
    let diff = car.yaw - this.camYaw;
    diff = Math.atan2(Math.sin(diff), Math.cos(diff));
    this.camYaw += diff * (1 - Math.exp(-4 * dt));
    const speedT = Math.min(1, car.speed / MAX_SPEED);
    const tune = this.look.settings;
    const back = tune.camBack + speedT * 2, up = tune.camUp + speedT * 0.6;
    const want = new THREE.Vector3(car.pos.x - Math.sin(this.camYaw) * back, car.pos.y + up, car.pos.z - Math.cos(this.camYaw) * back);
    want.y = Math.max(want.y, groundAt(want.x, want.z) + 1.5);
    this.camera.position.lerp(want, 1 - Math.exp(-10 * dt));
    const cam = this.camera.position;
    cam.y = Math.max(cam.y, groundAt(cam.x, cam.z) + 1.2);
    this.shake *= Math.exp(-6 * dt);
    if (this.shake > 0.01) this.camera.position.add(new THREE.Vector3((this.rand() - 0.5) * this.shake, (this.rand() - 0.5) * this.shake, 0));
    this.camera.lookAt(car.pos.x + Math.sin(this.camYaw) * 4, car.pos.y + 1.6, car.pos.z + Math.cos(this.camYaw) * 4);
    const fov = tune.fov + speedT * 14;
    if (Math.abs(this.camera.fov - fov) > 0.1) { this.camera.fov = fov; this.camera.updateProjectionMatrix(); }
    this.sun.position.set(car.pos.x + 60, car.pos.y + 110, car.pos.z + 35);
    this.sun.target.position.copy(car.pos);
    sunDir.value.copy(this.sun.position).sub(this.sun.target.position).normalize();
  }



  private updateArrow() {
    let target: THREE.Vector3 | null = null;
    if (this.ride) {
      target = this.ride.dest.curb.road;
      const t = this.ride.left / this.ride.total;
      const c = t > 0.45 ? 0x7dff6a : t > 0.15 ? 0xffd23a : 0xff4a3a;
      this.arrowMat.color.set(c);
      this.arrowMat.emissive.set(c);
      this.arrow.scale.setScalar(0.8);
    } else {
      let best = Infinity;
      for (const w of this.waiting) {
        const d = flat(w.curb.road, this.car.pos);
        if (d < best) { best = d; target = w.curb.road; }
      }
      this.arrowMat.color.set(0xffffff);
      this.arrowMat.emissive.set(0x888888);
      this.arrow.scale.setScalar(0.5);
    }
    this.arrow.visible = !!target && this.state === 'play';
    if (!target) return;
    const p = this.car.pos;
    const ahead = new THREE.Vector3(target.x - p.x, 0, target.z - p.z).normalize();
    // Centre the arrow over the cab; its pivot is the tail.
    // Float just under the camera's eye line, a little ahead of the cab, so it never blocks the road.
    const height = Math.min(3.4, this.look.settings.camUp * 0.62 + 1.25);
    const fwd = this.car.fwd;
    this.arrow.position.set(
      p.x + fwd.x * 2.2 - ahead.x * 1.65 * this.arrow.scale.x,
      p.y + height + Math.sin(this.clock * 4) * 0.08,
      p.z + fwd.y * 2.2 - ahead.z * 1.65 * this.arrow.scale.x,
    );
    // Point level along the ground, but roll the arrow about its own length so
    // its face turns towards the camera and never reads as an edge-on slab.
    const dir = new THREE.Vector3(target.x - p.x, 0, target.z - p.z).normalize();
    const toCam = this.camera.position.clone().sub(this.arrow.position);
    toCam.addScaledVector(dir, -toCam.dot(dir)).normalize();
    const up = new THREE.Vector3(0, 0.55, 0).addScaledVector(toCam, 0.45).normalize();
    const side = new THREE.Vector3().crossVectors(up, dir);
    this.arrow.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(side, up, dir));
    // Pointing away from the camera there's no face to roll towards it, so lift the tip a little.
    const camFwd = new THREE.Vector3(Math.sin(this.camYaw), 0, Math.cos(this.camYaw));
    const lift = 0.16 * Math.max(0, dir.dot(camFwd));
    this.arrow.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -lift));
  }

  private updateHud() {
    $('#time').textContent = String(Math.ceil(this.time));
    const surge = this.surge;
    $('#surge').textContent = surge ? t('hud.surge', { n: SURGE[surge][3] }) : '';
    $('#clock').classList.toggle('low', this.time < 10);
    $('#money').textContent = money(this.cash);
    $('#rating .score b').textContent = this.rating.toFixed(2);
    $('#rating .fill').style.width = `${this.safety}%`;
    $('#rating').classList.toggle('low', this.safety < 30);
    $('#speed b').textContent = String(Math.round(this.car.speed * 2.237));
    $('#combo').textContent = this.combo > 1 ? t('hud.combo', { n: this.combo }) : '';
    const lc = this.car.launchCharge;
    $('#launch').hidden = lc <= 0;
    $('#launch .fill').style.width = `${Math.min(100, (lc / 0.8) * 100)}%`;
    $('#launch').classList.toggle('armed', lc >= 0.35);
    const fare = $('#fare');
    const r = this.ride;
    fare.classList.toggle('hidden', !r);
    if (r) {
      const face = $<HTMLImageElement>('#fare .face');
      const src = `/portraits/${r.type.id}.avif`;
      if (!face.src.endsWith(src)) face.src = src;
      const who = $('#fare .who');
      who.textContent = nameTag(r.type, r.name) + (this.pool.length ? `  ${t('hud.aboard', { n: this.pool.length })}` : '');
      who.style.color = SPEAKERS[r.type.id].color;
      $('#fare .dest').textContent = r.firedT > 0 ? t('hud.firedNote') : `→ ${place(r.dest.name)}`;
      $('#fare .clock').textContent = r.firedT > 0 ? `${Math.ceil(r.firedT)}` : `${Math.ceil(r.left)}`;
      const share = r.left / r.total;
      fare.classList.toggle('warn', share <= 0.45 && share > 0.15);
      fare.classList.toggle('urgent', share <= 0.15);
    }
    // What this passenger wants, under the timer: like the driver rating, five stars to fill.
    const want = $('#want');
    want.classList.toggle('hidden', !r);
    if (r) {
      const w = r.want;
      $('#want .lbl').textContent = t('hud.wants', { name: shortName(r.type.id, r.name).toUpperCase() });
      $('#want .score b').textContent = `${w.def.icon} ${w.def.title}`;
      $('#want .fill').style.width = `${(w.fill * 100).toFixed(1)}%`;
      $('#want .note').textContent = w.targets.length ? t('hud.goal', { goal: w.targets.at(-1)!.toUpperCase(), now: w.shown.toUpperCase() }) : t('hud.everyBump');
    }
  }

  popup(text: string, cls = '') {
    const el = document.createElement('div');
    el.className = `popup ${cls}`;
    el.textContent = text;
    el.style.setProperty('--tilt', `${(Math.random() * 8 - 4).toFixed(1)}deg`);
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
      pos.push(x, groundAt(x, z) + 0.15, z);
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
