# VJTB Effect Authoring Rules

These rules are binding for humans and AI agents adding or changing effects in `src/effects/*`. Each one exists because breaking it shipped a real defect during QA. The defect is cited in brackets.

## 1. Portability (the exported .fs must run everywhere)
1. **Single pass only for built-ins.** Resolume's docs list float/bool/color/event inputs for Wire ISF nodes, and a staff forum reply said multipass ISF was still in progress. Persistent buffers are allowed only in *imported* shaders, which the runtime and TouchDesigner export still support.
2. **GLSL ES 1.00 subset.**
   - Loop bounds must be constants; use `if (...) break;` for variable counts.
   - Use float literals (`2.0`, not `2`).
   - Do not use `round()`, `tanh()`, int `clamp/max/min`, `%`, `switch`, arrays with initialisers, `texture()` or `#version`.
   - Declare no `uniform` for ISF inputs, because the host declares them.
   - Do not name identifiers `gl_*`. [`vec2 gl` passed WebGL but is risky on desktop drivers]
3. **Sample images only through `IMG_NORM_PIXEL` / `IMG_PIXEL`, and never put a comma inside their arguments.** Hosts may bind `sampler2DRect`. The official ISF-JS parser splits macro arguments on *every* comma, so `IMG_NORM_PIXEL(inputImage, clamp(uv, 0.0, 1.0))` fails to compile there. Use `imgClamp(uv)`, or compute the coordinate into a local first. [Found by `scripts/isf_reference_check.py`: all 25 effects failed in the reference renderer until fixed]
4. **Convert `long` and `bool` inputs before use:** `int(float(uX) + 0.5)` and `bool(uX)`. The same body then compiles where the input is an int (ISF spec), a float (the Wire-safe flavour) or a `#define` (TouchDesigner).
5. **Write output only through `vjOut(col, solid)` or `vjOutPM(premultipliedRGBA)`.** These give straight alpha for ISF hosts and premultiplied alpha for TouchDesigner (`VJ_PREMULT`).
6. **Use only the uniforms in `UNIVERSAL_PARAMS` and the category param set**, plus effect-specific extras that are listed in the effect's `params`.

## 2. Brand integrity (sponsors reject melted logos)
1. **The logo must be fully legible at rest.** At rest means growth/fold/crystal = 100%, glitch between bursts, or a stinger's hold phase. [Vortex v1 noise-eroded the letterforms; Crystal v1 replaced the silhouette with jagged cells]
2. **Never recolour the logo with a hard-coded hue.** Derive colours from `uTint` / `uTint2` / the palette, or keep `logo.rgb`. [Glass backdrop was hard-coded magenta, then a sickly green derived from `uTint.gbr`]
3. **Keep ink contrast automatic.** A white logo on a white paper or plate must still read. [Origami v1 printed white-on-white]

## 3. Alpha & framing
1. **Transparent outside the effect.** Glows must fall to exactly zero, so use `edgeGlow(sd, k, r)`, never a bare `exp(-abs(sd)*k)`. A bare `exp` leaves a full-frame floor wherever the distance field saturates. [Vortex v1 haze and Iris v1 rim covered 100% of the frame]
2. **Stingers draw nothing outside progress 0..1.** Skip shutter taps at t ≤ 0 or t ≥ 1 rather than clamping them. [Clamped taps left a full-screen tunnel and flash while idle]
3. **Keep particles near the logo.** Mask motes by logo proximity (`logoField(p, 0.16).x`) and keep density low. Full-frame noise reads as dirt on an LED wall. [Spores v1 filled every frame with dots]

## 4. Controls must do something visible
1. **Every exposed control needs a measurable effect.** It must change the frame by a mean |Δ| ≥ 1.5 (0–255 scale) between its min and max at the QA probe state. Values below 0.4 count as DEAD, and dead controls must be wired up or removed. [Baseline: 26 DEAD + 35 WEAK = 61 of 175 controls across the first 25 effects; the fix passes took that to 0 DEAD (the 21 remaining WEAK controls are logged in `VISUAL-QA.md`). An earlier version of this line said 31, a figure that cannot be reproduced from the baseline sweep]
2. **Reinterpret a category control that has no physical meaning in an effect.** Give it a meaning and document it in the param `hint`. Example: Mercury "Collision Bounce" became surface-tension ripple.
3. **Audio Reactivity must produce Δ ≥ 1.5 between silence and a kick.** Drive at least one structural property (scale, density, displacement), not only brightness.

## 5. Motion quality
1. **Keep idle animation under control.** Mean 60 fps frame-to-frame Δ at idle should stay below 2.0, except where flicker is the point (static, VHS, fast particle swarms). Note any exception in VISUAL-QA.md.
2. **Stateless particles move continuously.** When back-tracing particle layers, iterate the age fixed point (≥2 iterations) so grains slide rather than jump between layers.
3. **Use a constant-velocity scrolling grid for flow-field motion.** A particle's birth position is `current − velocity·age`, so emission can be tested against the logo exactly.

## 6. Verification (required before an effect is "done")
1. `python3 scripts/visual_check.py --compile-only` must pass all four targets: WebGL2, GLSL ES 1.00, TouchDesigner and Wire-safe. `python3 scripts/isf_reference_check.py` must report 0 failures in the official ISF-JS renderer. `node scripts/isf-lint.mjs` must be clean on the exported `.fs`.
2. `python3 scripts/qa_effects.py --only <id> --tag <name>` must show no DEAD controls.
3. `python3 scripts/visual_check.py --gif --only <id> --out verify-out/gif`, then view `<id>-gifsheet.png` **at full size**. Do not judge from thumbnails, and do not trust a render until its pixel extrema have been checked. [The first render pass was entirely black because of a GLSL3/`gl_FragColor` mismatch]
4. `python3 .claude/skills/vjtb-visual-qa/scripts/strobe_check.py --only <id> --presets all` must exit 0 (section 8.4), and the beat sheet it writes is what you judge a `dj` look on.
5. Someone other than the author reviews the sheets (the independent-critic workflow in `.claude/skills/vjtb-visual-qa/SKILL.md`). An author who approves their own effect reads intent into frames the audience will never see.
6. Record the critique (what was wrong, what changed, the numbers, the audience and the logo used) in `VISUAL-QA.md`.

## 7. Host facts (do not guess, these were verified)
- **Resolume Arena:**
  - REST and WebSocket run at `/api/v1` on port 8080. There is no Arena v2.
  - Set a parameter with `{"action":"set","parameter":"/parameter/by-id/<id>","value":<native>}`.
  - OSC input is on port 7000 and takes 0..1 floats.
  - `/composition/layers/N/dashboard/linkK` is the documented effect-agnostic OSC target.
- **Resolume Wire:**
  - The REST API is `/api/v2` on port 8081.
  - ISF runs through the ISF node; Arena does not load `.fs` files natively.
  - Patches with Category Effect appear in Arena.
- **TouchDesigner:**
  - Does not load ISF, so use the GLSL TOP translation.
  - Vector uniforms use the `vec` sequence (`vec0name`, `vec0valuex`...).
  - There is no built-in time uniform; bind `absTime.seconds`.
  - Web Server DAT callbacks take `dat` first.
  - The official TDMCP listens on 13316. The community `Pantani/tdmcp` also uses 9980.

## 8. Audience (who the look is for)
Every effect sets `audience: 'brand' | 'dj' | 'both'` in its `EffectDef`. The tag decides which of the qualities below is judged first. It never suspends sections 1 to 5, and it never raises the strobe cap in 8.4. The QA scripts pick the logo from the tag (`--logo auto`: the NOVA sample mark for `dj`, the VJTB mark otherwise). NOVA is only a stand-in for the DJ's own logo, so a look must not depend on its particular shape.
1. **Brand looks (sponsors, corporate, broadcast).** The logo is fully legible at rest (2.1) in every preset, and its silhouette is exact. Motion is restrained and eased, materials are believable (metal, glass, ink, light), and colour comes from the tint. Judge it by asking whether a sponsor would sign off on it on a stage screen. A loud, busy look fails here even if it is technically clean.
2. **DJ looks (clubs, festivals, streams).** Judge impact and beat response first. A kick must change structure (scale, displacement, cuts, segment count), not only brightness (4.3). Beat-locked motion reads `uBeat` and not a grid derived from `TIME`: `uBeat` is in phase with the 124 BPM test kick, while `TIME` restarts with the clock and drifts off the kick in the app. Contrast is high and the palette fits the genre (techno cold and mono, hardstyle red and black, psytrance UV and acid, house warm). Genre palettes live in the preset tint values, not as hard-coded hues in the shader (2.2). A tasteful look with no punch fails here.
3. **The logo lands on the beat or in the hold.** A DJ look may break up between hits, but its beat-locked hits must resolve to the clean logo on the downbeat (the first 15% of a beat, the gold tiles in the beat sheet). A stinger must be fully legible in its hold phase. A look that is never readable fails 2.1 whatever its audience.
4. **Strobe safety applies to every audience, DJ looks most of all.** No look may produce more than **3 flashes per second** over a meaningful part of the picture at its default and preset values at 124 BPM. A flash is a pair of opposing luminance changes of at least 0.1 relative luminance with the darker state under 0.8 (or a saturated-red equivalent), over at least a quarter of a third-of-frame window, as in WCAG 2.3.1. `strobe_check.py` is the screen and exits 1 on a failure. Gate beat flashes with `strobeGate` (`.claude/skills/isf-effect-designer/references/techniques.md`), which caps the rate. If a control can push a look past 3 flashes per second at its extreme, say so in that control's `hint`. The screen cannot see control extremes or other tempos, and it is not a certified flash analysis, so broadcast deliverables still need the broadcaster's own test.
5. **`both` looks serve two readers.** Preset 0 passes the brand rules, at least one other preset passes the DJ rules, every preset passes 8.4 and 2.1, and QA runs with both marks (`--logo brand` and `--logo dj`).
