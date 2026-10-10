// improv: the note-reading trainer's rules. Pure: no browser, no clock, runs under Node in the tests.
//
// A stage is a key and a hand: right hand first, then the left, then both, in C, then on through the keys.
// An exercise is four bars for two hands generated from a seed, never a stored piece, so it can only be
// read; the stage says which hand is judged, and the same seed gives the same piece whichever hand, so the
// piece practised one hand at a time is the piece played with both (Avi, 2026-10-10). The judge
// takes the notes played, in milliseconds from the first beat, and says for every written note whether it
// came, how far from its time, and what was played instead; the live display and the final score come
// from this one function. Step mode is a small state machine that waits for the right note. JUDGE_VERSION
// is saved with every take so old scores stay explainable when these rules change.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovReading = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const LETTERS = ["C", "D", "E", "F", "G", "A", "B"];
  const LETTER_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"];
  const FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"];
  // The keys in the order they are met: C, then alternating sharps and flats, so the hand meets one
  // new accidental at a time. `acc` is the count of sharps (positive) or flats (negative).
  const KEYS = [
    { pc: 0, name: "C", acc: 0 }, { pc: 7, name: "G", acc: 1 }, { pc: 5, name: "F", acc: -1 }, { pc: 2, name: "D", acc: 2 },
    { pc: 10, name: "Bb", acc: -2 }, { pc: 9, name: "A", acc: 3 }, { pc: 3, name: "Eb", acc: -3 }, { pc: 4, name: "E", acc: 4 },
    { pc: 8, name: "Ab", acc: -4 }, { pc: 11, name: "B", acc: 5 }, { pc: 1, name: "Db", acc: -5 }, { pc: 6, name: "F#", acc: 6 },
  ];
  const HANDS = ["R", "L", "B"];
  const HAND_WORDS = { R: "right hand", L: "left hand", B: "both hands" };
  const BARS = 4;
  const BEATS = 4;
  const CONTROL_FLOOR = 106;

  const JUDGE_VERSION = 1;
  const PASS_SCORE = 80;
  const PITCH_WEIGHT = 0.7;
  const TIMING_WEIGHT = 0.3;
  const TOLERANCE_OF_BEAT = 0.3;
  const TOLERANCE_MIN_MS = 60;
  const TOLERANCE_MAX_MS = 150;
  const STEP_QUICK_MS = 1500;
  const TEMPO_MIN = 30;
  const TEMPO_MAX = 160;
  const TEMPO_DEFAULT = 72;

  // Staff positions are diatonic steps: C4 is 28 (4 * 7 + 0). The treble staff runs E4 (30) to F5 (38),
  // the bass staff G2 (18) to A3 (26).
  const TREBLE = { bottom: 30, top: 38 };
  const BASS = { bottom: 18, top: 26 };
  const RANGES = {
    R: { 1: [28, 39], 2: [26, 42], 3: [24, 44] },
    L: { 1: [14, 26], 2: [14, 26], 3: [14, 30] },
  };
  const BASS_ROOTS = { 1: [14, 18, 21, 25], 2: [14, 17, 18, 21, 24, 25], 3: [14, 16, 17, 18, 19, 21, 24, 25, 28] };
  const BASS_RHYTHMS = { 1: [[4], [4], [2, 2]], 2: [[4], [2, 2], [2, 2], [2, 1, 1]], 3: [[2, 2], [2, 1, 1], [1, 1, 2], [1, 1, 1, 1]] };

  // ------------------------------------------------------------------------- stages

  function stageCount() {
    return KEYS.length * HANDS.length;
  }

  function stageOf(index) {
    const n = stageCount();
    const i = Math.min(n - 1, Math.max(0, Math.floor(Number(index) || 0)));
    const key = KEYS[Math.floor(i / HANDS.length)];
    return { index: i, pc: key.pc, key: key.name, hands: HANDS[i % HANDS.length], difficulty: 1 + Math.floor(Math.floor(i / HANDS.length) / 4) };
  }

  function stageIndex(keyName, hands) {
    const k = KEYS.findIndex((key) => key.name === keyName);
    const h = HANDS.indexOf(hands);
    if (k < 0 || h < 0) return -1;
    return k * HANDS.length + h;
  }

  function keyInfo(keyName) {
    return KEYS.find((key) => key.name === keyName) || null;
  }

  function keyWords(keyName) {
    const key = keyInfo(keyName);
    if (!key || key.acc === 0) return "no sharps or flats";
    const n = Math.abs(key.acc);
    const names = (key.acc > 0 ? SHARP_ORDER : FLAT_ORDER).slice(0, n).map((l) => l + (key.acc > 0 ? "#" : "b"));
    const word = key.acc > 0 ? "sharp" : "flat";
    return `${n} ${word}${n === 1 ? "" : "s"} (${names.join(", ")})`;
  }

  function stageTitle(stage) {
    return `${stage.key} major, ${HAND_WORDS[stage.hands]}`;
  }

  // The alteration the key signature gives each letter: -1, 0 or 1.
  function keyAccidentals(keyName) {
    const key = keyInfo(keyName);
    const out = { C: 0, D: 0, E: 0, F: 0, G: 0, A: 0, B: 0 };
    if (!key) return out;
    const order = key.acc > 0 ? SHARP_ORDER : FLAT_ORDER;
    for (let i = 0; i < Math.abs(key.acc); i++) out[order[i]] = key.acc > 0 ? 1 : -1;
    return out;
  }

  // Where the signature's accidentals sit on each staff, as diatonic steps, in the order they are drawn.
  function signaturePositions(keyName) {
    const key = keyInfo(keyName);
    if (!key || key.acc === 0) return { treble: [], bass: [], kind: "" };
    const sharps = key.acc > 0;
    const treble = sharps ? [38, 35, 39, 36, 33, 37, 34] : [34, 37, 33, 36, 32, 35, 31];
    const bass = treble.map((s) => s - 14);
    const n = Math.abs(key.acc);
    return { treble: treble.slice(0, n), bass: bass.slice(0, n), kind: sharps ? "#" : "b" };
  }

  // ------------------------------------------------------------------------- notes

  const letterOf = (step) => LETTERS[((step % 7) + 7) % 7];
  const octaveOf = (step) => Math.floor(step / 7);

  function midiOf(step, acc) {
    return 12 * (octaveOf(step) + 1) + LETTER_PC[letterOf(step)] + acc;
  }

  // The staff step and alteration a MIDI note is written with in this key: the key's own spelling when
  // the note is in the key, else a natural, else a sharp (a flat in a flat key).
  function spell(midi, keyName) {
    const sig = keyAccidentals(keyName);
    const key = keyInfo(keyName);
    const flats = Boolean(key && key.acc < 0);
    const octave = Math.floor(midi / 12) - 1;
    const pc = ((midi % 12) + 12) % 12;
    let best = null;
    for (let i = 0; i < 7; i++) {
      const letter = LETTERS[i];
      for (const acc of [-1, 0, 1]) {
        const value = LETTER_PC[letter] + acc;
        if (((value % 12) + 12) % 12 !== pc) continue;
        const cost = acc === sig[letter] ? 0 : acc === 0 ? 1 : (acc < 0) === flats ? 2 : 3;
        if (best && cost >= best.cost) continue;
        best = { cost, step: (octave + (value >= 12 ? -1 : value < 0 ? 1 : 0)) * 7 + i, acc };
      }
    }
    return { step: best.step, acc: best.acc };
  }

  // What is drawn before the note: nothing when the key already says so, else #, b or a natural.
  function shownAccidental(step, acc, keyName) {
    const inKey = keyAccidentals(keyName)[letterOf(step)];
    if (acc === inKey) return "";
    return acc === 1 ? "#" : acc === -1 ? "b" : "n";
  }

  function noteName(midi, spelling) {
    const sharps = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
    const flats = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];
    return (spelling === "flats" ? flats : sharps)[midi % 12] + (Math.floor(midi / 12) - 1);
  }

  function staffOf(hand) {
    return hand === "R" ? TREBLE : BASS;
  }

  // The part of the staff a note sits in, for the weak-spot map.
  function zoneOf(hand, step) {
    const staff = staffOf(hand);
    const name = hand === "R" ? "treble" : "bass";
    if (step < staff.bottom) return `${name}-below`;
    if (step > staff.top) return `${name}-above`;
    return `${name}-on`;
  }

  const ZONE_WORDS = {
    "treble-below": "Treble clef, below the staff",
    "treble-on": "Treble clef, on the staff",
    "treble-above": "Treble clef, above the staff",
    "bass-below": "Bass clef, below the staff",
    "bass-on": "Bass clef, on the staff",
    "bass-above": "Bass clef, above the staff",
  };

  function zoneWords(zone) {
    return ZONE_WORDS[zone] || zone;
  }

  // ------------------------------------------------------------------------- the generator

  function makeRandom(seed) {
    let s = (Math.floor(Number(seed)) >>> 0) || 1;
    return () => {
      s = (s * 1103515245 + 12345) >>> 0;
      return (s >>> 8) / 16777216;
    };
  }

  const pick = (rnd, list) => list[Math.floor(rnd() * list.length)];

  function rhythmFor(rnd, difficulty, lastBar) {
    if (lastBar) return pick(rnd, [[2, 2], [4], [1, 1, 2]]);
    const plain = [[1, 1, 1, 1], [2, 1, 1], [1, 1, 2], [2, 2], [1, 2, 1]];
    if (difficulty === 1) return pick(rnd, plain);
    const dotted = [[3, 1], [1, 3]];
    const eighths = [[0.5, 0.5, 1, 1, 1], [1, 0.5, 0.5, 1, 1], [1, 1, 0.5, 0.5, 1], [1, 1, 1, 0.5, 0.5], [0.5, 0.5, 1, 2], [2, 0.5, 0.5, 1]];
    if (difficulty === 2) return pick(rnd, [...plain, ...plain, ...dotted, ...eighths]);
    return pick(rnd, [...plain, ...dotted, ...eighths, ...eighths]);
  }

  // A line for one hand: a walk through the key's letters inside the hand's range. The bias leans the
  // walk toward a zone the player misreads, so the next exercise works on it.
  function melody(rnd, hand, keyName, difficulty, bias) {
    const [lo, hi] = RANGES[hand][difficulty];
    const sig = keyAccidentals(keyName);
    const zone = (bias || []).find((z) => z.startsWith(hand === "R" ? "treble" : "bass"));
    const lean = zone ? (zone.endsWith("above") ? 1 : zone.endsWith("below") ? -1 : 0) : 0;
    const tonicStep = (() => {
      const letter = keyInfo(keyName).name[0];
      const center = Math.round((lo + hi) / 2) + lean * 3;
      const i = LETTERS.indexOf(letter);
      let step = octaveOf(center) * 7 + i;
      while (step < lo) step += 7;
      while (step > hi) step -= 7;
      return step;
    })();
    let step = tonicStep;
    const moves = difficulty === 1 ? [-1, -1, 1, 1, 1, -2, 2] : difficulty === 2 ? [-1, -1, 1, 1, -2, 2, 3, -3, 4] : [-1, 1, 1, -2, 2, 3, -3, 4, -4, 5, -5];
    const notes = [];
    let chromaticDue = null;
    for (let bar = 0; bar < BARS; bar++) {
      const rhythm = rhythmFor(rnd, difficulty, bar === BARS - 1);
      let beat = 0;
      for (let i = 0; i < rhythm.length; i++) {
        const dur = rhythm[i];
        const last = bar === BARS - 1 && i === rhythm.length - 1;
        if (chromaticDue !== null) {
          step = chromaticDue;
          chromaticDue = null;
        } else if (last) {
          step = tonicStep;
        } else {
          let move = pick(rnd, moves);
          if (lean && rnd() < 0.35) move = Math.abs(move) * lean;
          let next = step + move;
          if (next < lo || next > hi) next = step - move;
          step = Math.max(lo, Math.min(hi, next));
        }
        let acc = sig[letterOf(step)];
        // A chromatic neighbour, sharpened and resolved a step up, only where the next letter is a whole step away.
        if (difficulty === 3 && !last && chromaticDue === null && dur <= 1 && step < hi && acc <= 0 && rnd() < 0.12) {
          const gap = ((midiOf(step + 1, sig[letterOf(step + 1)]) - midiOf(step, acc)) % 12 + 12) % 12;
          if (gap === 2) {
            acc += 1;
            chromaticDue = step + 1;
          }
        }
        notes.push({ hand, step, acc, midi: midiOf(step, acc), beat: bar * BEATS + beat, dur, bar });
        beat += dur;
      }
    }
    return notes;
  }

  // The left hand under the right hand's line: the key's bass notes, longer at first, moving more later.
  function accompaniment(rnd, keyName, difficulty) {
    const sig = keyAccidentals(keyName);
    const tonic = LETTERS.indexOf(keyInfo(keyName).name[0]);
    // Inside the bass staff until the third difficulty, which may reach above it.
    const top = RANGES.L[difficulty][1];
    const roots = BASS_ROOTS[difficulty].map((s) => s + tonic).map((s) => (s > top ? s - 7 : s));
    const home = Math.max(14, Math.min(28, 14 + tonic + (tonic > 4 ? 0 : 7)));
    const notes = [];
    for (let bar = 0; bar < BARS; bar++) {
      const last = bar === BARS - 1;
      const rhythm = last ? [4] : pick(rnd, BASS_RHYTHMS[difficulty]);
      let at = 0;
      for (const dur of rhythm) {
        const step = last ? home : pick(rnd, roots);
        const acc = sig[letterOf(step)];
        notes.push({ hand: "L", step, acc, midi: midiOf(step, acc), beat: bar * BEATS + at, dur, bar });
        at += dur;
      }
    }
    return notes;
  }

  // Always both hands, in the same order from the random stream, so the seed alone names the piece.
  function generate(stage, seed, bias) {
    const rnd = makeRandom(seed);
    const key = stage.key;
    const notes = [...melody(rnd, "R", key, stage.difficulty, bias), ...accompaniment(rnd, key, stage.difficulty)];
    notes.sort((a, b) => a.beat - b.beat || (a.hand === "L" ? -1 : 1) - (b.hand === "L" ? -1 : 1) || a.midi - b.midi);
    notes.forEach((n, i) => {
      n.index = i;
      n.shown = shownAccidental(n.step, n.acc, key);
    });
    return { key, hands: stage.hands, difficulty: stage.difficulty, seed: Math.floor(Number(seed)) >>> 0, bars: BARS, beats: BEATS, notes };
  }

  // Whether a note is the stage's to play: with one hand chosen, the other is shown and left alone.
  function isActive(exercise, note) {
    return exercise.hands === "B" || note.hand === exercise.hands;
  }

  function activeNotes(exercise) {
    return exercise.notes.filter((n) => isActive(exercise, n));
  }

  function keyboardRange(exercise) {
    const midis = activeNotes(exercise).map((n) => n.midi);
    const from = Math.min(...midis) - 3;
    const to = Math.max(...midis) + 3;
    return { from: from - (from % 12), to: to + (11 - ((to % 12) + 12) % 12) };
  }

  // ------------------------------------------------------------------------- the flow judge

  function toleranceMs(beatMs) {
    return Math.round(Math.min(TOLERANCE_MAX_MS, Math.max(TOLERANCE_MIN_MS, beatMs * TOLERANCE_OF_BEAT)));
  }

  function timingOf(offset, tolerance) {
    if (offset < -tolerance) return "early";
    if (offset > tolerance) return "late";
    return "ontime";
  }

  // input: { notes, tempo, events: [{t_ms, type, note}], latencyMs, now }
  function judge(input) {
    const beatMs = 60000 / input.tempo;
    const tolerance = toleranceMs(beatMs);
    const latency = input.latencyMs || 0;
    const live = input.now !== undefined && input.now !== null;
    const slots = input.notes.map((n) => ({ note: n, due: n.beat * beatMs, window: Math.min(beatMs / 2, (n.dur * beatMs) / 2), hit: null, wrong: null }));
    const presses = (input.events || [])
      .filter((e) => e.type === "on" && e.note < CONTROL_FLOOR && (!live || e.t_ms <= input.now))
      .map((e) => ({ note: e.note, t: e.t_ms - latency, used: false }))
      .sort((a, b) => a.t - b.t);

    for (const press of presses) {
      let best = null;
      for (const slot of slots) {
        if (slot.hit || slot.note.midi !== press.note) continue;
        const gap = Math.abs(press.t - slot.due);
        if (gap < slot.window && (best === null || gap < Math.abs(press.t - best.due))) best = slot;
      }
      if (best) {
        best.hit = { offsetMs: press.t - best.due };
        press.used = true;
      }
    }
    let extras = 0;
    for (const press of presses) {
      if (press.used) continue;
      let best = null;
      let bestCost = Infinity;
      for (const slot of slots) {
        if (slot.hit || slot.wrong) continue;
        const gap = Math.abs(press.t - slot.due);
        if (gap >= slot.window) continue;
        const cost = Math.abs(press.note - slot.note.midi) * 100 + gap;
        if (cost < bestCost) {
          best = slot;
          bestCost = cost;
        }
      }
      if (best && Math.abs(press.note - best.note.midi) <= 14) {
        best.wrong = { played: press.note, offsetMs: press.t - best.due };
        press.used = true;
      } else extras += 1;
    }

    const closed = (slot) => slot.hit !== null || slot.wrong !== null || !live || input.now >= slot.due + slot.window;
    const results = slots.map((slot) => {
      if (slot.hit) return { state: "right", timing: timingOf(slot.hit.offsetMs, tolerance), offset_ms: Math.round(slot.hit.offsetMs), played: null };
      if (slot.wrong) return { state: "wrong", timing: null, offset_ms: Math.round(slot.wrong.offsetMs), played: slot.wrong.played };
      return { state: closed(slot) ? "missed" : "pending", timing: null, offset_ms: null, played: null };
    });
    const counted = slots.filter(closed).length;
    const hits = slots.filter((s) => s.hit);
    const onTime = hits.filter((s) => Math.abs(s.hit.offsetMs) <= tolerance).length;
    const pitchAccuracy = counted + extras ? hits.length / (counted + extras) : 0;
    const timingAccuracy = hits.length ? onTime / hits.length : 0;
    const meanOffsetMs = hits.length ? Math.round(hits.reduce((a, s) => a + s.hit.offsetMs, 0) / hits.length) : 0;
    const score = Math.round(100 * (PITCH_WEIGHT * pitchAccuracy + TIMING_WEIGHT * timingAccuracy));
    return {
      version: JUDGE_VERSION,
      mode: "flow",
      results,
      matched: hits.length,
      expected: counted,
      extras,
      pitchAccuracy,
      timingAccuracy,
      meanOffsetMs,
      toleranceMs: tolerance,
      beatMs,
      score,
      passed: score >= PASS_SCORE,
      done: results.every((r) => r.state !== "pending"),
    };
  }

  // ------------------------------------------------------------------------- step mode

  // Waits at each onset until every note there has been played; a wrong key is counted against the
  // notes still waiting and the first wrong one is remembered. Nothing passes in step mode: it is the
  // repair shop, not the test.
  // `hands` is the stage's: notes of the other hand are out, as are the bars outside `range`.
  function createStepRun(notes, range, hands) {
    const from = range ? range[0] : 0;
    const to = range ? range[1] : BARS - 1;
    const inside = (n) => n.bar >= from && n.bar <= to && (!hands || hands === "B" || n.hand === hands);
    const mine = notes.filter(inside);
    const results = notes.map((n) => ({ state: inside(n) ? "pending" : "out", timing: null, offset_ms: null, played: null, tries: 0 }));
    const onsets = [...new Set(mine.map((n) => n.beat))].sort((a, b) => a - b);
    let at = 0;
    let arrivedMs = null;

    function waiting() {
      return mine.filter((n) => n.beat === onsets[at] && results[n.index].state === "pending");
    }

    function press(midi, tMs) {
      if (at >= onsets.length) return { done: true, right: false };
      if (arrivedMs === null) arrivedMs = tMs;
      const due = waiting();
      const hit = due.find((n) => n.midi === midi);
      if (!hit) {
        for (const n of due) {
          results[n.index].tries += 1;
          if (results[n.index].played === null) results[n.index].played = midi;
        }
        return { done: false, right: false };
      }
      const r = results[hit.index];
      r.state = r.tries ? "fixed" : "right";
      r.offset_ms = Math.max(0, Math.round(tMs - arrivedMs));
      r.timing = r.offset_ms <= STEP_QUICK_MS ? "quick" : "slow";
      if (!waiting().length) {
        at += 1;
        arrivedMs = tMs;
      }
      return { done: at >= onsets.length, right: true };
    }

    function summary() {
      const judged = results.filter((r) => r.state !== "out");
      const firstTry = judged.filter((r) => r.state === "right").length;
      const found = judged.filter((r) => r.state === "right" || r.state === "fixed");
      const quick = found.filter((r) => r.timing === "quick").length;
      const pitchAccuracy = judged.length ? firstTry / judged.length : 0;
      const timingAccuracy = found.length ? quick / found.length : 0;
      const score = Math.round(100 * (PITCH_WEIGHT * pitchAccuracy + TIMING_WEIGHT * timingAccuracy));
      return {
        version: JUDGE_VERSION,
        mode: "step",
        results: results.map((r) => ({ state: r.state === "fixed" ? "right" : r.state, timing: r.state === "fixed" ? "fixed" : r.timing, offset_ms: r.offset_ms, played: r.played })),
        matched: found.length,
        expected: judged.length,
        extras: 0,
        pitchAccuracy,
        timingAccuracy,
        meanOffsetMs: 0,
        score,
        passed: false,
        done: at >= onsets.length,
      };
    }

    return {
      press,
      summary,
      target: () => (at < onsets.length ? onsets[at] : null),
      waiting: () => waiting().map((n) => n.index),
      arrive: (tMs) => {
        arrivedMs = tMs;
      },
    };
  }

  // ------------------------------------------------------------------------- what went wrong

  // One line per kind of slip, the worst first, so the player knows what to look at.
  function slips(exercise, result) {
    const out = [];
    exercise.notes.forEach((n, i) => {
      const r = result.results[i];
      if (!r || r.state === "out" || r.state === "pending") return;
      const zone = zoneOf(n.hand, n.step);
      if (r.state === "missed") out.push({ index: i, kind: "missed", zone });
      else if (r.state === "wrong" || (r.state === "right" && r.timing === "fixed")) {
        const played = r.played;
        let kind = "wrong-other";
        if (played !== null && played !== undefined) {
          const spelled = spell(played, exercise.key);
          if (Math.abs(played - n.midi) === 12) kind = "wrong-octave";
          else if (n.shown && Math.abs(played - n.midi) === 1) kind = "wrong-accidental";
          else if (Math.abs(spelled.step - n.step) === 1) kind = "wrong-step";
        }
        out.push({ index: i, kind, zone });
      } else if (r.timing === "early" || r.timing === "late") out.push({ index: i, kind: r.timing, zone });
      else if (r.timing === "slow") out.push({ index: i, kind: "slow", zone });
    });
    return out;
  }

  const KIND_WORDS = {
    "wrong-step": "off by one step: a line read as the next space, or the other way",
    "wrong-octave": "in the wrong octave",
    "wrong-accidental": "an accidental missed",
    "wrong-other": "another note",
    missed: "not played",
    early: "early",
    late: "late",
    slow: "took more than a second and a half to find",
  };

  function spotWords(exercise, result) {
    const list = slips(exercise, result);
    if (!list.length) return ["Nothing to fix here."];
    const lines = [];
    const byZone = {};
    for (const s of list) if (s.kind.startsWith("wrong") || s.kind === "missed") byZone[s.zone] = (byZone[s.zone] || 0) + 1;
    for (const zone of Object.keys(byZone).sort((a, b) => byZone[b] - byZone[a])) {
      const seen = exercise.notes.filter((n, i) => zoneOf(n.hand, n.step) === zone && result.results[i] && result.results[i].state !== "out").length;
      lines.push(`${zoneWords(zone)}: ${byZone[zone]} of ${seen} missed or misread.`);
    }
    const byKind = {};
    for (const s of list) byKind[s.kind] = (byKind[s.kind] || 0) + 1;
    for (const kind of ["wrong-step", "wrong-octave", "wrong-accidental", "wrong-other", "slow"]) {
      if (byKind[kind]) lines.push(`${byKind[kind]} ${KIND_WORDS[kind]}.`);
    }
    const lateL = list.filter((s) => s.kind === "late" && exercise.notes[s.index].hand === "L").length;
    const lateR = list.filter((s) => s.kind === "late" && exercise.notes[s.index].hand === "R").length;
    const early = byKind.early || 0;
    if (lateL + lateR + early) {
      const where = lateL > lateR ? "the left hand drifts behind" : lateR ? "the right hand is behind" : "";
      lines.push(`${lateL + lateR + early} off the beat${where ? `, ${where}` : ""}: the notes are there, the pulse is not yet.`);
    }
    return lines;
  }

  function badBars(exercise, result) {
    const bars = new Set();
    for (const s of slips(exercise, result)) bars.add(exercise.notes[s.index].bar);
    return [...bars].sort((a, b) => a - b);
  }

  function verdict(result) {
    if (result.mode === "step") return `Step mode: ${result.score}. Only a Flow take can pass the stage.`;
    return `${result.passed ? "Passed" : "Not yet"}: ${result.score}. The line is ${PASS_SCORE}.`;
  }

  function noteWords(exercise, index, result, spelling) {
    const n = exercise.notes[index];
    const r = result ? result.results[index] : null;
    const who = `Bar ${n.bar + 1}, ${n.hand === "R" ? "right" : "left"} hand: ${noteName(n.midi, spelling)}`;
    if (!r || r.state === "pending" || r.state === "out") return `${who}.`;
    if (r.state === "missed") return `${who}, not played.`;
    if (r.state === "wrong") return `${who}, you played ${noteName(r.played, spelling)}.`;
    if (r.timing === "fixed") return `${who}, found after ${noteName(r.played, spelling)}.`;
    if (r.timing === "quick" || r.timing === "slow") return `${who}, found in ${(r.offset_ms / 1000).toFixed(1)} s.`;
    if (r.timing === "ontime") return `${who}, in time.`;
    return `${who}, ${r.timing} by ${Math.abs(r.offset_ms)} ms.`;
  }

  // ------------------------------------------------------------------------- the record and the screen

  function toRecord(exercise, result, setup) {
    const round4 = (x) => Math.round(x * 10000) / 10000;
    return {
      key: exercise.key,
      hands: exercise.hands,
      difficulty: exercise.difficulty,
      tempo_bpm: setup.tempo,
      mode: result.mode,
      curtain: Boolean(setup.curtain),
      seed: exercise.seed,
      notes: exercise.notes.map((n) => ({ hand: n.hand, step: n.step, acc: n.acc, midi: n.midi, beat: n.beat, dur: n.dur })),
      events: setup.events || [],
      results: result.results.map((r) => ({ state: r.state, timing: r.timing, offset_ms: r.offset_ms, played: r.played })),
      score: result.score,
      pitch_accuracy: round4(result.pitchAccuracy),
      timing_accuracy: round4(result.timingAccuracy),
      judge_version: result.version,
    };
  }

  function clampTempo(value) {
    if (value === null || value === undefined || value === "") return TEMPO_DEFAULT;
    const n = Number(value);
    if (!Number.isFinite(n)) return TEMPO_DEFAULT;
    return Math.min(TEMPO_MAX, Math.max(TEMPO_MIN, Math.round(n)));
  }

  function stageLine(report, stage) {
    const n = stageCount();
    const here = report && report.stage ? report.stage.index : 0;
    const where = `Stage ${stage.index + 1} of ${n}: ${stageTitle(stage)}.`;
    if (report && report.stage && report.stage.done) return `${where} Every stage is passed. Keep reading, or raise the tempo.`;
    if (stage.index < here) return `${where} Passed already; the path is at stage ${here + 1}.`;
    if (stage.index > here) return `${where} Ahead of the path, which is at stage ${here + 1}. A pass here counts.`;
    return `${where} Pass it in Flow to move on.`;
  }

  function workWords(report) {
    if (!report || !report.focus || !report.focus.length) return "";
    return `Work on: ${report.focus.map(zoneWords).join("; ")}. The next exercises lean that way.`;
  }

  // Keys lit while reading: the notes due now in amber, a held right note in green, a wrong one in red.
  function litNotes(exercise, result, dueIndexes, held) {
    const lit = [];
    const due = new Set(dueIndexes || []);
    for (const i of due) {
      const n = exercise.notes[i];
      const r = result ? result.results[i] : null;
      lit.push({ midi: n.midi, className: r && r.state === "right" ? "im-key-chord" : "im-key-pending" });
    }
    for (const midi of held || []) {
      const mine = lit.find((l) => l.midi === midi);
      if (mine) mine.className = "im-key-chord";
      else lit.push({ midi, className: "im-key-outside" });
    }
    return lit;
  }

  return {
    KEYS, HANDS, HAND_WORDS, BARS, BEATS, CONTROL_FLOOR, JUDGE_VERSION, PASS_SCORE, PITCH_WEIGHT, TIMING_WEIGHT, TEMPO_MIN, TEMPO_MAX, TEMPO_DEFAULT, TREBLE, BASS, RANGES,
    stageCount, stageOf, stageIndex, keyInfo, keyWords, stageTitle, keyAccidentals, signaturePositions, midiOf, spell, shownAccidental, noteName, zoneOf, zoneWords,
    makeRandom, generate, isActive, activeNotes, keyboardRange, toleranceMs, judge, createStepRun, slips, spotWords, badBars, verdict, noteWords, toRecord, clampTempo, stageLine, workWords, litNotes,
  };
});
