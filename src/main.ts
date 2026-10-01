import * as THREE from 'three';
import { Game } from './game';
import './style.css';

const canvas = document.getElementById('view') as HTMLCanvasElement;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;

const game = new Game(renderer);
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
