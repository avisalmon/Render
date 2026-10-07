// improv: the chord trainer's chords, positions, matcher and order of prompts. Pure: no browser, no
// clock, runs under Node in the tests. A chord is asked in a position: first is the root in the bass,
// second the first inversion and so on. An answer is right when the notes held are exactly the chord's
// pitch classes, in any octave and either hand, and the lowest note held is the bass of that position.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./scale.js"));
  else root.ImprovDrill = factory(root.ImprovScale);
})(typeof self !== "undefined" ? self : this, function (Scale) {
  const CIRCLE = Scale.CIRCLE;
  const LETTERS = ["C", "D", "E", "F", "G", "A", "B"];
  const LETTER_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];
  const DISPLAY = { from: 48, to: 72 };
  const KIND = "chord_position";

  const SHAPES = {
    maj: [0, 4, 7], m: [0, 3, 7], dim: [0, 3, 6],
    maj7: [0, 4, 7, 11], m7: [0, 3, 7, 10], 7: [0, 4, 7, 10], m7b5: [0, 3, 6, 10],
  };
  const TRIADS = ["maj", "m", "m", "maj", "maj", "m", "dim"];
  const SEVENTHS = ["maj7", "m7", "m7", "maj7", "7", "m7", "m7b5"];
  const ROMAN = ["I", "ii", "iii", "IV", "V", "vi", "vii°"];
  const ORDINAL = ["", "first", "second", "third", "fourth"];
  const INVERSION = ["root position", "first inversion", "second inversion", "third inversion"];

  function keyName(pc, spelling) {
    return Scale.keyName(pc, spelling);
  }

  function pcName(pc, spelling) {
    return (spelling === "flats" ? FLAT_NAMES : SHARP_NAMES)[((pc % 12) + 12) % 12];
  }

  // Each tone takes the next letter but one, so a seventh is a Bb and never an A#.
  function spell(rootName, rootPc, intervals) {
    const first = LETTERS.indexOf(rootName[0]);
    return intervals.map((interval, i) => {
      const letter = LETTERS[(first + 2 * i) % 7];
      const target = (rootPc + interval) % 12;
      const drift = ((((target - LETTER_PC[letter]) % 12) + 18) % 12) - 6;
      return letter + (drift === 1 ? "#" : drift === -1 ? "b" : "");
    });
  }

  function makeChord(pc, spelling, degree, symbol, kind, notes) {
    const rootName = notes[degree - 1];
    const rootPc = Scale.MAJOR[degree - 1] + pc;
    const intervals = SHAPES[symbol].slice();
    const rootMod = rootPc % 12;
    const pcs = intervals.map((i) => (rootMod + i) % 12).sort((a, b) => a - b);
    const shown = symbol === "maj" ? "" : symbol;
    return {
      id: `${kind === "borrowed" ? "b" : "d"}${degree}`,
      kind,
      degree,
      roman: kind === "borrowed" ? `${ROMAN[degree - 1]}7` : ROMAN[degree - 1],
      symbol,
      name: rootName + shown,
      rootName,
      rootPc: rootMod,
      intervals,
      pcs,
      tones: spell(rootName, rootMod, intervals),
    };
  }

  // The chords of a key at a level: 1 triads, 2 sevenths, 3 sevenths plus the borrowed I7 and IV7.
  function pool(pc, level, spelling) {
    if (![1, 2, 3].includes(level)) throw new Error(`There is no level ${level}.`);
    const notes = Scale.scaleNotes(pc, spelling);
    const shapes = level === 1 ? TRIADS : SEVENTHS;
    const chords = shapes.map((symbol, i) => makeChord(pc, spelling, i + 1, symbol, "diatonic", notes));
    if (level === 3) {
      chords.push(makeChord(pc, spelling, 1, "7", "borrowed", notes));
      chords.push(makeChord(pc, spelling, 4, "7", "borrowed", notes));
    }
    return chords;
  }

  function positionCount(chord) {
    return chord.intervals.length;
  }

  function makePrompt(pc, level, chord, position, spelling) {
    const count = positionCount(chord);
    if (!Number.isInteger(position) || position < 1 || position > count) {
      throw new Error(`${chord.name} has no position ${position}.`);
    }
    const bassName = chord.tones[position - 1];
    const bassPc = (chord.rootPc + chord.intervals[position - 1]) % 12;
    return {
      id: `${pc}-${chord.id}-${position}`,
      chordId: chord.id,
      key_pc: pc,
      key: keyName(pc, spelling),
      spelling: spelling === "flats" ? "flats" : "sharps",
      level,
      degree: chord.degree,
      roman: chord.roman,
      kind: chord.kind,
      symbol: chord.symbol,
      name: chord.name,
      rootPc: chord.rootPc,
      pcs: chord.pcs.slice(),
      tones: chord.tones.slice(),
      intervals: chord.intervals.slice(),
      position,
      positionCount: count,
      bassPc,
      bassName,
      title: `${chord.name}, ${ORDINAL[position]} position`,
      inversion: INVERSION[position - 1],
      detail: `${INVERSION[position - 1]}, ${bassName} in the bass`,
      slash: position === 1 ? chord.name : `${chord.name}/${bassName}`,
    };
  }

  // The chord as a closed voicing for the keyboard: the bass lowest, every other tone the next one up.
  function voicing(prompt) {
    const order = [];
    for (let i = 0; i < prompt.intervals.length; i++) {
      order.push((prompt.rootPc + prompt.intervals[(prompt.position - 1 + i) % prompt.intervals.length]) % 12);
    }
    const notes = [DISPLAY.from + ((order[0] - DISPLAY.from) % 12 + 12) % 12];
    for (let i = 1; i < order.length; i++) {
      const prev = notes[i - 1];
      notes.push(prev + ((order[i] - prev) % 12 + 12) % 12);
    }
    return notes;
  }

  // held: the midi notes now down. Wrong at once when a note is outside the chord; incomplete while
  // notes are still missing; with all of them, right only when the lowest is the expected bass.
  function judgeHeld(prompt, held) {
    const pcs = new Set(held.map((n) => ((n % 12) + 12) % 12));
    const extra = [...pcs].filter((p) => !prompt.pcs.includes(p)).sort((a, b) => a - b);
    if (extra.length) return { state: "wrong", reason: "extra", extra, missing: [] };
    const missing = prompt.pcs.filter((p) => !pcs.has(p));
    if (missing.length) return { state: "incomplete", reason: "missing", extra: [], missing };
    const lowest = Math.min(...held);
    if (((lowest % 12) + 12) % 12 !== prompt.bassPc) return { state: "wrong", reason: "bass", extra: [], missing: [] };
    return { state: "right", reason: "", extra: [], missing: [] };
  }

  function shuffle(items, rng) {
    const out = items.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }

  function allPrompts(pc, level, spelling) {
    const out = [];
    for (const chord of pool(pc, level, spelling)) {
      for (let p = 1; p <= positionCount(chord); p++) out.push(makePrompt(pc, level, chord, p, spelling));
    }
    return out;
  }

  function noRepeat(prompts) {
    return prompts.every((p, i) => i === 0 || p.chordId !== prompts[i - 1].chordId);
  }

  // Picks at random from the chords that differ from the last, always taking the chord with the most
  // left when it is the only way to keep the rest apart.
  function spread(prompts, rng) {
    const left = prompts.slice();
    const out = [];
    while (left.length) {
      const last = out.length ? out[out.length - 1].chordId : null;
      const counts = {};
      left.forEach((p) => { counts[p.chordId] = (counts[p.chordId] || 0) + 1; });
      let candidates = left.filter((p) => p.chordId !== last);
      const must = Object.keys(counts).find((id) => id !== last && counts[id] * 2 > left.length);
      if (must) candidates = candidates.filter((p) => p.chordId === must);
      if (!candidates.length) candidates = left;
      const pick = candidates[Math.floor(rng() * candidates.length)];
      left.splice(left.indexOf(pick), 1);
      out.push(pick);
    }
    return out;
  }

  function makeDrill(pc, level, spelling, rng) {
    const random = rng || Math.random;
    const shuffled = shuffle(allPrompts(pc, level, spelling), random);
    const spreadOut = spread(shuffled, random);
    return noRepeat(spreadOut) ? spreadOut : shuffled;
  }

  function makeCircle(level, spelling, rng) {
    const random = rng || Math.random;
    const out = [];
    for (const pc of CIRCLE) {
      const chords = shuffle(pool(pc, level, spelling), random);
      for (const chord of chords) {
        const position = 1 + Math.floor(random() * positionCount(chord));
        out.push(makePrompt(pc, level, chord, position, spelling));
      }
    }
    return out;
  }

  function learnList(pc, level, spelling) {
    return pool(pc, level, spelling).map((chord) => {
      const prompts = [];
      for (let p = 1; p <= positionCount(chord); p++) prompts.push(makePrompt(pc, level, chord, p, spelling));
      return { chord, prompts };
    });
  }

  function toAttempt(prompt, outcome) {
    const skipped = Boolean(outcome.skipped);
    const wrongTries = outcome.wrongTries || 0;
    return {
      kind: KIND,
      key_pc: prompt.key_pc,
      level: prompt.level,
      prompt,
      answer: { notes: outcome.notes || [], called: outcome.called || "" },
      is_correct: !skipped && wrongTries === 0,
      wrong_tries: wrongTries,
      hint_used: Boolean(outcome.hintUsed),
      skipped,
      response_ms: skipped || outcome.responseMs == null ? null : Math.round(outcome.responseMs),
    };
  }

  function seconds(ms) {
    if (ms == null) return "no time";
    return `${(ms / 1000).toFixed(1)} s`;
  }

  function wrongWords(prompt, result, called) {
    const heard = called ? `That was ${called}. ` : "";
    if (result.reason === "bass") {
      return `${heard}The right notes, but the lowest note should be ${prompt.bassName}.`;
    }
    const names = (result.extra || []).map((p) => pcName(p, prompt.spelling));
    if (!names.length) return `${heard}That is not this chord.`.trim();
    const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
    return `${heard}${list} ${names.length === 1 ? "is" : "are"} not in this chord.`;
  }

  return {
    CIRCLE, KIND, DISPLAY, SHAPES, keyName, pcName, spell, pool, positionCount, makePrompt, voicing,
    judgeHeld, makeDrill, makeCircle, learnList, toAttempt, seconds, wrongWords,
  };
});
