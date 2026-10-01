import * as THREE from 'three';
import { Game } from './game';
import { loadCab, loadPeople } from './models';
import { Pedestrians } from './pedestrians';
import { loadPassengerSprites } from './spritepeople';
import './style.css';

const canvas = document.getElementById('view') as HTMLCanvasElement;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;

const [cab, people] = await Promise.all([loadCab(), loadPeople()]);
const game = new Game(renderer, cab, people);
loadPassengerSprites().then((s) => { game.paxSprites = s; game.refreshPassengers(); }).catch((err) => console.warn('No passenger sprites:', err));
Pedestrians.load(game.scene).then((p) => { game.peds = p; }).catch((err) => console.warn('No pedestrians:', err));
const fit = () => {
  renderer.setSize(innerWidth, innerHeight, false);
  game.resize(innerWidth, innerHeight);
};
addEventListener('resize', fit);
fit();

let last = performance.now();
renderer.setAnimationLoop((now) => {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  game.frame(dt);
});

// Handy for poking at the game from the console.
(window as unknown as { game: Game }).game = game;
