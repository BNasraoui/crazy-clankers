import type { PersonSpec } from './models';
import type { Speaker } from './quips';
import type { WantId } from './wants';

export interface PassengerType {
  id: Exclude<Speaker, 'cab'>;
  label: string;
  vip: boolean;
  weight: number; // spawn odds
  timeMul: number; // < 1 means less time to make the drop
  fareMul: number;
  tipMul: number;
  jumpMul: number;
  prefers: string[]; // favourite destinations (landmark names)
  wants: WantId[]; // one is picked per trip
  person: PersonSpec;
}

const SKIN = [0xf1c8a8, 0xd9a47e, 0xa8714f, 0x6f4a33, 0xe8b996];

export const PASSENGERS: PassengerType[] = [
  {
    id: 'techbro', label: 'TECH BRO', vip: false, weight: 3, timeMul: 1, fareMul: 1, tipMul: 1, jumpMul: 2,
    prefers: ['Phlz Coffee', 'Series A Lounge', "Barri's Bootcamp", 'Dragon Gate'], // dim sum, for the 'gram
    wants: ['speed', 'air', 'closecalls'],
    person: { shirt: 0x9cc3e6, vest: 0x3c4a5a, pants: 0xb9a77a, hair: 0x5a3a22, skin: SKIN[0] },
  },
  {
    id: 'cmo', label: 'ABG CMO', vip: false, weight: 3, timeMul: 1, fareMul: 1, tipMul: 1, jumpMul: 3,
    prefers: ['Painted Ladies', 'Salesfarce Tower', 'Dolores Park', 'Palace of Fine Arts', 'Lombard Street'], // backdrops
    wants: ['air', 'drift'],
    person: { shirt: 0xf29ac0, pants: 0x1a1a1a, hair: 0x15110f, skin: SKIN[4], longHair: true, height: 0.95 },
  },
  {
    id: 'ceo', label: 'PSYCHO CEO', vip: false, weight: 2, timeMul: 0.65, fareMul: 2, tipMul: 1.5, jumpMul: 1,
    prefers: ['Salesfarce Tower', 'The Pyramid', 'Ferry Building', 'City Hall'], // a quiet word with the Mayor
    wants: ['speed', 'reckless', 'ontime'],
    person: { shirt: 0x161616, pants: 0x161616, hair: 0x9a9a9a, skin: SKIN[1] },
  },
  {
    id: 'founder', label: 'THE FOUNDER', vip: false, weight: 2, timeMul: 1, fareMul: 1, tipMul: 1, jumpMul: 1,
    prefers: ['Crypto Castle', 'Series A Lounge', 'Sand Hill On-Ramp', 'City Hall'], // permits, eventually
    wants: ['reckless', 'speed'],
    person: { shirt: 0xe07b1a, pants: 0x34507a, hair: 0x2a1c12, skin: SKIN[2] },
  },
  {
    id: 'sweater', label: '★ THE SWEATER', vip: true, weight: 0.7, timeMul: 1, fareMul: 1.5, tipMul: 1, jumpMul: 1,
    prefers: ['The Lab', 'Palace of Fine Arts'],
    wants: ['smooth'],
    person: { shirt: 0x8c8f94, pants: 0x2c3440, hair: 0x5a4030, skin: SKIN[0], height: 0.9 },
  },
  {
    id: 'rocket', label: '★ THE ROCKET GUY', vip: true, weight: 0.7, timeMul: 1, fareMul: 1.5, tipMul: 1, jumpMul: 1,
    prefers: ['Coit Tower', 'Ferry Building', 'Alcatraz'], // wants to buy it
    wants: ['air', 'speed'],
    person: { shirt: 0x111111, pants: 0x222222, hair: 0x3a2a1e, skin: SKIN[0], height: 1.12 },
  },
  {
    id: 'safety', label: '★ THE SAFETY GUY', vip: true, weight: 0.7, timeMul: 1.2, fareMul: 1.5, tipMul: 1, jumpMul: 1,
    prefers: ['The Lab', 'Dolores Park', 'Alcatraz'], // somewhere to keep the models
    wants: ['smooth', 'reckless'], // gentle, or gathering evidence of how dangerous these models are
    person: { shirt: 0x4f6fa8, pants: 0x3a3a3a, hair: 0x4a3020, skin: SKIN[0], curly: true, glasses: true },
  },
];

export function pickPassenger(r: () => number): PassengerType {
  const total = PASSENGERS.reduce((s, p) => s + p.weight, 0);
  let x = r() * total;
  for (const p of PASSENGERS) if ((x -= p.weight) <= 0) return p;
  return PASSENGERS[0];
}
