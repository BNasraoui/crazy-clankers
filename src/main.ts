import * as THREE from 'three';
import './fit';
import { Game } from './game';
import { treeRefs } from './world';
import { loadCars, loadPeople } from './models';
import { loadStreetKit } from './scenery';
import { loadFacades } from './facades';
import { loadSky } from './sky';
import { Pedestrians } from './pedestrians';
import { loadPassengerSprites } from './spritepeople';

const canvas = document.getElementById('view') as HTMLCanvasElement;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;

const [, people] = await Promise.all([loadCars(), loadPeople(), loadStreetKit(), loadFacades(), loadSky()]);
const game = new Game(renderer, people);
document.body.classList.add('ready'); // the boot screen's title is now the real one
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
(window as unknown as { game: Game; treeRefs: typeof treeRefs }).game = game;
(window as unknown as { treeRefs: typeof treeRefs }).treeRefs = treeRefs;
