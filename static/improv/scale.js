// improv: the scale trainer's layout, names and fingering, and its judge. Pure: no browser, no clock,
// runs under Node in the tests. A step is one note in each hand at the same moment; the right hand
// plays an octave above the left, both going up the major scale and then back down.
//
// The judge takes the notes played, in milliseconds from the moment the first step was due, and says
// for every note the player was asked for whether it came, and how far from its time. A note counts for
// a step when it is the right key and lands within half a step of the step's time; any other key press
// is an extra. The live display and the final score come from this one function, run with `now` while
// the player plays and without it at the end, so the screen cannot show one thing while the score says
// another. JUDGE_VERSION is saved with every run so old scores stay explainable when these rules change.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovScale = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const MAJOR = [0, 2, 4, 5, 7, 9, 11];
  const LETTERS = ["C", "D", "E", "F", "G", "A", "B"];
  const LETTER_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const KEY_NAMES = ["C", "Db", "D", "Eb", "E", "F", null, "G", "Ab", "A", "Bb", "B"];
  // The three top keys of an 88-key piano are the control keys (control.js), so no scale reaches them.
  const CONTROL_FLOOR = 106;
  const LOWEST_KEY = 21;

  const LEVELS = { 1: 2, 2: 3, 3: 4 };

  const JUDGE_VERSION = 1;
  const PASS_SCORE = 80;
  const PITCH_WEIGHT = 0.7;
  const TIMING_WEIGHT = 0.3;
  const TOLERANCE_OF_STEP = 0.4;
  const TOLERANCE_MIN_MS = 50;
  const TOLERANCE_MAX_MS = 120;
  const STEADY_MS = 25;

  function levelInfo(level) {
    const octaves = LEVELS[level];
    if (!octaves) throw new Error(`There is no level ${level}.`);
    return { level, octaves, perBeat: octaves, steps: 14 * octaves + 1 };
  }

  function needsFullKeyboard(octaves) {
    return octaves >= 4;
  }

  function keyName(pc, spelling) {
    if (pc === 6) return spelling === "flats" ? "Gb" : "F#";
    return KEY_NAMES[((pc % 12) + 12) % 12];
  }

  function scaleNotes(pc, spelling) {
    const tonic = keyName(pc, spelling);
    const first = LETTERS.indexOf(tonic[0]);
    return MAJOR.map((interval, i) => {
      const letter = LETTERS[(first + i) % 7];
      const target = (pc + interval) % 12;
      const drift = ((((target - LETTER_PC[letter]) % 12) + 18) % 12) - 6;
      return letter + (drift === 1 ? "#" : drift === -1 ? "b" : "");
    });
  }

  // The left hand's first note. Two octaves sit around middle C; more start lower, and a scale whose
  // top would touch the control keys moves down an octave.
  function leftStart(pc, octaves) {
    let start = (octaves === 2 ? 48 : 36) + pc;
    if (start + 12 * octaves + 12 >= CONTROL_FLOOR) start -= 12;
    return start;
  }

  function buildSteps(pc, octaves) {
    const start = leftStart(pc, octaves);
    const total = 7 * octaves;
    const up = [];
    for (let k = 0; k <= total; k++) {
      up.push(start + 12 * Math.floor(k / 7) + MAJOR[k % 7]);
    }
    const notes = up.concat(up.slice(0, total).reverse());
    return notes.map((left, index) => ({
      index,
      left,
      right: left + 12,
      degree: (index <= total ? index : 2 * total - index) % 7,
      direction: index < total ? "up" : index === total ? "top" : "down",
    }));
  }

  // The finger for each note going up. A stored row holds seven numbers for the first octave, seven for
  // the later ones, and the finger of the last (top) note.
  function fingers(row, octaves) {
    const total = 7 * octaves;
    const out = [];
    for (let k = 0; k < total; k++) {
      out.push((k < 7 ? row.first_octave : row.next_octaves)[k % 7]);
    }
    out.push(row.last_note);
    return out;
  }

  function fingersUpAndDown(row, octaves) {
    const up = fingers(row, octaves);
    return up.concat(up.slice(0, -1).reverse());
  }

  function plan(pc, octaves, spelling, fingerings) {
    const rows = fingerings || [];
    const find = (hand) => rows.find((r) => r.root_pc === pc && r.hand === hand);
    const leftRow = find("L");
    const rightRow = find("R");
    const left = leftRow ? fingersUpAndDown(leftRow, octaves) : null;
    const right = rightRow ? fingersUpAndDown(rightRow, octaves) : null;
    const names = scaleNotes(pc, spelling);
    const steps = buildSteps(pc, octaves).map((step) => ({
      ...step,
      name: names[step.degree],
      leftFinger: left ? left[step.index] : null,
      rightFinger: right ? right[step.index] : null,
    }));
    return { key: keyName(pc, spelling), pc, octaves, steps, hasFingering: Boolean(left && right) };
  }

  // ---------------------------------------------------------------------- the judge

  function stepMs(tempo, perBeat) {
    return 60000 / (tempo * perBeat);
  }

  function toleranceMs(step) {
    return Math.round(Math.min(TOLERANCE_MAX_MS, Math.max(TOLERANCE_MIN_MS, step * TOLERANCE_OF_STEP)));
  }

  function timingOf(offset, tolerance) {
    if (offset < -tolerance) return "early";
    if (offset > tolerance) return "late";
    return "ontime";
  }

  // input: { steps, tempo, perBeat, events: [{t_ms, type, note}], latencyMs, now }
  function judge(input) {
    const steps = input.steps;
    const step = stepMs(input.tempo, input.perBeat);
    const half = step / 2;
    const tolerance = toleranceMs(step);
    const latency = input.latencyMs || 0;
    const live = input.now !== undefined && input.now !== null;

    // One slot for each note asked of each hand at each step.
    const slots = [];
    steps.forEach((s, i) => {
      slots.push({ step: i, hand: "left", note: s.left, due: i * step, hit: null });
      slots.push({ step: i, hand: "right", note: s.right, due: i * step, hit: null });
    });

    const presses = (input.events || [])
      .filter((e) => e.type === "on" && e.note < CONTROL_FLOOR && (!live || e.t_ms <= input.now))
      .map((e) => ({ note: e.note, t: e.t_ms - latency }))
      .sort((a, b) => a.t - b.t);

    let extras = 0;
    for (const press of presses) {
      let best = null;
      for (const slot of slots) {
        if (slot.hit || slot.note !== press.note) continue;
        const gap = Math.abs(press.t - slot.due);
        if (gap <= half && (best === null || gap < Math.abs(press.t - best.due))) best = slot;
      }
      if (best) best.hit = { offsetMs: press.t - best.due };
      else extras += 1;
    }

    const closed = (slot) => slot.hit !== null || !live || input.now >= slot.due + half;
    const stepStates = steps.map((s, i) => {
      const part = (slot) => {
        if (slot.hit) return { state: "hit", offsetMs: Math.round(slot.hit.offsetMs), timing: timingOf(slot.hit.offsetMs, tolerance) };
        return { state: closed(slot) ? "missed" : "pending", offsetMs: null, timing: null };
      };
      const left = part(slots[2 * i]);
      const right = part(slots[2 * i + 1]);
      const states = [left.state, right.state];
      let state = "partial";
      if (states.every((x) => x === "hit")) state = "hit";
      else if (states.every((x) => x === "pending")) state = "pending";
      else if (states.every((x) => x === "missed")) state = "missed";
      else if (states.includes("pending") && !states.includes("missed")) state = "pending";
      return { index: i, left, right, state };
    });

    const counted = slots.filter(closed);
    const matched = slots.filter((slot) => slot.hit).length;
    const expected = counted.length;
    const hits = slots.filter((slot) => slot.hit);
    const onTime = hits.filter((slot) => Math.abs(slot.hit.offsetMs) <= tolerance).length;
    const pitchAccuracy = expected + extras ? matched / (expected + extras) : 0;
    const timingAccuracy = matched ? onTime / matched : 0;
    const meanOffsetMs = matched ? Math.round(hits.reduce((a, slot) => a + slot.hit.offsetMs, 0) / matched) : 0;
    const score = Math.round(100 * (PITCH_WEIGHT * pitchAccuracy + TIMING_WEIGHT * timingAccuracy));
    const missedSteps = stepStates.filter((s) => s.left.state === "missed" || s.right.state === "missed").map((s) => s.index);
    const done = stepStates.every((s) => s.state !== "pending");

    return {
      version: JUDGE_VERSION,
      steps: stepStates,
      matched,
      expected,
      extras,
      pitchAccuracy,
      timingAccuracy,
      meanOffsetMs,
      feel: meanOffsetMs < -STEADY_MS ? "early" : meanOffsetMs > STEADY_MS ? "late" : "steady",
      toleranceMs: tolerance,
      stepMs: step,
      score,
      passed: score >= PASS_SCORE,
      missedSteps,
      done,
    };
  }

  // What a ScaleRun row holds, from a finished judgement.
  function toRecord(result, setup) {
    const round4 = (x) => Math.round(x * 10000) / 10000;
    return {
      root_pc: setup.rootPc,
      octaves: setup.octaves,
      notes_per_beat: setup.perBeat,
      tempo_bpm: setup.tempo,
      score: result.score,
      pitch_accuracy: round4(result.pitchAccuracy),
      timing_accuracy: round4(result.timingAccuracy),
      mean_offset_ms: Math.round(result.meanOffsetMs),
      passed: result.passed,
      missed_steps: result.missedSteps,
      judge_version: result.version,
    };
  }

  // ---------------------------------------------------------------------- the screen's rules

  // The order Avi drills in: round the circle of fifths from G.
  const CIRCLE = [7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5, 0];
  const TEMPO_MIN = 30;
  const TEMPO_MAX = 160;
  const TEMPO_DEFAULT = 60;
  const COUNT_IN_BEATS = 4;

  function nextKey(pc) {
    const at = CIRCLE.indexOf(pc);
    return at < 0 ? CIRCLE[0] : CIRCLE[(at + 1) % CIRCLE.length];
  }

  function clampTempo(value) {
    if (value === null || value === undefined || value === "") return TEMPO_DEFAULT;
    const n = Number(value);
    if (!Number.isFinite(n)) return TEMPO_DEFAULT;
    return Math.min(TEMPO_MAX, Math.max(TEMPO_MIN, Math.round(n)));
  }

  function timeline(tempo, perBeat) {
    const beatMs = 60000 / tempo;
    return { beatMs, stepMs: beatMs / perBeat, countInBeats: COUNT_IN_BEATS, countInMs: COUNT_IN_BEATS * beatMs };
  }

  function runBeats(plan, perBeat) {
    return plan.steps.length / perBeat;
  }

  function runMs(plan, clock) {
    return plan.steps.length * clock.stepMs;
  }

  function levelLabel(level) {
    const info = levelInfo(level);
    return `${info.octaves} octaves, ${info.perBeat} notes a beat`;
  }

  function verdict(result) {
    return `${result.passed ? "Passed" : "Not yet"}: ${result.score}. The line is ${PASS_SCORE}.`;
  }

  function feelWords(result) {
    const ms = Math.abs(result.meanOffsetMs);
    const side = result.meanOffsetMs < 0 ? "early" : "late";
    if (result.feel === "steady") return ms === 0 ? "Steady: right on the beat." : `Steady: ${ms} ms ${side} on average.`;
    return `${result.feel === "late" ? "You were behind" : "You rushed"}: ${ms} ms ${side} on average.`;
  }

  function missedWords(plan, result, limit) {
    const cap = limit || 8;
    const where = { up: "up", down: "down", top: "at the top" };
    const all = result.missedSteps.map((i) => {
      const step = plan.steps[i];
      return `${step.name} ${where[step.direction]} (step ${i + 1})`;
    });
    if (all.length <= cap) return all;
    return [...all.slice(0, cap), `and ${all.length - cap} more`];
  }

  function fingerWords(step) {
    if (step.leftFinger === null || step.rightFinger === null) return step.name;
    return `${step.name}: left ${step.leftFinger}, right ${step.rightFinger}`;
  }

  function bestOf(runs, rootPc, octaves) {
    const mine = (runs || []).filter((r) => r.root_pc === rootPc && r.octaves === octaves);
    if (!mine.length) return null;
    const best = mine.reduce((a, b) => (b.score > a.score ? b : a));
    return { score: best.score, tempo: best.tempo_bpm, passed: best.passed };
  }

  function keyboardRange(plan) {
    return {
      from: Math.min(...plan.steps.map((s) => s.left)),
      to: Math.max(...plan.steps.map((s) => s.right)),
    };
  }

  // Green for a note asked for and held, amber for one still to play, red for a held one nobody asked for.
  function litNotes(step, held) {
    if (!step) return (held || []).map((midi) => ({ midi, className: "im-key-on" }));
    const asked = [step.left, step.right];
    const lit = asked.map((midi) => ({ midi, className: (held || []).includes(midi) ? "im-key-chord" : "im-key-pending" }));
    for (const midi of held || []) if (!asked.includes(midi)) lit.push({ midi, className: "im-key-outside" });
    return lit;
  }

  return { CIRCLE, TEMPO_MIN, TEMPO_MAX, TEMPO_DEFAULT, nextKey, clampTempo, timeline, runBeats, runMs, levelLabel, verdict, feelWords, missedWords, fingerWords, bestOf, keyboardRange, litNotes, JUDGE_VERSION, PASS_SCORE, PITCH_WEIGHT, TIMING_WEIGHT, stepMs, toleranceMs, judge, toRecord, MAJOR, CONTROL_FLOOR, LOWEST_KEY, levelInfo, needsFullKeyboard, keyName, scaleNotes, leftStart, buildSteps, fingers, fingersUpAndDown, plan };
});
