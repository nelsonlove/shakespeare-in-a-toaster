# Web Version (toaster.nelson.love) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Client-side web version of the sonnet generator with a System 7 look, served as an assets-only Cloudflare Worker at toaster.nelson.love.

**Architecture:** Vanilla ES-module port of the Python engine (`web/public/engine.js`) driven by a no-framework UI (`index.html`/`style.css`/`app.js`); lexicon JSON copied from the Python package at build time; deployed with local `wrangler deploy`.

**Tech Stack:** Vanilla JS (ES2022), `node --test` (Node ≥ 20), wrangler 4.x, Cloudflare Workers static assets.

## Global Constraints

- Engine behavior must mirror `src/toaster/engine/composer.py` exactly (post-review-fix semantics: unfrozen lines cleared before compose; frozen literals not applicable on web — no file load).
- The lexicon single source of truth is `src/toaster/data/lexicon.json`; `web/public/lexicon.json` is build output, never edited (gitignored).
- Constants verbatim from the spec: scheme `"ABAB CDCD EFEF GG"`, line length 10, templates `01010101010` / `10010101010`, filler 32%, inversion 9%/3%, connective cascade percentages summing to 100.
- No frameworks, no bundler, no npm dependencies in `web/` (wrangler invoked via `npx wrangler@4`).
- Spec: vault `92212.10 Requirements & design/Web version design.md`.

---

### Task 1: Engine port with fidelity tests

**Files:**
- Create: `web/public/engine.js`
- Test: `web/test/engine.test.js`

**Interfaces:**
- Produces: `mulberry32(seed) -> () => float in [0,1)`; `class Engine { constructor(lexiconJson, rng?); newSonnet() -> Sonnet; rewrite(sonnet) -> void }`; `Sonnet = { lines: Line[] }`; `Line = { letter: string|null, verseNo: number, tokens: string[], endWord: {text,vowel,consonant}|null, frozen: boolean }`; helpers `lineText(line) -> string`, `sonnetText(sonnet) -> string`. Task 4 consumes all of these.

- [ ] **Step 1: Write the failing tests**

`web/test/engine.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Engine, mulberry32, sonnetText, lineText } from "../public/engine.js";

const lexicon = JSON.parse(
  readFileSync(new URL("../../src/toaster/data/lexicon.json", import.meta.url)));

const engine = (seed, opts = {}) => new Engine(lexicon, mulberry32(seed), opts);

test("sonnet has 14 verse lines and 3 blanks", () => {
  const s = engine(7).newSonnet();
  const verse = s.lines.filter(l => l.letter !== null);
  assert.equal(verse.length, 14);
  assert.equal(s.lines.length - verse.length, 3);
  for (const l of verse) {
    assert.ok(l.tokens.length > 0);
    assert.ok(l.endWord);
    assert.match(lineText(l)[0], /[A-Z]/);
  }
});

test("seeded determinism", () => {
  assert.equal(sonnetText(engine(42).newSonnet()),
               sonnetText(engine(42).newSonnet()));
  assert.notEqual(sonnetText(engine(42).newSonnet()),
                  sonnetText(engine(43).newSonnet()));
});

test("rhyme groups agree on vowel and never self-rhyme", () => {
  for (let seed = 0; seed < 20; seed++) {
    const s = engine(seed).newSonnet();
    const groups = {};
    for (const l of s.lines) {
      if (l.letter) (groups[l.letter] ??= []).push(l.endWord);
    }
    for (const words of Object.values(groups)) {
      assert.equal(new Set(words.map(w => w.vowel)).size, 1);
      const ends = words.map(w => w.text.toLowerCase());
      assert.equal(new Set(ends).size, ends.length);
    }
  }
});

test("masculine endings on even verse lines and line 13", () => {
  const e = engine(9);
  for (let i = 0; i < 20; i++) {
    const s = e.newSonnet();
    for (const l of s.lines) {
      if (!l.letter) continue;
      if (l.verseNo % 2 === 0 || l.verseNo === 13) {
        const cls = e.classOf(l.endWord);
        assert.ok(!e.patternOdd(cls).endsWith("0"),
          `line ${l.verseNo} feminine: ${lineText(l)}`);
      }
    }
  }
});

test("rewrite preserves frozen lines and rhymes against them", () => {
  const e = engine(11);
  const s = e.newSonnet();
  const verse = s.lines.filter(l => l.letter !== null);
  verse[0].frozen = true;
  const before = lineText(verse[0]);
  e.rewrite(s);
  assert.equal(lineText(verse[0]), before);
  assert.equal(verse[2].endWord.vowel, verse[0].endWord.vowel); // both 'A'
});

test("rewrite unlocks rhyme sounds when nothing is frozen", () => {
  const e = engine(2);
  const s = e.newSonnet();
  const vowels = new Set();
  for (let i = 0; i < 6; i++) {
    e.rewrite(s);
    vowels.add(s.lines.find(l => l.letter === "A").endWord.vowel);
  }
  assert.ok(vowels.size > 1);
});

test("connective distribution matches the 1989 cascade", () => {
  const e = engine(5);
  const n = 20000, counts = {};
  for (let i = 0; i < n; i++) {
    const w = e.connective("xylophone");
    counts[w] = (counts[w] ?? 0) + 1;
  }
  assert.ok(Math.abs(counts["the"] / n - 0.35) < 0.02);
  assert.ok(Math.abs(counts["no"] / n - 0.21) < 0.02);
  assert.ok(Math.abs(counts["and"] / n - 0.11) < 0.02);
  assert.ok(counts["a"] > 0 && !counts["an"]);
  const v = {};
  for (let i = 0; i < 5000; i++) {
    const w = e.connective("apple");
    v[w] = (v[w] ?? 0) + 1;
  }
  assert.ok(v["an"] > 0 && !v["a"]);
});
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd ~/repos/shakespeare-in-a-toaster && node --test web/test/`
Expected: FAIL — cannot find module `../public/engine.js`.

- [ ] **Step 3: Implement `web/public/engine.js`**

```js
/* Engine port of Shakespeare v1.0 (c) 1989-1991 Bob Schumaker.
   Mirrors src/toaster/engine/composer.py — see the reverse-engineering
   notes ("Sonnet engine internals", JD 92212). */

export const PAT_EVEN = ["0","01","01","10","11","10","01",
  "010","0101","1010","01010","1010","101","10101"];
export const PAT_ODD  = ["0","1","01","10","11","10","01",
  "010","0101","1010","01010","1010","101","10101"];
const TEMPLATE_NORMAL = "01010101010";
const TEMPLATE_INVERTED = "10010101010";
export const DEFAULT_SCHEME = "ABAB CDCD EFEF GG";
const LINE_LENGTH = 10;
const FILLER_PCT = 32, INVERT_Q = 9, INVERT_OTHER = 3;
const CONNECTIVES = [
  [35,"the"],[21,"no"],[11,"and"],[8,["a","an"]],[5,"of"],
  [5,["in a","in an"]],[3,"with"],[2,"for"],[1,"to"],
  [1,["for a","for an"]],[1,["by a","by an"]],[1,["to a","to an"]],
  [1,["with a","with an"]],[1,"they"],[1,"we"],[1,"O"],[1,"but"],[1,"thou"],
];
const MAX_LINE_RESTARTS = 10000;

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function lineText(line) {
  if (line.letter === null) return "";
  const joined = line.tokens.join(" ");
  return joined ? joined[0].toUpperCase() + joined.slice(1) : "";
}

export function sonnetText(sonnet) {
  return sonnet.lines.map(lineText).join("\n");
}

export class Engine {
  constructor(lexiconJson, rng = Math.random, { scheme = DEFAULT_SCHEME } = {}) {
    this.rng = rng;
    this.scheme = scheme;
    // classes[c] = [{text, vowel, consonant}]
    this.classes = Array.from({ length: 14 }, () => []);
    for (const entry of Object.values(lexiconJson)) {
      this.classes[entry.resource_id - 128] =
        entry.words.map(w => ({ text: w.word, vowel: w.rhyme[0], consonant: w.rhyme[1] }));
    }
    this.total = this.classes.reduce((n, c) => n + c.length, 0);
    this._classIndex = new Map();  // word text (lower) -> class id
    this.classes.forEach((words, c) =>
      words.forEach(w => this._classIndex.set(w.text.toLowerCase(), c)));
    // cumulative weights for class picking
    this._cum = [];
    let acc = 0;
    this.classes.forEach((words, c) => { acc += words.length; this._cum[c] = acc; });
  }

  classOf(word) { return this._classIndex.get(word.text.toLowerCase()); }
  patternEven(c) { return PAT_EVEN[c]; }
  patternOdd(c) { return PAT_ODD[c]; }

  randInt(n) { return Math.floor(this.rng() * n); }

  pickClass() {
    const r = this.randInt(this.total);
    return this._cum.findIndex(c => r < c);
  }

  connective(nextWord) {
    const roll = this.randInt(100);
    let acc = 0;
    for (const [pct, entry] of CONNECTIVES) {
      acc += pct;
      if (roll < acc) {
        if (Array.isArray(entry)) {
          return "aeiou".includes(nextWord[0].toLowerCase()) ? entry[1] : entry[0];
        }
        return entry;
      }
    }
    return "the";
  }

  newSonnet() {
    const lines = [];
    let verseNo = 0;
    for (const ch of this.scheme) {
      lines.push(ch === " "
        ? { letter: null, verseNo: 0, tokens: [], endWord: null, frozen: false }
        : { letter: ch, verseNo: ++verseNo, tokens: [], endWord: null, frozen: false });
    }
    const sonnet = { lines };
    this.rewrite(sonnet);
    return sonnet;
  }

  rewrite(sonnet) {
    for (const l of sonnet.lines) {
      if (l.letter !== null && !l.frozen) { l.tokens = []; l.endWord = null; }
    }
    for (const l of sonnet.lines) {
      if (l.letter !== null && !l.frozen) this._composeLine(sonnet, l);
    }
  }

  _groupRhyme(sonnet, line) {
    let code = null;
    const taken = [];
    for (const other of sonnet.lines) {
      if (other === line || other.letter !== line.letter) continue;
      if (other.endWord) {
        code ??= other.endWord.vowel + other.endWord.consonant;
        taken.push(other.endWord.text.toLowerCase());
      }
    }
    return [code, taken];
  }

  _composeLine(sonnet, line) {
    const [groupCode, takenEnds] = this._groupRhyme(sonnet, line);
    let strict = true;
    for (let restart = 0; restart < MAX_LINE_RESTARTS; restart++) {
      const tokens = [];
      let pos = 0, failed = false, endWord = null;
      while (pos < LINE_LENGTH) {
        const invert = pos === 0 && this.randInt(100) <
          ((line.verseNo - 1) % 4 === 0 ? INVERT_Q : INVERT_OTHER);
        const allowFiller = this.randInt(100) < FILLER_PCT;
        const tried = new Set();
        let placed = false;
        for (let attempt = 0; attempt < this.total; attempt++) {
          const cls = this.pickClass();
          const idx = this.randInt(this.classes[cls].length);
          const key = cls * 100000 + idx;
          if (tried.has(key)) continue;
          tried.add(key);
          const word = this.classes[cls][idx];
          const pattern = (pos & 1 ? PAT_ODD : PAT_EVEN)[cls];
          const template = invert && cls !== 5 ? TEMPLATE_INVERTED : TEMPLATE_NORMAL;
          if (!template.startsWith(pattern, pos)) continue;
          const needsFiller = (pos & 1) === 0 && cls === 1;
          if (needsFiller && !allowFiller) continue;
          if (pos + pattern.length >= LINE_LENGTH) {          // line ender
            if ((line.verseNo % 2 === 0 || line.verseNo === 13)
                && pattern.endsWith("0")) continue;
            if (groupCode !== null) {
              const code = word.vowel + word.consonant;
              if (code[0] !== groupCode[0]) continue;
              if (strict && code[1] !== groupCode[1]) continue;
              if (takenEnds.includes(word.text.toLowerCase())) continue;
            }
            endWord = word;
          }
          if (needsFiller) tokens.push(this.connective(word.text));
          tokens.push(word.text);
          pos += pattern.length;
          placed = true;
          break;
        }
        if (!placed) { failed = true; break; }
      }
      if (!failed) {
        line.tokens = tokens;
        line.endWord = endWord;
        return;
      }
      strict = false;
    }
    throw new Error(`could not compose line ${line.verseNo} — lexicon too constrained`);
  }
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `node --test web/test/`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/public/engine.js web/test/engine.test.js
git commit -m "feat(web): JS engine port with node fidelity tests"
```

---

### Task 2: Build script, wrangler config, gitignore

**Files:**
- Create: `web/build.sh`, `web/wrangler.jsonc`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `web/public/lexicon.json` (build output consumed by Task 4's `app.js` via `fetch("lexicon.json")`); `npx wrangler@4 deploy` config used by Task 5.

- [ ] **Step 1: Write `web/build.sh`**

```bash
#!/bin/sh
# Copy the single-source lexicon into the static bundle.
set -e
cd "$(dirname "$0")"
cp ../src/toaster/data/lexicon.json public/lexicon.json
echo "lexicon.json copied ($(wc -c < public/lexicon.json) bytes)"
```

Then: `chmod +x web/build.sh`

- [ ] **Step 2: Write `web/wrangler.jsonc`**

```jsonc
{
  "name": "shakespeare-toaster-web",
  "compatibility_date": "2026-07-01",
  "assets": { "directory": "./public" },
  "routes": [
    { "pattern": "toaster.nelson.love", "custom_domain": true }
  ]
}
```

- [ ] **Step 3: Gitignore the build output**

Append to `.gitignore`:

```
# Web build output (copied from src/toaster/data by web/build.sh)
web/public/lexicon.json
```

- [ ] **Step 4: Verify build works**

Run: `web/build.sh`
Expected: `lexicon.json copied (105258 bytes)` and `web/public/lexicon.json` exists.

- [ ] **Step 5: Commit**

```bash
git add web/build.sh web/wrangler.jsonc .gitignore
git commit -m "feat(web): build script and wrangler assets config"
```

---

### Task 3: System 7 UI shell (HTML, CSS, assets, font)

**Files:**
- Create: `web/public/index.html`, `web/public/style.css`
- Create: `web/public/assets/` (copied 1989 art), `web/public/fonts/` (ChicagoFLF if obtainable)

**Interfaces:**
- Produces: DOM ids consumed by Task 4's `app.js`: `#sonnet`, `#menubar` (menus with `data-menu`), menu items `#mi-new`, `#mi-save`, `#mi-copy`, `#mi-about`, `#mi-help`, palette buttons `#pal-rewrite`, `#pal-save`, `#pal-copy`, dialogs `#about-dialog`, `#help-dialog`, and `<template id="line-tpl">`.

- [ ] **Step 1: Copy the 1989 assets**

```bash
cd ~/repos/shakespeare-in-a-toaster && mkdir -p web/public/assets web/public/fonts
SRC="/Users/nelson/Documents/90-99 Projects/92 Software/92212 Shakespeare in a Toaster/92212.10 Original app & lexicon/UI assets"
cp "$SRC/ICON_200_Application_ICON.png" web/public/assets/toaster-head.png
cp "$SRC/ICON_128_Rewrite_sonnet.png"   web/public/assets/rewrite.png
cp "$SRC/ICON_129_Save_Sonnet.png"      web/public/assets/save.png
cp "$SRC/ICON_130_Read_Sonnet.png"      web/public/assets/copy.png
cp "$SRC/About_Shakespeare_portrait.png" web/public/assets/portrait.png
cp "$SRC/Help_screen.png"               web/public/assets/help.png
```

- [ ] **Step 2: Try to fetch ChicagoFLF (graceful if unavailable)**

```bash
curl -fsSL -o web/public/fonts/ChicagoFLF.ttf \
  "https://fontlibrary.org/assets/downloads/chicagoflf/df657f60ac9d1af26113ef6779ba3242/chicagoflf.zip" \
  && (cd web/public/fonts && unzip -o ChicagoFLF.ttf || true) || echo "font fetch failed — fallback stack only"
```

If the URL 404s, search for the current ChicagoFLF download (it's freeware) or continue with the CSS fallback stack; the `@font-face` rule is written to degrade silently.

- [ ] **Step 3: Write `web/public/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Presenting… Shakespeare In A Toaster</title>
<meta name="description" content="The 1989 Mac sonnet generator, in your browser. Click a line to freeze it; rewrite the rest.">
<link rel="icon" type="image/png" href="assets/toaster-head.png">
<link rel="stylesheet" href="style.css">
</head>
<body>
<nav id="menubar">
  <div class="menu" data-menu="apple"><span class="menu-title"></span>
    <div class="menu-items">
      <button id="mi-about">About Shakespeare…</button>
      <button id="mi-help">Shakespeare Help…</button>
    </div>
  </div>
  <div class="menu" data-menu="file"><span class="menu-title">File</span>
    <div class="menu-items">
      <button id="mi-new">New Sonnet&nbsp;&nbsp;⌘N</button>
      <button id="mi-save">Save</button>
    </div>
  </div>
  <div class="menu" data-menu="edit"><span class="menu-title">Edit</span>
    <div class="menu-items">
      <button id="mi-copy">Copy&nbsp;&nbsp;⌘C</button>
    </div>
  </div>
</nav>

<main id="desktop">
  <section class="window" id="main-window" aria-label="Shakespeare">
    <header class="title-bar"><span class="close-box"></span>
      <h1 class="title">Shakespeare</h1>
    </header>
    <div id="sonnet" aria-live="polite"></div>
  </section>

  <aside class="window palette" id="palette" aria-label="Tools">
    <header class="title-bar mini"></header>
    <button id="pal-rewrite" title="Rewrite sonnet (unfrozen lines)">
      <img src="assets/rewrite.png" alt="Rewrite"></button>
    <button id="pal-save" title="Save sonnet as text file">
      <img src="assets/save.png" alt="Save"></button>
    <button id="pal-copy" title="Copy sonnet to clipboard">
      <img src="assets/copy.png" alt="Copy"></button>
  </aside>
</main>

<dialog id="about-dialog" class="window modal">
  <div class="about-flex">
    <img src="assets/portrait.png" alt="Droeshout portrait of Shakespeare" width="192">
    <div class="credits-viewport"><div class="credits">
      <p><b>Shakespeare v1.0</b><br>© 1989–1991 by Bob Schumaker,<br>all rights reserved.</p>
      <p>Rewritten for the Macintosh by Bob Schumaker</p>
      <p>Overhauled by /rich $alz</p>
      <p>Composer code written by Chris Wilbur</p>
      <p>Thanks to Paul DuBois for the original TransSkel (now much modified).</p>
      <p>Portions © by THINK Technologies, Inc.</p>
      <p>No warranties expressed or implied.</p>
      <p>The suitability of this product for any purpose in not gauranteed.</p>
      <p>Web port, 2026 — a preservation project.<br>
         <a href="https://github.com/nelsonlove/shakespeare-in-a-toaster">Source &amp; story</a></p>
    </div></div>
  </div>
  <form method="dialog"><button class="ok">OK</button></form>
</dialog>

<dialog id="help-dialog" class="window modal">
  <img src="assets/help.png" alt="Original 1989 help screen" width="550">
  <p class="help-caption">On the web: the palette is Rewrite / Save / Copy, and clicking a line freezes it — shown inverted.</p>
  <form method="dialog"><button class="ok">OK</button></form>
</dialog>

<template id="line-tpl"><div class="line" role="button" tabindex="0"></div></template>
<script type="module" src="app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Write `web/public/style.css`**

```css
@font-face {
  font-family: "ChicagoFLF";
  src: url("fonts/ChicagoFLF.ttf") format("truetype");
  font-display: swap;
}
:root {
  --chicago: "ChicagoFLF", "Chicago", Geneva, "Helvetica Neue", monospace;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  font-family: var(--chicago);
  /* 50% stipple desktop */
  background: repeating-conic-gradient(#000 0% 25%, #7f7f7f 0% 50%) 0 0/2px 2px;
  image-rendering: pixelated;
  color: #000;
}

/* menu bar */
#menubar {
  position: sticky; top: 0; z-index: 10;
  display: flex; gap: 0; height: 26px;
  background: #fff; border-bottom: 2px solid #000;
  padding: 0 8px; align-items: stretch;
}
.menu { position: relative; }
.menu-title { display: flex; align-items: center; padding: 0 12px; height: 100%; font-size: 16px; }
.menu.open .menu-title, .menu-title:hover { background: #000; color: #fff; }
.menu-items {
  display: none; position: absolute; left: 0; top: 100%;
  background: #fff; border: 1px solid #000; box-shadow: 2px 2px 0 #000;
  min-width: 190px; padding: 2px 0;
}
.menu.open .menu-items { display: block; }
.menu-items button {
  display: block; width: 100%; text-align: left;
  font: inherit; font-size: 15px; background: none; border: 0; padding: 3px 14px;
}
.menu-items button:hover { background: #000; color: #fff; }

/* windows */
#desktop { display: flex; gap: 24px; padding: 40px; justify-content: center; align-items: flex-start; flex-wrap: wrap; }
.window { background: #fff; border: 2px solid #000; box-shadow: 2px 2px 0 #000; }
.title-bar {
  position: relative; height: 22px; border-bottom: 2px solid #000;
  background: repeating-linear-gradient(#fff 0 2px, #000 2px 3px) content-box;
  padding: 3px 6px; display: flex; align-items: center;
}
.title-bar .title {
  margin: 0 auto; font-size: 15px; font-weight: normal;
  background: #fff; padding: 0 10px; line-height: 16px;
}
.close-box {
  position: absolute; left: 8px; top: 4px; width: 13px; height: 13px;
  border: 1px solid #000; background: #fff;
}
.title-bar.mini { height: 14px; }

#main-window { width: min(560px, 92vw); }
#sonnet { padding: 18px 26px; font-size: 17px; line-height: 1.55; }
.line { min-height: 1.55em; padding: 0 6px; cursor: pointer; white-space: pre-wrap; }
.line:hover { outline: 1px dotted #000; }
.line.frozen { background: #000; color: #fff; }
.line.blank { cursor: default; }
.line.blank:hover { outline: none; }

/* palette */
.palette { display: flex; flex-direction: column; width: 56px; }
.palette button { background: #fff; border: 0; border-bottom: 1px solid #000; padding: 6px; cursor: pointer; }
.palette button:last-child { border-bottom: 0; }
.palette button:active { filter: invert(1); }
.palette img { width: 32px; height: 32px; image-rendering: pixelated; display: block; margin: 0 auto; }

/* dialogs */
dialog.modal { border: 2px solid #000; box-shadow: 2px 2px 0 #000; padding: 18px; max-width: 640px; }
dialog.modal::backdrop { background: rgba(0,0,0,.25); }
.about-flex { display: flex; gap: 18px; align-items: flex-start; }
.about-flex img { image-rendering: pixelated; }
.credits-viewport { height: 200px; overflow: hidden; position: relative; width: 300px; }
.credits { position: absolute; animation: scroll-credits 30s linear infinite; font-size: 14px; }
@keyframes scroll-credits { from { top: 100%; } to { top: -350%; } }
.help-caption { font-size: 13px; max-width: 550px; }
dialog img { max-width: 100%; height: auto; }
button.ok {
  font: inherit; font-size: 15px; background: #fff; color: #000;
  border: 2px solid #000; border-radius: 8px; padding: 4px 26px; margin-top: 12px;
  box-shadow: 0 0 0 2px #fff, 0 0 0 3px #000; cursor: pointer;
}
button.ok:active { background: #000; color: #fff; }

@media (max-width: 700px) {
  #desktop { padding: 16px; gap: 12px; }
  .palette { flex-direction: row; width: auto; }
  .palette button { border-bottom: 0; border-right: 1px solid #000; }
}
```

- [ ] **Step 5: Visual check**

Run: `cd web/public && python3 -m http.server 8123` and screenshot `http://localhost:8123` via the Chrome MCP (page will show empty window until Task 4 — chrome should render menu bar, stipple, window chrome, palette icons).

- [ ] **Step 6: Commit**

```bash
git add web/public/index.html web/public/style.css web/public/assets web/public/fonts
git commit -m "feat(web): System 7 shell — window chrome, menu bar, palette, 1989 assets"
```

---

### Task 4: App wiring (`app.js`)

**Files:**
- Create: `web/public/app.js`

**Interfaces:**
- Consumes: Task 1's `Engine`, `mulberry32`, `lineText`, `sonnetText`; Task 3's DOM ids.

- [ ] **Step 1: Write `web/public/app.js`**

```js
import { Engine, mulberry32, lineText, sonnetText } from "./engine.js";

const $ = (sel) => document.querySelector(sel);

async function boot() {
  let lexicon;
  try {
    const res = await fetch("lexicon.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    lexicon = await res.json();
  } catch (err) {
    $("#sonnet").textContent = `The wordlist could not be loaded (${err.message}). Reload to try again.`;
    return;
  }

  const params = new URLSearchParams(location.search);
  const seedParam = params.get("seed");
  const seed = seedParam !== null ? Number(seedParam) >>> 0
                                  : crypto.getRandomValues(new Uint32Array(1))[0];
  const engine = new Engine(lexicon, mulberry32(seed));
  let sonnet = engine.newSonnet();

  const sonnetEl = $("#sonnet");
  const tpl = $("#line-tpl");

  function render() {
    sonnetEl.replaceChildren();
    for (const line of sonnet.lines) {
      const el = tpl.content.firstElementChild.cloneNode(true);
      if (line.letter === null) {
        el.classList.add("blank");
        el.textContent = " ";
      } else {
        el.textContent = lineText(line);
        el.classList.toggle("frozen", line.frozen);
        const toggle = () => {
          line.frozen = !line.frozen;
          el.classList.toggle("frozen", line.frozen);
        };
        el.addEventListener("click", toggle);
        el.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
        });
      }
      sonnetEl.appendChild(el);
    }
  }

  function newSonnet() {
    sonnet = engine.newSonnet();
    render();
  }
  function rewrite() {
    engine.rewrite(sonnet);
    render();
  }
  function save() {
    const blob = new Blob([sonnetText(sonnet) + "\n"], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "sonnet.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(sonnetText(sonnet));
    } catch {
      const range = document.createRange();
      range.selectNodeContents(sonnetEl);
      const sel = getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }
  }

  // menus
  for (const menu of document.querySelectorAll(".menu")) {
    menu.querySelector(".menu-title").addEventListener("click", (e) => {
      e.stopPropagation();
      const wasOpen = menu.classList.contains("open");
      document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open"));
      if (!wasOpen) menu.classList.add("open");
    });
  }
  document.addEventListener("click", () =>
    document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open")));

  $("#mi-new").addEventListener("click", newSonnet);
  $("#mi-save").addEventListener("click", save);
  $("#mi-copy").addEventListener("click", copy);
  $("#mi-about").addEventListener("click", () => $("#about-dialog").showModal());
  $("#mi-help").addEventListener("click", () => $("#help-dialog").showModal());
  $("#pal-rewrite").addEventListener("click", rewrite);
  $("#pal-save").addEventListener("click", save);
  $("#pal-copy").addEventListener("click", copy);
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "n") { e.preventDefault(); newSonnet(); }
    if (e.key === "r" && !e.metaKey && !e.ctrlKey && e.target === document.body) rewrite();
  });

  render();
}

boot();
```

- [ ] **Step 2: Manual test locally**

Run: `web/build.sh && cd web/public && python3 -m http.server 8123`
In Chrome (MCP): load `http://localhost:8123?seed=1989`, verify a sonnet renders; click line 1 (inverts); click palette quill (all lines except line 1 change); File → Save downloads `sonnet.txt`; Edit → Copy fills clipboard;  → About shows portrait + scrolling credits; Help shows the 1989 PICT.

- [ ] **Step 3: Commit**

```bash
git add web/public/app.js
git commit -m "feat(web): interactions — freeze, rewrite, save, copy, menus, dialogs"
```

---

### Task 5: Deploy to toaster.nelson.love and smoke-test

**Files:**
- Modify: `README.md` (add live URL)

- [ ] **Step 1: Run tests + build, then deploy**

```bash
cd ~/repos/shakespeare-in-a-toaster
node --test web/test/ && web/build.sh
cd web && npx wrangler@4 deploy
```

Expected: upload of ~12 assets, route bound to `toaster.nelson.love` (custom domain creates DNS automatically; requires the nelson.love zone in the account — if wrangler errors "zone not found", stop and confirm with Nelson).

- [ ] **Step 2: Live smoke test**

Via Chrome MCP on `https://toaster.nelson.love?seed=1989`: sonnet renders in Chicago-style type; click-to-freeze inverts; Rewrite preserves frozen; About/Help open; favicon is the toaster head. Screenshot for the record.

- [ ] **Step 3: Update README + vault, commit, push**

Add under the install section of `README.md`:

```markdown
Or just visit **[toaster.nelson.love](https://toaster.nelson.love)** — the
same engine ported to JavaScript, wearing its original System 7 clothes.
```

```bash
git add README.md
git commit -m "docs: link the live web version"
git push
```

Update vault: project note "The port" section gains the live URL; task note gains a line. (Vault edits are outside the repo — do them with the usual tools.)

---

## Self-Review

- **Spec coverage**: engine port ✓ (T1), build/lexicon single-source ✓ (T2), System 7 UI + menus + palette + About/Help + font + favicon ✓ (T3/T4), freeze/rewrite/copy/save ✓ (T4), seed param ✓ (T4), deploy + custom domain + smoke test ✓ (T5), error handling (lexicon fetch, clipboard fallback, restart cap) ✓ (T1/T4).
- **Placeholders**: none — all code inline.
- **Type consistency**: `Engine`, `mulberry32`, `lineText`, `sonnetText`, DOM ids match between T1/T3/T4.
