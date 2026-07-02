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
