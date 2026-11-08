# Kid mode in the browser

`index.html` + `kid.js`: Doom runs in the page; `voice/kid_web.py` serves it, keeps the keys and
gives Pixel its eyes (H Holo), voice (ElevenLabs) and ears (Gladia live, push-to-talk).

`websockets-doom.js` / `websockets-doom.wasm` are Chocolate Doom for WebAssembly, built from
[cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm) @ 65e0d3a (GPL-2.0, source there)
with emsdk 3.1.61 (`emscripten/emsdk:3.1.61` Docker image, `./scripts/build.sh`). Two flag changes
in `configure.ac`: `SAFE_HEAP=0` and `STACK_OVERFLOW_CHECK=0` (SAFE_HEAP aborts with "alignment
fault"), and `EXPORTED_RUNTIME_METHODS=[FS,ccall,callMain]`. emsdk >= 3.1.62 builds a game that
draws no floors on the left of the screen (cloudflare/doom-wasm#9), so stay on 3.1.61.

The WAD is served from `data/freedoom1.wad` (or `P2_KID_WAD`): Freedoom, BSD licence.
