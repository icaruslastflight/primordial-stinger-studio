# VJTB Stinger Studio: architecture reference

Read `SKILL.md` first. This file is the lookup table: where things live, what the messages look like, and the order to rebuild the app from its spec. Verify against the code before relying on a name; the app is changing (user presets and a program-only viewport were being added when this was written).

Contents: 1 File map · 2 Effect model · 3 Shader pipeline · 4 State · 5 Engine loop · 6 Sync protocols · 7 Verification harness · 8 Ports · 9 Rebuild from spec · 10 Not verified

## 1. File map
| Path | Role |
|---|---|
| `src/effects/types.ts` | `EffectDef`, `ParamDef`, `EffectPreset`, `AutoDef`, `Audience`, `CategoryId` |
| `src/effects/common.ts` | `CATEGORIES`, param builders (`fl`, `long`, `bool`, `color`, `auto`), `UNIVERSAL_PARAMS`, `BEAT_PARAM` |
| `src/effects/{botanical,particle,volumetric,glitch,stingers}.ts` | The 25 built-in effects and each category's fixed param set (`FLORA`, `FLUID(tint)`, `METAL(tint)`, `GLITCH`, `STING` + `STING_MAIN`) |
| `src/effects/ext/<cat>.ts` | Empty extension slots, one per category, spread into the registry |
| `src/effects/registry.ts` | `BUILTIN_EFFECTS`, `deckItems`, `defaultValues`, `effectFromISF` (wraps an imported `.fs`) |
| `src/isf/glslLib.ts` | `GLSL_LIB` chunks with `provides` and `deps`; `resolveChunks(body)` tree-shakes by regex on the body |
| `src/isf/compose.ts` | `composeISF(effect, values, flavor)`, `isfFileStem` (`VJTB-<NameWithoutSpaces>`) |
| `src/isf/parse.ts` | `parseISF` (leading `/*{json}*/`), `stringifyHeader`, `bakeDefaults` |
| `src/isf/prelude.ts` | Uniform declarations and `IMG_*` macros for the runtime (WebGL2) and the strict GLSL ES 1.00 check |
| `src/isf/runtime.ts` | `ISFRenderer` on Three.js: typed inputs, multipass, persistent float buffers, audio and FFT textures |
| `src/isf/tdExport.ts` | ISF to TouchDesigner GLSL TOP translation and uniform table |
| `src/isf/validate.ts` | `compileReport`: WebGL2, GLSL ES 1.00 and the TD shim, with body-relative line numbers |
| `src/engine/engine.ts` | `StudioEngine`: owns the WebGL context, loop, thumbnails, push |
| `src/engine/{audio,automation,logo,instance}.ts` | Analyser and synthetic audio, LFOs and `resolveValues`, logo plate drawing (VJTB and NOVA marks), the engine singleton |
| `src/state/store.ts` | `useStudio` (zustand) and `live` (mutable per-frame data) |
| `src/sync/hub.ts` | `SyncHub`: `Conn` sockets, `tick`, `push`, Resolume composition scan |
| `src/ui/*` | `EffectDeck`, `Inspector` (Controls, Export, AI Setup, Sync), `ParamControl`, `SyncBar`, `Viewport` + `Transport`, `Toasts`, `primitives` |
| `src/prompts/prompts.ts` | AI Setup prompts, filled with live ports and the current effect |
| `src/state/presets.ts`, `src/prompts/skills.ts` | App branch only until merged: user presets (storage, JSON import and export) and the bundle of `.claude/skills/*/SKILL.md` + `references/*.md` for the AI Wizard tab and export pack |
| `src/verify.ts`, `verify.html` | Headless harness (`window.__verify`) for all scripts |
| `src/refcheck.ts`, `refcheck.html` | Official ISF-JS renderer cross-check (`window.__ref`) |
| `bridge/{core,osc,server}.mjs` | Origin-checked UDP OSC relay and file drop; Vite plugin and CLI share `core.mjs` |
| `td/vjtb_webserver_callbacks.py` | Web Server DAT callbacks that build `/project1/vjtb` and set uniforms |
| `scripts/*`, `.claude/skills/*/scripts/*` | Verification tools (see `SKILL.md` section 5) |

## 2. Effect model
- `EffectDef { id, category, audience?, name, blurb, params, glsl, presets, rawSource? }`. `id` is `<category>-<slug>`. `rawSource` marks an imported shader that bypasses the composer.
- `ParamDef.type`: `float | long | bool | color | point2D | event`. `driver` marks values the app supplies every frame: `audio-bass | audio-mid | audio-high | cue | beat`. A driver parameter is never hand-edited and is excluded from sweeps.
- `UNIVERSAL_PARAMS` (appended to every built-in): `uLumaKey`, `uAudioReact`, `uBass`, `uMid`, `uHigh`. `BEAT_PARAM` (`uBeat`) is an optional extra for beat-locked DJ looks.
- Presets are value overrides over `ParamDef.default`; `auto` overrides LFO settings. Params with `auto` start automated: touching the slider turns the LFO off (`setValue`), like a fader on a desk.
- Stingers implement `vec4 stingerFrame(vec2 p, float t)` and append `STING_MAIN` (6-tap shutter blur, shake, idle transparency). Their `uProgress` is driven by the cue (TAKE), or by TIME when `uLoop` is on.

## 3. Shader pipeline
**composeISF.** Header JSON (`ISFVSN "2"`, `CATEGORIES [label, "VJTB"]`, `INPUTS` = `inputImage` + one input per param with current values baked as DEFAULT), a comment block, the tree-shaken helper chunks in library order, then `// ---- effect ----` and the body.

**Flavours.** `spec`: `long` stays `long` with VALUES/LABELS. `wire`: Resolume documents float, bool, color and event inputs for Wire ISF nodes, so `long` becomes a stepped `float` (MIN 0, MAX n-1) whose LABEL lists the options. Bodies convert with `int(float(uX)+0.5)` and `bool(uX)` so both compile.

**Runtime (`ISFRenderer`).** `load()` parses, pre-compiles against the live WebGL2 context for readable errors (line numbers re-based to the body), then builds a `ShaderMaterial` with no `glslVersion` (Three adds GLSL1 compat defines: `gl_FragColor`, `texture2D`). Uniforms per input; `RENDERSIZE`, `TIME`, `TIMEDELTA`, `FRAMEINDEX`, `PASSINDEX`, `DATE`. Multipass and persistent buffers follow the ISF spec, but built-in effects are single pass because Wire's multipass support is unconfirmed. Output is a straight-alpha render target.

**Validation.** `compileReport` compiles: (1) the runtime source as WebGL2, (2) `webgl1Source` as strict GLSL ES 1.00 (the portability bar: constant loops, no implicit int to float), (3) each TD pass through `tdShimSource`. `verify.ts` adds the Wire-safe flavour. `refcheck.ts` loads both flavours in the official ISF-JS renderer.

**TouchDesigner translation (`toTouchDesigner`).** Per pass: `void main` becomes `isf_main`, `gl_FragColor` becomes `isf_FragColor`, `texture2D` becomes `texture`. Defines: `VJ_PREMULT`, `RENDERSIZE` = `uTDOutputInfo.res.zw`, `isf_FragNormCoord` = `vUV.st`, the `IMG_*` macros, images as `sTD2DInputs[n]` (logo first, buffers after). bool, long and event become `<name>_f` float uniforms with a `#define` back to the ISF name. `TIME`, `TIMEDELTA`, `FRAMEINDEX_F` are built-in uniforms bound by expression (`absTime.seconds`, `absTime.stepSeconds`, `absTime.frame`) because TD has no time uniform. Output goes through `TDOutputSwizzle`. A source that contains `vjOutPM` (every VJTB effect, via the library, with `VJ_PREMULT` defined) already outputs premultiplied alpha; an imported ISF without it is multiplied in `main`.

## 4. State
| Where | What | Rule |
|---|---|---|
| `useStudio` | effects list, selection, `values[effectId]`, `autos[effectId]`, logo and `logoVersion`, view, audio config (source, BPM, gain), sync config (persisted under `vjtb.sync.v1`), connection statuses, discovered Resolume effects, panel, toasts, thumbnails, compile error | Changes on user action or on a socket event. Never in the frame loop. |
| `live` | `values` (what drives the shader this frame), `audio`, `fps`, `frameMs`, `time`, `cue`, `msgRate` | Written by the engine loop. Read by rAF or interval callbacks into DOM refs. |
| `StudioEngine` fields | WebGL context, ISF renderers (main 1280x720 by default and a 256x144 thumbnail one), logo canvas and texture, thumbnail queue | Subscribes to the store for logo and resolution changes only. |
| localStorage | `vjtb.sync.v1` | Wrap in try/catch (private mode). Merge over defaults so old saves survive new fields. |

`window.__studio` is the store, exposed in dev builds only, for `e2e_sync.py` and UI scripts.

## 5. Engine loop (`StudioEngine.loop`, every frame)
1. Read the store; `ensureEffect` recompiles only when the selected effect id changes (preset and slider changes are uniform updates).
2. `audio.sample(now, bpm, gain)`: analyser bands with auto-gain, or the synthetic 124 BPM envelope (`syntheticAudio`). Cue progress for stingers from `cueStart`, with the hit SFX at the hit point.
3. `beat = ((now * bpm) / 60) % 1`, the `uBeat` driver. It shares `now` with the synthetic kick, so phase 0 is the kick onset. With mic or file audio it is still only the BPM clock; the app does not detect tempo from the music. `TIME` is `now - clockEpoch` and restarts, so it is not beat-aligned.
4. `resolveValues(effect, base, autos, time, drivers)` gives `live.values`: base, then LFOs, then drivers.
5. Render the ISF to the output target, draw it to the canvas, then `hub.tick(effect, values)`.
6. Every second frame, render one queued thumbnail (time 3.2 s, automated params at 80% of their range, bands 0.5/0.4/0.3, stingers at progress 0.55) and store a JPEG data URL.

## 6. Sync protocols
**TouchDesigner**, WebSocket to the Web Server DAT (default `ws://localhost:9980`), JSON text frames.
| App sends | Meaning | TD replies |
|---|---|---|
| `{t:'hello',app,version}` | on open | `{t:'hello',build}` |
| `{t:'ping',id}` | every 2 s, RTT | `{t:'pong',id}` |
| `{t:'logo',name,png_b64}` | write `vjtb_assets/vjtb_logo.png` and reload `logo_in` | none |
| `{t:'push',effect,name,stem,resolution,passes[],inputs[],uniforms[]}` | rebuild `/project1/vjtb`: `logo_in` to `pass0..N` (GLSL TOP, `shader_N` Text DAT, `fb_*` Feedback TOPs for later-pass buffers) to `out1` | `{t:'pushed',op,uniforms,errors}` |
| `{t:'params',effect,values:{name:[...]}}` | set `vecNvalue{x,y,z,w}` on every GLSL TOP, only where the parameter is in constant mode (the three built-in time uniforms stay expressions) | none |
Errors come back as `{t:'error',error,trace}`. Older TD builds use `uniname0/value0x`; the callbacks fall back.

**Bridge**, WebSocket (dev: `ws://localhost:5173/__vjtb`; CLI: `ws://127.0.0.1:9010`).
| App sends | Result |
|---|---|
| `{t:'ping',id}` | `{t:'pong',id,ts}` |
| `{t:'osc',packets:[{host,port,address,args:[{type:'f',value}]}]}` | UDP OSC 1.0 to private or loopback hosts only; others are counted in `stats.dropped` |
| `{t:'write',id,target:'resolume'|'td',files:[{name,content,encoding?}]}` | `{t:'written',files}` or `{t:'error',error}` |
| `{t:'stats'}` | counters |
On connect the bridge sends `{t:'hello',version,udp,host,exportDirs}`.

**Resolume Arena**, WebSocket `ws://localhost:8080/api/v1`. Arena pushes the whole composition JSON on connect; the hub reads `layers[].video.effects[]` and `layers[].clips[].video.effects[]` into `{key,label,params{name:{id,valuetype,min,max,options}}}`. Target: the effect chosen in the Sync panel, else the first whose normalised label contains the normalised effect name or `VJTB-<Name>`. Parameter match: normalised `label` or `name` or name without the leading `u`, or a key that starts with the normalised label (Wire appends option text to long labels). Values are native: `ParamColor` as `#rrggbbaa`, `ParamBoolean` as bool, `ParamChoice` as the label string, everything else a number.

**OSC out.** TD: `/vjtb/<effectId>/<param>` floats; colour and point2D split into `/x /y /z /w`. Resolume: the first eight non-driver float params to `/composition/layers/{layer}/dashboard/link{n}`, 0..1 by min and max. Address templates and the layer are user settings.

## 7. Verification harness (`verify.html`, `window.__verify`)
`list()` (ids, names, categories, `audience`, presets, auto param), `compileAll()` (four flags per effect), `load(id)`, `frames(id, preset, times, overrides, audio, logo?)` returning PNG data URLs plus per-frame stats (`coverage`, `clipped`, `meanLum`, `borderAlpha`), `params(id)`, `source(id, flavor)`, `setLogo('brand'|'dj')`, `logo()`, `logoPlate(which)`. Frames render at 640x360 from an explicit clock with `audio` of `synthetic` (124 BPM, `uBeat` from the same clock), `silent` or `kick` (bass 1, mid 0.8, high 0.8). Output is drawn over a checkerboard; read `rawStats` for alpha truth. Deterministic: reruns match to the last decimal.

## 8. Ports and addresses
| Thing | Default |
|---|---|
| App (Vite dev, main tree) | 5173; other agents' worktrees 5181 to 5185 |
| Bridge (dev plugin) | `ws://localhost:5173/__vjtb`; CLI `--port 9010` |
| TouchDesigner Web Server DAT | 9980 (collides with the community `Pantani/tdmcp`); official TDMCP 13316 |
| Resolume Arena REST/WebSocket | 8080, `/api/v1`; Wire REST 8081, `/api/v2`; OSC in 7000 |
| TD OSC In (default) | 10000 |
| `mock_hosts.mjs` | TD ws 9980, Arena 8080, UDP 7000 and 10000 (it holds the real hosts' ports, so stop real hosts first) |
| `osc-monitor.mjs <port>` | rehearse OSC without a host: set the app's Resolume OSC port to 7001 and run `node scripts/osc-monitor.mjs 7001` |

## 9. Rebuild from the spec: order that worked
The spec: a Vite/React/TS/Three.js/Tailwind/zustand app with an infinite smooth-scrolling effect deck; real-time preview; custom GLSL/ISF import; SVG/PNG logo import into a composition-sized straight-alpha plate; audio triggers (mic, line-in, file, BPM clock); a dual-mode sync bar with one-click push; 5 categories x 5 effects with granular controls; LFO automation; live OSC/WebSocket output; ISF export in three flavours plus a zip.
1. `isf/types`, `parse`, `compose`, `prelude`; get one trivial effect to compile on WebGL2 and strict ES 1.00.
2. `runtime.ts` (typed inputs, then multipass) and the checks in `validate.ts`. Look at pixel extrema before anything else.
3. `glslLib.ts`: logo access (`logoP`, `logoField`, `edgeGlow`), noise, `vjOut`, then effect helpers. Write down every portability rule as you hit it; they became `docs/EFFECT-RULES.md`.
4. Effects and registry, category by category, each through the `isf-effect-designer` loop.
5. `store`, `automation`, `audio`, `engine` (loop, thumbnails), then the UI: deck, inspector, transport, sync bar.
6. `tdExport.ts` and `td/vjtb_webserver_callbacks.py`, tested against `test_td_bridge.py`'s stub of the TD API.
7. `hub.ts` and `bridge/`, tested against `mock_hosts.mjs` and `e2e_sync.py`.
8. Scripts, `verify.ts`, the QA log, `REALITY-CHECK.md`, `AGENTS.md`, skills. Do the reality check before step 6, not after: the spec's Arena `/api/v2` and "TouchDesigner parses ISF natively" were both wrong.

## 10. Not verified (state this in every report)
No live TouchDesigner or Resolume was available: TD callbacks ran against a stub, Resolume against a mock built from the OpenAPI shapes. Timing was measured in SwiftShader only. Of each effect's three presets, only preset 0 has a control sweep. Strobe screening is a screen, not a certified Harding/PEAT analysis.
