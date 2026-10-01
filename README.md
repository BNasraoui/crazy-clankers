# Crazy Clankers

A Crazy Taxi-style arcade game where you play the robotaxi. Three.js + TypeScript + Vite.

    npm install
    npm run dev      # http://localhost:5173 (--host, so it's reachable from a Steam Deck on your network)
    npm run build    # static site in dist/

Controls: RT/W gas, LT/S brake and reverse, stick or A/D steer, B/RB/Space drift, Start/Esc pause.

- `src/quips.ts`: every passenger line. Edit freely.
- `src/passengers.ts`: passenger types, odds and fare and tip rules.
- `src/world.ts`: the map (hills, blocks, landmarks).
- `src/car.ts`: driving physics constants.
