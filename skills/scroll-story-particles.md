---
name: 'scroll-story-particles'
type: 'craft'
description: 'Build a scroll-driven story section where one particle field morphs through a sequence of shapes as the reader scrolls, with chapter copy in normal flow over a sticky canvas. Use for a scroll-telling hero, morphing particle scene, WebGL scroll animation, or story-driven landing page.'
validation_status: 'piloted'
last_validated: '2026-09-06'
sources:
  - '/Users/taborsmac/.cursor/skills/scroll-story-particles/SKILL.md'
  - '/Users/taborsmac/.cursor/skills/scroll-story-particles/reference.md'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/DESIGN.md @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/lib/oklch.ts @ 2c3bd9d'
---

# Scroll story particles

## Why this document exists

A landing page that "has a WebGL hero" is cheap. A landing page whose one particle field is the story, whose colour travels with the scroll, and whose still SVG is the product when the canvas never mounts, is not. This was derived once, at cost, and the next site should not re-derive the pin-host arithmetic, the rest-weight line lock, or the shader that morphs N baked shapes.

Load with `context/site-design-contract.md`. The canvas is an enhancement. Everything the reader needs is server-rendered.

## Architecture

One `points` mesh, N shapes baked as vertex attributes, a single scroll progress number driving both the morph and the page colour.

```
section[data-pin-host]                 progress = -rect.top / (height - vh)
  .stage (sticky, 100svh)              canvas mounts here, still SVG underneath
    SceneMount progressMode="pin"
    .stage-scrim                       gradient so text is legible by CSS, not luck
    StageIndex                         optional instrument strip
  Hero                                 chapter 00, normal flow
  Chapter × N                          min-height 100svh, align-content: end
```

Chapters sit in normal flow under the sticky stage (the stage is pulled back with a negative margin). With JS off the reader gets the same sequence over the SVG still.

Progress is measured against the pin host, not the document, so the colour finishes travelling when the story ends and stays put through the rest of the page. Reading progress from the document is how "hue travelled 0 degrees" happens.

## Shapes

Generate every shape as `Float32Array(n * 3)` in one deterministic pass (seeded RNG, fixed `n` for all shapes). Set each as `aP0` through `aPk` attributes; alias `position` to the first and set `frustumCulled={false}`.

Helpers that carry most shapes: `boxSurface`, `boxEdges`, `segment`, a value `noise(x, z)` for terrain, and `fit(points, n)` to pad or trim to exactly `n`.

Text as a shape: draw the word on an offscreen 2D canvas in the display font, sample lit pixels, map to scene units. Wrap in try/catch and fall back to a geometric stand-in — fonts may not be ready. Take the word's lateral offset as an input: beside the heading on landscape, centred on portrait.

Fix particle count and shape inputs at mount (`useState(() => …)`), never on resize. Rebuilding seven shapes on an address-bar resize is a hitch.

## Shader

The vertex stage picks neighbouring baked shapes with `mix(aP[i], aP[i+1], smoothstep(f))` where `i = floor(progress * (k - 1))`. Per-particle drift comes from a seed attribute. A flight term (`sin(f * PI)`) enlarges particles mid-morph. Point size is proportional to DPR over `-mv.z`. A pointer in NDC pushes particles away within a radius.

The fragment stage reads colour from a baked OKLCH ramp texture (`DataTexture`, 256 by 1), sampled by progress plus per-particle jitter. Never `mix()` two hex colours in sRGB — it goes through mud.

Worked example, seven shapes. Adapt `pick` and the clamp when `k` is not 7. The GLSL is the pattern, not a file to paste unchanged.

Vertex:

```glsl
attribute vec3 aP0; attribute vec3 aP1; attribute vec3 aP2; attribute vec3 aP3;
attribute vec3 aP4; attribute vec3 aP5; attribute vec3 aP6;
attribute vec3 aSeed;
uniform float uProgress;
uniform float uTime, uSize, uDpr, uAspect, uPush;
uniform vec2  uPointer;
varying float vAlpha, vCore, vFlight, vJitter;

vec3 pick(int i) {
  if (i <= 0) return aP0; if (i == 1) return aP1; if (i == 2) return aP2;
  if (i == 3) return aP3; if (i == 4) return aP4; if (i == 5) return aP5;
  return aP6;
}

void main() {
  float t = clamp(uProgress, 0.0, 6.0);
  int i = int(floor(t));
  float f = t - float(i);
  vec3 a = pick(i), b = pick(min(i + 1, 6));

  float delay = aSeed.x * 0.42;
  float ff = clamp((f - delay) / 0.58, 0.0, 1.0);
  ff = ff * ff * (3.0 - 2.0 * ff);
  float flight = sin(ff * 3.14159265);

  vec3 p = mix(a, b, ff);
  vec3 dir = normalize(aSeed - 0.5 + vec3(0.0001));
  p += dir * flight * (0.35 + aSeed.y * 1.1);
  p += vec3(sin(uTime*0.6 + aSeed.x*6.2832), cos(uTime*0.45 + aSeed.y*6.2832),
            sin(uTime*0.5 + aSeed.z*6.2832)) * (0.014 + flight * 0.08);

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  vec4 clip = projectionMatrix * mv;

  vec2 ndc = clip.xy / clip.w;
  vec2 d = ndc - uPointer; d.x *= uAspect;
  float dist = length(d) + 0.0001;
  float push = smoothstep(0.42, 0.0, dist) * uPush;
  clip.xy += (d / dist) * push * 0.16 * clip.w;
  gl_Position = clip;

  float size = uSize * (0.55 + aSeed.z * 1.15) * (1.0 + flight * 1.4);
  gl_PointSize = size * uDpr * (5.6 / max(0.5, -mv.z));
  vAlpha = (0.32 + aSeed.z * 0.68) * (1.0 - flight * 0.45);
  vCore = step(0.9, aSeed.z);
  vFlight = flight;
  vJitter = (aSeed.y - 0.5) * 0.16;
}
```

Fragment, additive on a dark ground. Convert hex to linear (`THREE.Color().convertSRGBToLinear()`). Material: `transparent`, `depthWrite: false`, additive blending.

```glsl
precision highp float;
uniform sampler2D uRamp;
uniform vec3 uInk, uBg;
uniform float uPhase;
varying float vAlpha, vCore, vFlight, vJitter;

void main() {
  vec2 c = gl_PointCoord - 0.5;
  float r = length(c);
  float disc = smoothstep(0.5, 0.1, r);
  float ph = clamp(uPhase + vJitter, 0.0, 1.0);
  vec3 tint = texture2D(uRamp, vec2(ph, 0.5)).rgb;
  vec3 col = mix(mix(uBg, tint, 0.42), tint, vAlpha);
  col = mix(col, tint, vFlight * 0.6);
  col = mix(col, uInk, vCore * smoothstep(0.3, 0.0, r));
  gl_FragColor = vec4(col, disc * vAlpha);
}
```

## Colour travel

CSS and the shader must agree. In CSS, `--live` mixes the two poles with `longer hue` against `--phase`. In TypeScript, the same curve (`mixOklchLonger`, `rampBytes`) bakes the texture. The audit samples both.

Write `--phase` in about 60 steps from an eased rAF follow, not every frame:

```
STEPS = 60
current += (target - current) * 0.06
step = round(current * STEPS)
if step != written: root.style.setProperty("--phase", step / STEPS)
```

Stop the loop when within `1 / (STEPS * 4)` of target, landing on the exact step. Pin `--phase` mid-scale under reduced motion (`0.45 !important`) so the reader still gets the direction's character.

## Fallbacks

`prefers-reduced-motion`: do not mount the scene; the still is the picture. No WebGL, low device budget, or JS off: the SVG still carries a title, the canvas is `aria-hidden`. Every chapter is plain prose with its figures and source in the DOM.

The mount gate is in-view (rootMargin 200px), not reduced-motion, WebGL present, `hardwareConcurrency >= 4`, not `saveData`, then `requestIdleCallback` to import the scene with a timeout. Cross-fade only on the first real frame, with a ~1.4s fallback that keeps the still.

## Line lock

Run after `document.fonts.ready`, before animating `wght`. Resting weight is the base state; the charge is the animation. The function below is the one that actually held. Rebuild it; do not import a previous site's class names.

```ts
function lockLines(el: HTMLElement) {
  if (el.dataset.linesLocked) return;
  el.dataset.linesLocked = "1";
  for (const n of Array.from(el.childNodes)) {
    if (n.nodeType === Node.COMMENT_NODE) n.remove();
  }
  el.normalize();
  for (const node of Array.from(el.childNodes)) {
    if (node.nodeType !== Node.TEXT_NODE || !node.textContent?.trim()) continue;
    const probes = node.textContent.split(/(\s+)/).filter(Boolean).map((p) => {
      const s = document.createElement("span");
      s.textContent = p;
      return s;
    });
    const frag = document.createDocumentFragment();
    probes.forEach((s) => frag.appendChild(s));
    node.replaceWith(frag);
    const lines: HTMLSpanElement[][] = [];
    let top: number | null = null;
    for (const s of probes) {
      const r = s.getBoundingClientRect();
      if (r.width === 0 && lines.length) {
        lines[lines.length - 1].push(s);
        continue;
      }
      if (top === null || Math.abs(r.top - top) > 1) {
        top = r.top;
        lines.push([]);
      }
      lines[lines.length - 1].push(s);
    }
    for (const line of lines) {
      const wrap = document.createElement("span");
      wrap.className = "line";
      wrap.style.display = "block";
      wrap.style.whiteSpace = "nowrap";
      line[0].before(wrap);
      wrap.textContent = line.map((s) => s.textContent).join("");
      line.forEach((s) => s.remove());
    }
  }
}
```

Strip comment nodes first. React SSR puts comment markers between adjacent text nodes, and interpolating two sentences will otherwise leave a lone period on its own line.

## Gotchas — things that have actually broken

**`ch` on a variable-weight heading.** Believed to be a character cap. `1ch` is the zero's advance and grows with `wght`. A 14-ch cap grew about 30% while charging 300 to 760 (CLS 0.12). Use `em`.

**Weight animation re-wrapping lines.** Believed the heading could charge in place. It could not. Lock lines at rest weight first, after fonts are ready.

**Progress read from the document.** Believed `--phase` would finish with the story. It finished with the page, so the live colour never travelled across the chapters ("hue travelled 0 degrees"). Measure against the pin host.

**Playwright at 127.0.0.1.** Turbopack blocked the chunks. The canvas never mounted, so the still was scored as the scene. Use `localhost` on the dev server.

**`mask-image` plates under chapter labels.** axe saw an opaque background that was not there. Paint fills as a degenerate gradient.

## Conventions

- The still is the finished picture. Nothing is lost if the scene never mounts.
- One mesh, N shapes, one progress number. Do not add a second particle system to "do the next chapter".
- Colour travel is OKLCH long-hue, in CSS and in the ramp texture, sampled by the audit.
- Particle count is fixed at mount.
- The seven hard rules in `context/site-design-contract.md` still apply.

## Off-limits

- Do not mount the scene eagerly, and do not gate `frameloop` on `inView` in a way that blanks the canvas when the section scrolls away if anything below the fold still has to talk to it. Linked controls sit beside the stage, not under it.
- Do not rebuild shapes on resize.
- Do not vendor the last site's `shapes.ts` or class prefix. The next story has different chapters.

## Definition of done

1. Every chapter is legible as plain prose with JS off and with reduced motion. The still has a title; the canvas is `aria-hidden`.
2. `--live` travels across the pin host and holds after the story. The audit's ramp samples all clear 4.5:1.
3. Headlines do not re-wrap while charging. Overflow is false at 390 / 768 / 1440.
4. Screenshots exist for the story at those widths, plus `--reduce` and `--nojs`.
5. The scene mounts only through the gate. A machine that fails the gate still has the still.
