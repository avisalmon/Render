// improv: the rules of the repertoire screen, pure so they run under Node. A piece is stored whole; this file cuts
// the stretch a rung asks for out of it (rebased to start at beat 0 of bar 0, the shape the reading judge and the
// staff already take), and says in words where the player is on the ladder. The ladder itself, and what passes,
// belong to the server (improv/ladder.py); the page only reads it.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./reading.js"));
  else root.ImprovRepertoire = factory(root.ImprovReading);
})(typeof self !== "undefined" ? self : this, function (R) {
  "use strict";

  const PER_PAGE = 4;
  const DRILL = "drill";
  const HAND_NAMES = { R: "right hand", L: "left hand", B: "both hands" };
  const EPS = 1e-6;

  // The stretch of `piece` from bar `firstBar` to `lastBar` (counted from 1, as printed), as an exercise.
  // Both hands are always on the staff; `hands` is the one being asked for.
  function slice(piece, firstBar, lastBar, hands) {
    const beats = piece.beats_per_bar;
    const origin = (firstBar - 1) * beats;
    const length = (lastBar - firstBar + 1) * beats;
    const mine = piece.notes
      .filter((n) => n.bar >= firstBar && n.bar <= lastBar)
      .map((n, order) => ({ n, order }))
      .sort((a, b) => a.n.beat - b.n.beat || (a.n.hand === b.n.hand ? a.n.step - b.n.step : a.n.hand === "R" ? -1 : 1) || a.order - b.order);
    const notes = mine.map(({ n }, index) => {
      const out = {
        hand: n.hand,
        step: n.step,
        acc: n.acc,
        midi: n.midi,
        beat: n.beat - origin,
        dur: n.dur,
        bar: n.bar - firstBar,
        index,
        voice: n.voice || 1,
        shown: n.shown || "",
      };
      if (n.hold) out.hold = n.hold;
      if (n.ties && n.ties.length) {
        const ties = n.ties.map(([beat, dur]) => [beat - origin, dur]).filter(([beat]) => beat < length - EPS);
        if (ties.length) out.ties = ties;
      }
      return out;
    });
    const bars = lastBar - firstBar + 1;
    return { key: piece.key, hands, beats, bars, firstBar, perPage: Math.min(PER_PAGE, bars), notes };
  }

  function exerciseFor(piece, rung) {
    return slice(piece, rung.first_bar, rung.last_bar, rung.hands);
  }

  const barsWords = (first, last) => (first === last ? `bar ${first}` : `bars ${first} to ${last}`);

  // The line a teacher would write on the piece for this rung.
  function rungWords(rung) {
    if (rung.key === DRILL) return `Drill ${barsWords(rung.first_bar, rung.last_bar)}, ${HAND_NAMES[rung.hands]}`;
    const where = barsWords(rung.first_bar, rung.last_bar);
    const pace = rung.tempo === "slow" ? "slowly" : "at tempo";
    if (rung.kind === "phrase") return `${capital(where)}: ${HAND_NAMES[rung.hands]}, ${pace}`;
    if (rung.kind === "join") return `Join, ${where}: both hands, at tempo`;
    if (rung.kind === "whole") return `The whole piece, both hands, ${pace}`;
    return `Performance: the whole piece, both hands, line ${rung.line}`;
  }

  const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  // Which group of the rung list a rung sits in: a phrase has its own, joins and the whole share the last.
  function groupOf(rung, piece) {
    if (rung.kind === "phrase") {
      const phrase = piece.phrases.find((p) => p.order === rung.phrase);
      return { id: `p${rung.phrase}`, label: `Phrase ${rung.phrase}: ${phrase ? phrase.title : barsWords(rung.first_bar, rung.last_bar)}` };
    }
    if (rung.kind === "join") return { id: "join", label: "Joining the phrases" };
    return { id: "whole", label: "The whole piece" };
  }

  // What a teacher would say before the rung. `phrase` is the piece's phrase row.
  function advice(rung, piece) {
    if (rung.key === DRILL) return "Any bars, either hand. Pick the stretch that went wrong and play it until it is easy.";
    if (rung.kind === "phrase") {
      const phrase = piece.phrases.find((p) => p.order === rung.phrase);
      const start = phrase && phrase.hint ? ` ${phrase.hint}` : "";
      if (rung.hands === "R") return `Right hand alone. The left hand is shown but not asked for.${start}`;
      if (rung.hands === "L") return `Left hand alone. Same bars, now the other hand.${start}`;
      return rung.tempo === "slow" ? `Both hands, slowly. Put the two together.${start}` : `Both hands at the piece's own tempo.${start}`;
    }
    if (rung.kind === "join") return "Two phrases in one go, so the seam between them is no surprise.";
    if (rung.kind === "whole") return rung.tempo === "slow" ? "The whole piece, slowly, from the first bar to the last." : "The whole piece at tempo.";
    return `A performance: play it through as if for someone. The line is ${rung.line}.`;
  }

  const bpmOf = (rung, piece) => (rung.tempo === "slow" ? piece.slow_bpm : piece.tempo_bpm);

  // Clicks before a run: one bar, or four when the bar is short.
  function countIn(beats) {
    return beats <= 2 ? 4 : beats;
  }

  function verdict(result, rung) {
    if (result.mode === "step") return `Step mode: ${result.score}. Only a Flow take of a rung can pass it.`;
    if (!rung || rung.key === DRILL) return `Drill: ${result.score}. A drill is for fixing; it never counts as a pass.`;
    return `${result.passed ? "Passed" : "Not yet"}: ${result.score}. The line is ${rung.line}.`;
  }

  // Bar numbers as printed, for the bars with a slip in them.
  function badBars(exercise, result) {
    return R.badBars(exercise, result).map((bar) => bar + exercise.firstBar);
  }

  function noteWords(exercise, index, result, spelling) {
    const n = exercise.notes[index];
    const r = result ? result.results[index] : null;
    const who = `Bar ${exercise.firstBar + n.bar}, ${n.hand === "R" ? "right" : "left"} hand: ${R.noteName(n.midi, spelling)}`;
    if (!r || r.state === "pending" || r.state === "out") return `${who}.`;
    if (r.state === "missed") return `${who}, not played.`;
    if (r.state === "wrong") return `${who}, you played ${R.noteName(r.played, spelling)}.`;
    if (r.timing === "fixed") return `${who}, found after ${R.noteName(r.played, spelling)}.`;
    if (r.timing === "quick" || r.timing === "slow") return `${who}, found in ${(r.offset_ms / 1000).toFixed(1)} s.`;
    if (r.timing === "ontime") return `${who}, in time.`;
    return `${who}, ${r.timing} by ${Math.abs(r.offset_ms)} ms.`;
  }

  // The body of a piece take, from a judged run.
  function toRecord(piece, rung, exercise, result, setup) {
    const round4 = (x) => Math.round(x * 10000) / 10000;
    return {
      piece: piece.slug,
      rung: rung.key,
      first_bar: exercise.firstBar,
      last_bar: exercise.firstBar + exercise.bars - 1,
      hands: exercise.hands,
      mode: result.mode,
      tempo_bpm: setup.tempo,
      curtain: Boolean(setup.curtain),
      notes: exercise.notes.map((n) => ({ hand: n.hand, step: n.step, acc: n.acc, midi: n.midi, beat: n.beat, dur: n.dur, bar: n.bar })),
      events: setup.events || [],
      results: result.results.map((r) => ({ state: r.state, timing: r.timing, offset_ms: r.offset_ms, played: r.played })),
      score: result.score,
      pitch_accuracy: round4(result.pitchAccuracy),
      timing_accuracy: round4(result.timingAccuracy),
      judge_version: result.version,
    };
  }

  // The piece's line in the piece list: where the player is on its ladder.
  function pieceLine(entry) {
    if (entry.done) return `${entry.title}: finished`;
    return `${entry.title}: ${entry.passed_count} of ${entry.total}`;
  }

  // One line under the controls: the rung's place on the path.
  function pathLine(entry, rung) {
    if (!entry) return "";
    if (rung.key === DRILL) return "A drill never counts toward the path; it is for mending a bar.";
    const row = entry.rungs.find((r) => r.key === rung.key);
    const index = entry.rungs.findIndex((r) => r.key === rung.key);
    const where = `Step ${index + 1} of ${entry.total}.`;
    if (entry.done) return `${where} Every rung of this piece is passed.`;
    if (row && row.passed) return `${where} Passed already${row.best !== null ? `, best ${row.best}` : ""}.`;
    if (entry.next === rung.key) return `${where} This is the next step on the path.`;
    const nextIndex = entry.rungs.findIndex((r) => r.key === entry.next);
    return `${where} The path is at step ${nextIndex + 1}. A pass here counts.`;
  }

  return { PER_PAGE, DRILL, HAND_NAMES, slice, exerciseFor, rungWords, groupOf, advice, bpmOf, countIn, verdict, badBars, noteWords, toRecord, pieceLine, pathLine, barsWords };
});
