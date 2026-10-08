// improv: "Show me". Pure: no browser, runs under Node in the tests.
//
// Given the exercise's scoring kind and its settings, work out the notes that do what it asks,
// so the player can hear and see it before trying. The notes are built from the same chart and
// the same chord table the judge reads, and the tests run them through the real judge, so the
// demonstration is a passing take and cannot drift from what the exercise really wants.
//
//   const demo = ImprovDemo.build({ scoring, chart, from, to, qualities, beatsPerBar, bpm, downbeat });
//   demo.ok     false, with demo.reason, when there is nothing to show
//   demo.notes  [{ note, when, seconds, velocity }] on the audio clock, from `downbeat`
//   demo.line   one sentence saying what is about to be shown
//   demo.endsAt the audio time the last bar ends
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovDemo = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const LOW = 55; // G3
  const HIGH = 79; // G5
  const MIDDLE = 64;
  const VELOCITY = 0.8;
  const EPS = 1e-9;
  const SHOWN = ["scale_only", "chord_tones_on_beats", "guide_tones", "approach_notes", "rhythm_motif", "call_and_response"];

  const pcOf = (note) => ((note % 12) + 12) % 12;

  function canShow(kind) {
    return SHOWN.includes(kind);
  }

  // ----------------------------------------------------------------- the words

  function beatWords(pos) {
    const whole = Math.floor(pos + EPS);
    const frac = pos - whole;
    if (frac < EPS) return `beat ${whole + 1}`;
    if (Math.abs(frac - 0.5) < EPS) return `the and of ${whole + 1}`;
    if (Math.abs(frac - 0.25) < EPS) return `a quarter of the way into beat ${whole + 1}`;
    if (Math.abs(frac - 0.75) < EPS) return `three quarters of the way into beat ${whole + 1}`;
    return `${frac.toFixed(2)} of the way into beat ${whole + 1}`;
  }

  function joinWords(list) {
    if (list.length <= 1) return list.join("");
    return `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
  }

  // ----------------------------------------------------------------- the chart

  function chordAtPos(chart, from, beatsPerBar, pos) {
    const bar = chart.bars[from + Math.max(0, Math.floor((pos + EPS) / beatsPerBar))];
    if (!bar || !bar.chords.length) return null;
    const into = Math.max(0, pos - Math.floor((pos + EPS) / beatsPerBar) * beatsPerBar);
    let chord = bar.chords[0];
    for (const c of bar.chords) if (into + EPS >= c.beat) chord = c;
    return chord;
  }

  function tonesOf(chord, byQuality) {
    const q = chord && byQuality.get(chord.quality);
    if (!q) return { pcs: new Set(), guides: new Set(), scale: new Set() };
    const pcs = new Set((q.intervals || []).map((i) => pcOf(chord.root + i)));
    const roles = q.roles || {};
    const guides = new Set(
      Object.keys(roles)
        .filter((step) => roles[step] === "third" || roles[step] === "seventh")
        .map((step) => pcOf(chord.root + Number(step)))
    );
    const first = (q.scales || [])[0];
    const scale = new Set(first ? (first.intervals || []).map((i) => pcOf(chord.root + i)) : pcs);
    return { pcs, guides, scale };
  }

  function candidates(pcs) {
    const out = [];
    for (let n = LOW; n <= HIGH; n++) if (pcs.has(pcOf(n))) out.push(n);
    return out;
  }

  function nearest(cands, from, avoid) {
    let best = null;
    for (const c of cands) {
      if (avoid && c === from && cands.length > 1) continue;
      if (best === null || Math.abs(c - from) < Math.abs(best - from)) best = c;
    }
    return best;
  }

  // ----------------------------------------------------------------- the kinds

  // Each builder gives events: { pos, note, len? } with pos in beats from the first downbeat.

  function chordToneEvents(ctx, positions) {
    const events = [];
    let prev = MIDDLE;
    for (const pos of positions) {
      const chord = chordAtPos(ctx.chart, ctx.from, ctx.beatsPerBar, pos);
      const cands = candidates(tonesOf(chord, ctx.byQuality).pcs);
      if (!cands.length) continue;
      prev = nearest(cands, prev, true);
      events.push({ pos, note: prev });
    }
    return events;
  }

  function perBar(ctx, beats) {
    const out = [];
    for (let k = 0; k < ctx.bars; k++) for (const b of beats) if (b < ctx.beatsPerBar - EPS) out.push(k * ctx.beatsPerBar + b);
    return out;
  }

  function namedBeats(params, beatsPerBar, fallback) {
    if (Array.isArray(params.beats) && params.beats.length) return params.beats;
    return fallback || Array.from({ length: beatsPerBar }, (_, i) => i + 1);
  }

  function scaleEvents(ctx) {
    const events = [];
    let prev = null;
    let dir = 1;
    for (let pos = 0; pos < ctx.bars * ctx.beatsPerBar - EPS; pos++) {
      const chord = chordAtPos(ctx.chart, ctx.from, ctx.beatsPerBar, pos);
      const cands = candidates(tonesOf(chord, ctx.byQuality).scale);
      if (!cands.length) continue;
      let index = cands.indexOf(nearest(cands, prev === null ? 60 : prev, false));
      if (prev !== null) {
        if (index + dir < 0 || index + dir >= cands.length) dir = -dir;
        index += dir;
      }
      prev = cands[Math.max(0, Math.min(cands.length - 1, index))];
      events.push({ pos, note: prev, len: 0.9 });
    }
    return events;
  }

  function guideEvents(ctx) {
    const events = [];
    let prev = MIDDLE;
    let prevName = null;
    for (let k = 0; k < ctx.bars; k++) {
      for (const chord of ctx.chart.bars[ctx.from + k].chords) {
        const tones = tonesOf(chord, ctx.byQuality);
        const cands = candidates(tones.guides.size ? tones.guides : tones.pcs);
        if (!cands.length) continue;
        prev = nearest(cands, prev, chord.name === prevName);
        prevName = chord.name;
        events.push({ pos: k * ctx.beatsPerBar + chord.beat, note: prev, len: Math.max(0.5, chord.beats * 0.95) });
      }
    }
    return events;
  }

  function approachEvents(ctx, params) {
    const events = [];
    let prev = MIDDLE;
    for (const pos of perBar(ctx, namedBeats(params, ctx.beatsPerBar, [1]).map((b) => b - 1))) {
      const chord = chordAtPos(ctx.chart, ctx.from, ctx.beatsPerBar, pos);
      const tones = tonesOf(chord, ctx.byQuality);
      const cands = candidates(tones.pcs);
      if (!cands.length) continue;
      const target = nearest(cands, prev, true);
      const outside = (n) => !tones.pcs.has(pcOf(n)) && !tones.scale.has(pcOf(n));
      const lead = outside(target - 1) ? target - 1 : outside(target + 1) ? target + 1 : target - 1;
      events.push({ pos: pos - 0.4, note: lead, len: 0.35 });
      events.push({ pos, note: target });
      prev = target;
    }
    return events;
  }

  function phraseEvents(ctx, params) {
    const phrase = params.phrase;
    const ok = Array.isArray(phrase) && phrase.length > 0 && phrase.every((p) => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && p[0] >= 0 && Number.isInteger(p[1]));
    if (!ok) return null;
    const answerBar = Number.isInteger(params.answerBar) ? params.answerBar : 1;
    if (answerBar < 1 || answerBar >= ctx.bars) return null;
    const events = [];
    for (const bar of [answerBar - 1, answerBar]) for (const [beat, note] of phrase) events.push({ pos: bar * ctx.beatsPerBar + beat, note, len: 0.8 });
    return { events, answerBar };
  }

  // ---------------------------------------------------------------------- build

  function build(input) {
    const scoring = input.scoring || {};
    const kind = scoring.kind;
    const params = scoring.params || {};
    if (!canShow(kind)) return { ok: false, reason: "This one has no set answer, so there is nothing to show. Play whatever you like." };
    const chart = input.chart;
    const beatsPerBar = input.beatsPerBar || (chart && chart.beatsPerBar) || 4;
    const bars = input.to - input.from;
    if (!chart || !chart.bars || bars < 1) return { ok: false, reason: "There are no bars to show it over." };
    const ctx = {
      chart,
      from: input.from,
      bars,
      beatsPerBar,
      byQuality: new Map((input.qualities || []).map((q) => [q.symbol, q])),
    };

    let events;
    let line;
    if (kind === "rhythm_motif") {
      const pattern = params.pattern;
      const good = Array.isArray(pattern) && pattern.length > 0 && pattern.every((p) => Number.isFinite(p) && p >= 0 && p < beatsPerBar);
      if (!good) return { ok: false, reason: "This exercise has no rhythm written down, so there is nothing to show." };
      events = chordToneEvents(ctx, perBar(ctx, pattern));
      line = `In every bar, a chord tone on ${joinWords(pattern.map(beatWords))}. The same rhythm from the first bar to the last.`;
    } else if (kind === "chord_tones_on_beats") {
      const named = namedBeats(params, beatsPerBar);
      events = chordToneEvents(ctx, perBar(ctx, named.map((b) => b - 1)));
      line = `A note of the bar's chord on ${joinWords(named.map((b) => beatWords(b - 1)))}, in every bar.`;
    } else if (kind === "scale_only") {
      events = scaleEvents(ctx);
      line = "One note a beat, walking up and down the scale that goes with each chord. Every note belongs to it.";
    } else if (kind === "guide_tones") {
      events = guideEvents(ctx);
      line = "The third or the seventh of each chord, held, moving by the smallest step to the next chord's.";
    } else if (kind === "approach_notes") {
      const named = namedBeats(params, beatsPerBar, [1]);
      events = approachEvents(ctx, params);
      line = `A note a half step away leads into a chord tone on ${joinWords(named.map((b) => beatWords(b - 1)))}, in every bar.`;
    } else {
      const made = phraseEvents(ctx, params);
      if (!made) return { ok: false, reason: "This exercise has no phrase written down, so there is nothing to show." };
      events = made.events;
      line = `The call in bar ${made.answerBar}, then the same notes as the answer in bar ${made.answerBar + 1}.`;
    }
    if (!events.length) return { ok: false, reason: "There is nothing to show over this chart." };

    events.sort((a, b) => a.pos - b.pos || a.note - b.note);
    const beatSeconds = 60 / input.bpm;
    const notes = events.map((e, i) => {
      let len = e.len;
      if (len === undefined) {
        const next = events.slice(i + 1).find((n) => n.pos > e.pos + EPS);
        len = next ? Math.min(2, Math.max(0.25, (next.pos - e.pos) * 0.9)) : 1;
      }
      return { note: e.note, when: input.downbeat + e.pos * beatSeconds, seconds: Math.max(0.05, len * beatSeconds), velocity: VELOCITY };
    });
    return { ok: true, notes, line, endsAt: input.downbeat + bars * beatsPerBar * beatSeconds };
  }

  return { build, canShow, beatWords, joinWords, SHOWN };
});
