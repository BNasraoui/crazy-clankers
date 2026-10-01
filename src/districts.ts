import * as THREE from 'three';

// San Francisco neighbourhoods on our 10x10 block grid (bi = west→east, bj = north→south).
// Each district sets how its buildings look: lot widths, storeys, colours and details.

export type DistrictId = 'fidi' | 'soma' | 'nob' | 'northbeach' | 'pacheights' | 'haight' | 'mission' | 'sunset' | 'potrero';

export interface District {
  id: DistrictId;
  name: string;
  lot: [number, number]; // lot width range, metres
  floors: [number, number];
  colors: number[];
  bays: number; // chance of a bay window on a lot
  gables: number; // chance of a gabled roof
  garages: number; // chance of a garage door
  cornerFloors: number; // extra storeys on corner buildings (0 = none)
  shops: number; // chance a corner building has a shopfront and awning
  yard: boolean; // small front yards instead of paving to the building line
  graffiti: number; // chance of a tag on a street-facing wall
}

const mute = (c: number, k = 0.2) => new THREE.Color(c).lerp(new THREE.Color(0xc9c2b6), k).getHex();

export const DISTRICTS: Record<DistrictId, District> = {
  fidi: { id: 'fidi', name: 'Financial District', lot: [20, 20], floors: [10, 30], colors: [], bays: 0, gables: 0, garages: 0, cornerFloors: 0, shops: 0, yard: false, graffiti: 0 },
  soma: {
    id: 'soma', name: 'SoMa', lot: [10, 14], floors: [4, 6],
    colors: [0xa65a42, 0xb8724a, 0x8f8578, 0xc4b9a3, 0x9b6b4f, 0xb0a48e].map((c) => mute(c, 0.1)),
    bays: 0, gables: 0, garages: 0.5, cornerFloors: 1, shops: 0.3, yard: false, graffiti: 0.12,
  },
  nob: {
    id: 'nob', name: 'Nob Hill', lot: [12, 18], floors: [6, 9],
    colors: [0xe8dcc0, 0xd9cbb0, 0xcfc4b0, 0xbfb6a6, 0xe2d6bd].map((c) => mute(c, 0.1)),
    bays: 0.4, gables: 0, garages: 0.1, cornerFloors: 2, shops: 0.3, yard: false, graffiti: 0,
  },
  northbeach: {
    id: 'northbeach', name: 'North Beach', lot: [7, 9], floors: [3, 4],
    colors: [0xf3dc8a, 0xf0c4a2, 0xe9e3d6, 0xd98a6c, 0xb7dcc4, 0xf2e6cc].map((c) => mute(c)),
    bays: 0.6, gables: 0, garages: 0.3, cornerFloors: 1, shops: 0.7, yard: false, graffiti: 0.03,
  },
  pacheights: {
    id: 'pacheights', name: 'Pacific Heights', lot: [9, 11], floors: [3, 4],
    colors: [0x9fb2bf, 0xb3c79c, 0xe9e3d6, 0x8e9aa6, 0xc8bfae, 0xa9b9a0].map((c) => mute(c)),
    bays: 0.8, gables: 0.5, garages: 0.4, cornerFloors: 0, shops: 0, yard: false, graffiti: 0,
  },
  haight: {
    id: 'haight', name: 'Haight / Alamo Square', lot: [6, 7.5], floors: [3, 3],
    colors: [0x9fbad3, 0xb7dcc4, 0xf3dc8a, 0xd98a6c, 0xc7b8d8, 0xf0c4a2, 0xe58fa5].map((c) => mute(c)),
    bays: 0.9, gables: 0.45, garages: 0.45, cornerFloors: 1, shops: 0.5, yard: false, graffiti: 0.03,
  },
  mission: {
    id: 'mission', name: 'Mission', lot: [6, 8], floors: [2, 3],
    colors: [0xf2cf55, 0xe58fa5, 0x5f9ec2, 0x86c07a, 0xee8f5a, 0xb08ad8, 0xf3dc8a].map((c) => mute(c, 0.15)),
    bays: 0.7, gables: 0.1, garages: 0.5, cornerFloors: 1, shops: 0.8, yard: false, graffiti: 0.15,
  },
  sunset: {
    id: 'sunset', name: 'Twin Peaks / Sunset', lot: [7.5, 9], floors: [2, 2],
    colors: [0xf2ebdd, 0xeadfcf, 0xf0d9d4, 0xd8e6dc, 0xe6e2c8, 0xdcd8e8],
    bays: 0.3, gables: 0, garages: 1, cornerFloors: 0, shops: 0, yard: true, graffiti: 0,
  },
  potrero: {
    id: 'potrero', name: 'Potrero Hill', lot: [7, 10], floors: [2, 3],
    colors: [0xb7dcc4, 0xf2e6cc, 0x9fbad3, 0xd98a6c, 0xa65a42, 0x8f8578].map((c) => mute(c)),
    bays: 0.4, gables: 0.15, garages: 0.6, cornerFloors: 0, shops: 0.2, yard: false, graffiti: 0.06,
  },
};

export function districtOf(bi: number, bj: number): District {
  const d = DISTRICTS;
  if (bi >= 7 && bj <= 3) return d.fidi;
  if (bi >= 6 && bj >= 4 && bj <= 6) return d.soma;
  if (bi >= 4 && bi <= 6 && bj >= 1 && bj <= 3) return d.nob;
  if (bj <= 1 && bi >= 2 && bi <= 6) return d.northbeach;
  if (bi <= 2 && bj <= 4) return d.pacheights;
  if (bi <= 1 && bj >= 5) return d.sunset;
  if (bi >= 6 && bj >= 7) return d.potrero;
  if (bj >= 6) return d.mission;
  return d.haight;
}
