# GAME: Chocolate Doom + Freedoom (T05)

Approved by the team in [#6](https://github.com/kaktamsdengami/player-two/issues/6) (defaults 1–7).

## Choice and licence

| | |
|---|---|
| Engine | [Chocolate Doom](https://github.com/chocolate-doom/chocolate-doom) 3.1.1, GPL-2.0, by Simon Howard and contributors (id Software source release). |
| Fork | [kaktamsdengami/chocolate-doom](https://github.com/kaktamsdengami/chocolate-doom), branch `player-two-qa` (commit `7a354254`), based on tag `chocolate-doom-3.1.1`. Licence and credits unchanged. |
| Game data | [Freedoom](https://freedoom.github.io/) 0.13.0 `freedoom1.wad`, BSD-3-Clause, by the Freedoom project. Downloaded at build time, never committed. |
| Why | Chocolate Doom keeps vanilla Doom's engine bugs on purpose, so documented vanilla bugs are still live and have public write-ups and fixes in other ports. |

`freedoom1.wad` SHA-256 (0.13.0): `7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`.

## QA build flags (fork only, separate from any fix)

| Flag | Effect |
|---|---|
| `-qa-tics N` | **Frame-step.** In a level the game clock is frozen; every new key press lets it run `N` tics (35 = 1 s of game time), then it freezes again. Menus, intermissions and demos run in real time. |
| `-qa-framestep` | Same as `-qa-tics 35`. |
| `-qa-slowmo K` | The game clock runs `K` times slower (in a level). |
| `-qa-log FILE` | JSONL event log, one `GameEvent` (see `app/contracts.py`) per line: `level`, `spawn`, `player` (trace), `pickup`, `damage`, `death`, `kill`, `powerup`, `message`, `face`, `render`, `qa`. For the verifier only. |
| `-qa-trace N` | Log the player state every `N` tics (default 35, 0 = off). |
| `-qa-script FILE` | Timed QA actions, one per line `<leveltic> <cmd> [args]`: `health n`, `hurt n`, `give <power>`, `god`, `warp x y angle`, `move forward side turn tics`, `shot [n]`, `quit`. |
| `-qa-wall-err P`, `-qa-wall-len N` | Log a `render` event when a wall at least `N` units long (default 512) is drawn with a distance error of at least `P` % (default 0.5). |
| Reset | `-warp E M -skill S` (fresh map) or `-loadgame N` (a save) — stock Chocolate Doom flags. |

Wipes (screen melt) are disabled while a QA clock flag is on, so a frozen game never hangs in a melt.

The tester agent never gets the event log, the scripts, or `eval/known_bugs.yaml`; it plays from pixels.

## Build on Linux (verified on Devin's Ubuntu 22.04 VM)

```bash
sudo apt-get install -y build-essential autoconf automake libtool pkg-config python3 \
  libsdl2-dev libsdl2-mixer-dev libsdl2-net-dev libpng-dev libsamplerate0-dev
git clone -b player-two-qa https://github.com/kaktamsdengami/chocolate-doom.git
cd chocolate-doom && ./autogen.sh && make -j8          # -> src/chocolate-doom
curl -LO https://github.com/freedoom/freedoom/releases/download/v0.13.0/freedoom-0.13.0.zip
unzip -j freedoom-0.13.0.zip freedoom-0.13.0/freedoom1.wad
sha256sum freedoom1.wad                               # must match the hash above
```

## Build on Windows (stage laptop, needs:local)

Same steps as the upstream CI job "MSYS2 UCRT64" (`.github/workflows/main.yml`), which now also
runs on pushes to `player-two-qa` once GitHub Actions is enabled on the fork. In an
**MSYS2 UCRT64** shell:

```bash
pacman -S --needed autotools zip git mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-python-pip \
  mingw-w64-ucrt-x86_64-SDL2 mingw-w64-ucrt-x86_64-SDL2_mixer mingw-w64-ucrt-x86_64-SDL2_net \
  mingw-w64-ucrt-x86_64-libpng mingw-w64-ucrt-x86_64-libsamplerate mingw-w64-ucrt-x86_64-fluidsynth
git clone -b player-two-qa https://github.com/kaktamsdengami/chocolate-doom.git
cd chocolate-doom && ./autogen.sh && make -j4
cd pkg/win32 && make       # zip with chocolate-doom.exe and the DLLs
```

Or download the `Win64` artifact of the fork's CI run instead of building.

## Run

Agent run (stage, frame-step, borderless fullscreen, no mouse):

```bash
chocolate-doom -iwad freedoom1.wad -warp 1 1 -skill 3 -nomouse -nosound \
  -qa-tics 35 -qa-log run.jsonl
```

Scripted reproduction of a known bug (windowed, quits on its own):

```bash
chocolate-doom -iwad freedoom1.wad -warp 1 1 -skill 3 -window -nosound -nomouse \
  -nomonsters -qa-trace 0 -qa-log kb1.jsonl -qa-script qa/kb1_kb2_medikit.txt
```

`shot` writes `DOOMnn.pcx` into the working directory.

## Known bugs (hidden list: `eval/known_bugs.yaml`)

| ID | Bug | Map | Script (in the fork) | Evidence |
|---|---|---|---|---|
| KB1 | "REALLY need" medikit message never shows | E1M1 | `qa/kb1_kb2_medikit.txt` | `docs/game/kb1_medikit_message.png` |
| KB2 | Ouch face never shows on a big hit | E1M1 | `qa/kb1_kb2_medikit.txt` | `docs/game/kb2_no_ouch_face.png` |
| KB3 | Sky ignores the invulnerability colormap | E1M1 | `qa/kb3_sky_invul.txt` | `docs/game/kb3_sky_invulnerability.png` |
| KB4 | Long-wall wobble | E1M7 | `qa/kb4_e1m7_along.txt` | `docs/game/kb4_long_wall_e1m7.png` |
