# Dashboard radio

Three kinds of station: **internet radio** (the defaults), **YouTube** playlists or videos, and **your own files**. All of them play with the radio collapsed to a small sticker in the lower-left corner; click the sticker for the controls.

## Stations

`DEFAULT_STATIONS` in `src/radio.ts` starts with six game-soundtrack YouTube playlists (Crazy Taxi, Jet Set Radio, Jet Set Radio Future, Tony Hawk's Pro Skater 1-4, Aggressive Inline, SSX Tricky), each checked on 2026-10-02 to allow embedding on every track, then eleven internet radio stations, one per genre: punk, alt rock, hip hop, US rap, synthwave, drum & bass, house, funk, city pop / future funk, cumbia and lo-fi. Each is a licensed broadcaster's public HTTPS MP3 stream, played through a plain audio element and credited by name ("Punk · via Polygon.FM"). They were found through the [Radio Browser](https://www.radio-browser.info/) directory and checked to stream on 2026-10-01. Streams come and go: if one fails, the radio skips to the next station; replace dead ones in `DEFAULT_STATIONS`. SomaFM's streams refuse requests from other sites' players, so they aren't used.

Open **Radio** on the title or pause menu with **M / X** to add a station (a YouTube playlist or video URL, or any `https://` stream URL), rename, reorder or remove stations. Stations and volume persist in localStorage (`clankers.radio.v2`; defaults added since a list was saved join it once, and a default you remove stays removed; anything added under the first build's `v1` key is carried over, minus its two placeholder stations).

YouTube stations play through the official IFrame API from a player kept off screen, so they behave like the others. That is outside YouTube's terms for embedded players (which want the player visible); it's Ben's call for a personal site. YouTube's own ads still play.

**Play my own files** / **Choose folder** play local audio through blob URLs; nothing is uploaded. Choose them again after a reload.

## Controls

- **Tap LB / T:** next station. **Hold LB / T:** the station wheel opens and the game slows; aim with the right stick (or left/right) and release to tune. The wheel includes My files and Off.
- **X / N:** next track (on a live radio station, the next station).
- In the Radio screen: D-pad/stick moves focus, A activates, B/Esc returns, left/right adjusts a focused volume slider.

The radio ducks to 60% while the game's voice blips play. See [browser checks](../tests/README.md) for the automated tests.
