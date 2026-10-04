// improv: the chart parser and transposition. Pure: no browser, runs under Node in the
// tests. The grammar is written down in docs/improv/api.md ("Chart grammar"), because
// the editor, the library and the recognizer all share it.
//
// parseChart(text, qualities, options) returns either
//   { ok: true, bars, writtenCount, beatsPerBar, homeKey }  or
//   { ok: false, error: { message, line, column, bar } }
// and never a partial timeline. `bars` is in playing order, repeats and endings
// expanded; each bar knows which written bar it came from, so the screen can light
// the right place in the text.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovChart = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];
  const NATURAL_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const MAX_PLAYED_BARS = 2000;
  const MAX_BEATS_PER_BAR = 12;
  // Keys written without an accidental that are spelled with flats.
  const FLAT_MAJOR = new Set(["F"]);
  const FLAT_MINOR = new Set(["D", "G", "C", "F"]);

  // ---------------------------------------------------------------------- notes

  function notePc(text) {
    const m = /^([A-G])([#b]?)$/.exec(text);
    if (!m) return null;
    return (NATURAL_PC[m[1]] + (m[2] === "#" ? 1 : m[2] === "b" ? -1 : 0) + 12) % 12;
  }

  function parseKey(text) {
    if (typeof text !== "string") return null;
    const m = /^([A-G][#b]?)(m|min|-)?$/.exec(text);
    if (!m) return null;
    const minor = Boolean(m[2]);
    return { pc: notePc(m[1]), minor, name: m[1] + (minor ? "m" : "") };
  }

  function prefersFlats(key) {
    if (key.name[1] === "b") return true;
    if (key.name[1] === "#") return false;
    return key.minor ? FLAT_MINOR.has(key.name[0]) : FLAT_MAJOR.has(key.name[0]);
  }

  function chordName(rootName, quality, bassName) {
    return rootName + (quality === "maj" ? "" : quality) + (bassName ? "/" + bassName : "");
  }

  // ----------------------------------------------------------------- vocabulary

  function vocabulary(qualities) {
    const map = new Map();
    for (const q of qualities) map.set(q.symbol, q.symbol);
    for (const q of qualities) for (const alias of q.aliases || []) if (!map.has(alias)) map.set(alias, q.symbol);
    if (map.has("maj")) map.set("", "maj");
    return map;
  }

  // -------------------------------------------------------------------- reading

  function tokenize(text) {
    const tokens = [];
    let i = 0;
    let line = 1;
    let col = 1;
    const advance = () => {
      if (text[i] === "\n") {
        line++;
        col = 1;
      } else col++;
      i++;
    };
    const at = (offset) => text[i + offset];
    while (i < text.length) {
      const ch = text[i];
      if (ch === "\n" || ch === "\r" || ch === " " || ch === "\t" || ch === "﻿") {
        advance();
        continue;
      }
      if (ch === "/" && at(1) === "/") {
        while (i < text.length && text[i] !== "\n") advance();
        continue;
      }
      const start = { line, col };
      if (ch === "|") {
        advance();
        if (text[i] === "|") {
          advance();
          tokens.push({ kind: "bar", text: "||", ...start });
        } else if (text[i] === ":") {
          advance();
          tokens.push({ kind: "open", text: "|:", ...start });
        } else tokens.push({ kind: "bar", text: "|", ...start });
      } else if (ch === ":") {
        advance();
        if (text[i] === "|") {
          advance();
          if (text[i] === ":") {
            advance();
            tokens.push({ kind: "closeopen", text: ":|:", ...start });
          } else tokens.push({ kind: "close", text: ":|", ...start });
        } else tokens.push({ kind: "stray", text: ":", ...start });
      } else if (ch === "[") {
        advance();
        let digits = "";
        while (i < text.length && /[0-9]/.test(text[i])) {
          digits += text[i];
          advance();
        }
        tokens.push({ kind: "ending", text: "[" + digits, n: digits ? parseInt(digits, 10) : null, ...start });
      } else if (ch === "]") {
        advance();
        tokens.push({ kind: "endclose", text: "]", ...start });
      } else if (ch === "{") {
        let body = "";
        advance();
        while (i < text.length && text[i] !== "}" && text[i] !== "\n" && text[i] !== "\r") {
          body += text[i];
          advance();
        }
        const closed = text[i] === "}";
        if (closed) advance();
        tokens.push({ kind: "marker", text: "{" + body + (closed ? "}" : ""), body: body.trim(), closed, ...start });
      } else {
        let word = "";
        while (i < text.length && !/[\s|\[\]{}:]/.test(text[i])) {
          word += text[i];
          advance();
        }
        tokens.push({ kind: "word", text: word, ...start });
      }
    }
    return tokens;
  }

  function fail(message, token, bar) {
    return { ok: false, error: { message, line: token ? token.line : 1, column: token ? token.col : 1, bar } };
  }

  class ChartError extends Error {
    constructor(message, token, bar) {
      super(message);
      this.info = fail(message, token, bar);
    }
  }

  function readChord(token, vocab) {
    const slash = token.text.indexOf("/");
    const head = slash === -1 ? token.text : token.text.slice(0, slash);
    const bassText = slash === -1 ? null : token.text.slice(slash + 1);
    const letter = head[0];
    if (!letter || !(letter in NATURAL_PC)) return { error: `Unknown chord "${token.text}": it does not start with a note name from A to G` };
    const accidental = head[1] === "#" || head[1] === "b" ? head[1] : "";
    const rootText = letter + accidental;
    const qualityText = head.slice(rootText.length);
    const quality = vocab.get(qualityText);
    if (quality === undefined) return { error: `Unknown chord "${token.text}": "${qualityText}" is not a chord quality I know` };
    let bass = null;
    if (bassText !== null) {
      bass = notePc(bassText);
      if (bass === null) return { error: `Unknown bass note "${bassText}" in "${token.text}"` };
    }
    return {
      chord: {
        typed: token.text,
        name: chordName(rootText, quality, bassText),
        rootName: rootText,
        bassName: bassText,
        root: notePc(rootText),
        quality,
        bass,
      },
    };
  }

  // ---------------------------------------------------------------------- parse

  function parseChart(text, qualities, options) {
    const opts = options || {};
    const beatsPerBar = opts.beatsPerBar === undefined ? 4 : opts.beatsPerBar;
    if (!Number.isInteger(beatsPerBar) || beatsPerBar < 1 || beatsPerBar > MAX_BEATS_PER_BAR) {
      return fail(`Beats per bar must be a whole number from 1 to ${MAX_BEATS_PER_BAR}`, null, 0);
    }
    let homeKey = null;
    if (opts.homeKey !== undefined && opts.homeKey !== null) {
      homeKey = parseKey(opts.homeKey);
      if (!homeKey) return fail(`The home key "${opts.homeKey}" is not a key (examples: C, Eb, F#m)`, null, 0);
    }
    try {
      return build(typeof text === "string" ? text : "", vocabulary(qualities), beatsPerBar, homeKey);
    } catch (e) {
      if (e instanceof ChartError) return e.info;
      throw e;
    }
  }

  function build(text, vocab, beatsPerBar, homeKey) {
    const tokens = tokenize(text);
    const written = [];
    const items = [];
    let key = homeKey;
    let pending = null; // { first, words: [{token, chord}], percent }
    let rep = null;
    let mode = "top"; // top | body | ending | awaiting
    let openMark = null;
    let endingMark = null;
    let prevToken = null;

    const barNo = () => written.length + 1;
    const err = (message, token, bar) => {
      throw new ChartError(message, token, bar === undefined ? barNo() : bar);
    };

    function place(idx) {
      if (mode === "awaiting") finalize(true);
      if (mode === "top") items.push(idx);
      else if (mode === "body") rep.body.push(idx);
      else rep.endings[rep.endings.length - 1].push(idx);
    }

    function finalize(implicitLast) {
      rep.implicitLast = Boolean(implicitLast);
      items.push(rep);
      rep = null;
      mode = "top";
    }

    function flush() {
      if (!pending) return;
      const first = pending.first;
      let chords;
      if (pending.percent) {
        const before = written[written.length - 1];
        chords = before.chords.map((c) => ({ ...c }));
      } else {
        const n = pending.words.length;
        if (n > beatsPerBar) err(`${n} chords do not fit in ${beatsPerBar} beats`, first);
        const length = beatsPerBar / n;
        chords = pending.words.map((w, i) => ({ ...w.chord, beat: i * length, beats: length }));
      }
      written.push({ chords, line: first.line, col: first.col, key });
      place(written.length - 1);
      pending = null;
    }

    for (const token of tokens) {
      switch (token.kind) {
        case "word": {
          if (token.text === "%") {
            if (pending) err("A % has to be alone in its bar", token);
            if (!written.length) err("The % in bar 1 has no bar before it to repeat", token);
            pending = { first: token, words: [], percent: true };
            break;
          }
          if (pending && pending.percent) err("A % has to be alone in its bar", token);
          const read = readChord(token, vocab);
          if (read.error) err(read.error, token);
          if (!pending) pending = { first: token, words: [], percent: false };
          pending.words.push({ token, chord: read.chord });
          break;
        }
        case "bar":
          if (!pending && prevToken && (prevToken.kind === "bar" || prevToken.kind === "open" || prevToken.kind === "ending")) {
            // A bar line that starts a new line right after one that ended the line before is one bar line.
            if (prevToken.line === token.line) err(`Bar ${barNo()} is empty (use % to repeat the last bar)`, token);
          }
          flush();
          break;
        case "open":
        case "closeopen":
        case "close": {
          flush();
          if (token.kind !== "open") closeRepeat(token);
          if (token.kind !== "close") openRepeat(token);
          break;
        }
        case "ending":
          flush();
          openEnding(token);
          break;
        case "endclose":
          flush();
          if (mode === "ending") {
            if (rep.endings.length < 2) err(`Ending [1 needs a repeat sign :| at its end`, endingMark, endingMark.bar);
            finalize(false);
          }
          break;
        case "marker": {
          if (pending) err("A key change has to sit between bars, not inside one", token);
          if (!token.closed) err(`The { in "${token.text}" is never closed with }`, token);
          const m = /^key\s*:\s*(\S+)$/i.exec(token.body);
          if (!m) err(`Unknown marker "${token.text}". The one marker is {key: Eb}`, token);
          const parsed = parseKey(m[1]);
          if (!parsed) err(`Unknown key "${m[1]}" in ${token.text} (examples: C, Eb, F#m)`, token);
          key = parsed;
          break;
        }
        default:
          err(`Unexpected "${token.text}"`, token);
      }
      prevToken = token;
    }
    flush();

    function openRepeat(token) {
      if (mode === "body") err("A repeat opened with |: is not closed with :| before the next |:", token);
      if (mode === "ending") {
        if (rep.endings.length < 2) err("Ending [1 needs a repeat sign :| at its end", endingMark, endingMark.bar);
        finalize(false);
      } else if (mode === "awaiting") finalize(true);
      rep = { body: [], endings: [], implicitLast: false };
      mode = "body";
      openMark = { line: token.line, col: token.col, bar: barNo() };
    }

    function closeRepeat(token) {
      if (mode === "top") {
        let from = items.length;
        while (from > 0 && typeof items[from - 1] === "number") from--;
        const body = items.splice(from);
        if (!body.length) err("A repeat sign :| has no bars before it to repeat", token);
        items.push({ body, endings: [], implicitLast: false });
      } else if (mode === "body") {
        if (!rep.body.length) err("This repeat has no bars in it", { line: openMark.line, col: openMark.col }, openMark.bar);
        finalize(false);
      } else if (mode === "ending") {
        if (!rep.endings[rep.endings.length - 1].length) err(`Ending [${rep.endings.length} has no bars in it`, endingMark, endingMark.bar);
        mode = "awaiting";
      } else err("This repeat sign :| has no matching |: before it", token);
    }

    function openEnding(token) {
      if (token.n === null) err("An ending marker needs a number, like [1", token);
      if (token.n < 1) err("Ending numbers start at 1", token);
      if (mode === "top") err(`Ending [${token.n} has no repeat (|:) before it`, token);
      if (mode === "ending") {
        err(`Ending [${rep.endings.length} is not closed by a repeat sign :| before ending [${token.n}`, endingMark, endingMark.bar);
      }
      if (mode === "body") {
        if (token.n !== 1) err(`The first ending is [1, not [${token.n}`, token);
        if (!rep.body.length) err("This repeat has no bars before its first ending", token);
      } else if (token.n !== rep.endings.length + 1) {
        err(`Endings have to come in order: expected [${rep.endings.length + 1}, found [${token.n}`, token);
      }
      rep.endings.push([]);
      mode = "ending";
      endingMark = { line: token.line, col: token.col, bar: barNo() };
    }

    if (mode === "body") err("The repeat opened with |: is never closed with :|", { line: openMark.line, col: openMark.col }, openMark.bar);
    if (mode === "ending") {
      if (rep.endings.length < 2) err("Ending [1 needs a repeat sign :| at its end", endingMark, endingMark.bar);
      finalize(false);
    } else if (mode === "awaiting") finalize(true);

    if (!written.length) err("The chart is empty: write bars between | signs, like | Dm7 | G7 | Cmaj7 |", { line: 1, col: 1 }, 0);

    const bars = [];
    function emit(idx, pass) {
      if (bars.length >= MAX_PLAYED_BARS) {
        err(`The chart is too long: it plays more than ${MAX_PLAYED_BARS} bars once repeats are counted`, { line: 1, col: 1 }, 0);
      }
      const w = written[idx];
      bars.push({
        n: bars.length,
        written: idx,
        line: w.line,
        col: w.col,
        pass,
        beats: beatsPerBar,
        key: w.key ? { ...w.key } : null,
        chords: w.chords.map((c) => ({ ...c })),
      });
    }
    for (const item of items) {
      if (typeof item === "number") {
        emit(item, 1);
        continue;
      }
      const passes = item.endings.length ? item.endings.length + (item.implicitLast ? 1 : 0) : 2;
      for (let pass = 1; pass <= passes; pass++) {
        for (const idx of item.body) emit(idx, pass);
        if (item.endings.length && pass <= item.endings.length) for (const idx of item.endings[pass - 1]) emit(idx, pass);
      }
    }
    return { ok: true, bars, writtenCount: written.length, beatsPerBar, homeKey };
  }

  // -------------------------------------------------------------- transposition

  // How far the chart moves to go from one key to another, as the shorter way round
  // (-5 to +6). Only the tonic counts, so C to Am is -3.
  function semitonesBetween(from, to) {
    const a = parseKey(from);
    const b = parseKey(to);
    if (!a) throw new Error(`"${from}" is not a key`);
    if (!b) throw new Error(`"${to}" is not a key`);
    const d = (((b.pc - a.pc) % 12) + 12) % 12;
    return d > 6 ? d - 12 : d;
  }

  // The same chart in another key. Computed at play time and never stored. Returns a
  // new chart; the one passed in is not changed.
  function transposeToKey(parsed, fromKey, toKey) {
    if (!parsed || !parsed.ok) throw new Error("Only a chart that parsed can be transposed");
    const target = parseKey(toKey);
    const shift = semitonesBetween(fromKey, toKey);
    const names = prefersFlats(target) ? FLAT_NAMES : SHARP_NAMES;
    const mod = (n) => (((n % 12) + 12) % 12);
    const bars = parsed.bars.map((bar) => ({
      ...bar,
      key: bar.key ? { pc: mod(bar.key.pc + shift), minor: bar.key.minor, name: names[mod(bar.key.pc + shift)] + (bar.key.minor ? "m" : "") } : null,
      chords: bar.chords.map((c) => {
        const root = mod(c.root + shift);
        const bass = c.bass === null ? null : mod(c.bass + shift);
        const rootName = names[root];
        const bassName = bass === null ? null : names[bass];
        return { ...c, root, bass, rootName, bassName, name: chordName(rootName, c.quality, bassName) };
      }),
    }));
    return { ...parsed, bars, homeKey: target, transposedBy: shift };
  }

  return { parseChart, parseKey, transposeToKey, semitonesBetween, chordName, SHARP_NAMES, FLAT_NAMES, MAX_PLAYED_BARS };
});
