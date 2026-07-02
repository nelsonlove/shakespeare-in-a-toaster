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
