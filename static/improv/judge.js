// improv: the judge. Pure: no page, no clock, no network. Runs under Node in the tests.
//
// The notes played, the chart they were played over, the tempo and feel, the scoring kind
// and the player's latency offset go in; a class for every note, the timing, the metrics and
// the score come out. The live display and the final score come from this one function, run
// with `now` while it plays and without it at the end, so the screen cannot show one thing
// while the score says another. JUDGE_VERSION is written into every take it scores, so when
// these rules change old scores stay explainable.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovJudge = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const JUDGE_VERSION = 1;
  const SCORING_KINDS = [
    "chord_tones_on_beats",
    "scale_only",
    "free_play",
    "guide_tones",
    "approach_notes",
    "rhythm_motif",
    "call_and_response",
  ];
  const GUIDE_STEP = 2; // a guide tone connects to the next chord's by a step: a tone or less
  const GUIDE_ROLES = new Set(["third", "seventh"]);
  const LOOKAHEAD_BEATS = 0.5;
  const APPROACH_BEATS = 1;
  const TOLERANCE_OF_BEAT = 0.1;
  const EPS = 1e-9;

  const pcOf = (note) => ((note % 12) + 12) % 12;

  function toleranceMs(bpm) {
    return Math.round((60000 / bpm) * TOLERANCE_OF_BEAT);
  }

  // -------------------------------------------------------------------- the chord

  // The chord sounding `ms` after the first judged downbeat, looking half a beat ahead so a
  // player who anticipates the change is judged against the chord they were going for. The
  // judged bars loop, so a time past the end comes round to the start.
  function chordAt(chart, from, to, bpm, ms) {
    const beatMs = 60000 / bpm;
    const bars = chart.bars.slice(from, to);
    if (!bars.length) return null;
    const barBeats = bars.map((b) => b.beats);
    const loopBeats = barBeats.reduce((a, b) => a + b, 0);
    let beat = (ms / beatMs + LOOKAHEAD_BEATS) % loopBeats;
    if (beat < 0) beat += loopBeats;
    let index = 0;
    while (index < bars.length - 1 && beat >= barBeats[index] - EPS) {
      beat -= barBeats[index];
      index += 1;
    }
    const bar = bars[index];
    let chord = bar.chords[0];
    for (const c of bar.chords) if (beat + EPS >= c.beat) chord = c;
    return chord ? { ...chord, barIndex: from + index } : null;
  }

  function chordTones(chord, byQuality) {
    const quality = byQuality.get(chord.quality);
    if (!quality) return { pcs: new Set(), guides: new Set(), scale: new Set() };
    const pcs = new Set((quality.intervals || []).map((i) => pcOf(chord.root + i)));
    const roles = quality.roles || {};
    const guides = new Set(
      Object.keys(roles)
        .filter((step) => GUIDE_ROLES.has(roles[step]))
        .map((step) => pcOf(chord.root + Number(step)))
    );
    const first = (quality.scales || [])[0];
    const scale = new Set(first ? (first.intervals || []).map((i) => pcOf(chord.root + i)) : []);
    return { pcs, guides, scale };
  }

  // --------------------------------------------------------------------- the grid

  // The grid the notes are judged against, in ms from the first judged downbeat, long
  // enough to cover the last note. The swung grid puts the off-beat where the band's own
  // swing puts it (band.js, swingBeat), so a swung eighth is on time when it is with the band.
  function gridTimes(kind, bpm, swingRatio, untilMs) {
    const beatMs = 60000 / bpm;
    const out = [];
    const last = Math.max(untilMs, 0) + beatMs * 2;
    for (let beat = 0; beat * beatMs <= last; beat++) {
      out.push(beat * beatMs);
      if (kind === "eighth") out.push((beat + 0.5) * beatMs);
      else if (kind === "swung") out.push((beat + swingRatio) * beatMs);
    }
    return out;
  }

  function nearest(ms, points) {
    let best = 0;
    for (let i = 1; i < points.length; i++) {
      if (Math.abs(ms - points[i]) < Math.abs(ms - points[best])) best = i;
    }
    return { index: best, offsetMs: ms - points[best] };
  }

  // -------------------------------------------------------------------- the words

  function timingWords(timing) {
    if (!timing || !timing.notes) return "no notes yet";
    const mean = Math.round(timing.meanMs);
    if (timing.withinPct < 60) return `your timing is uneven: only ${timing.withinPct}% of notes were close to the beat`;
    if (Math.abs(mean) <= 5) return "right on the beat";
    return mean < 0 ? `you rush by ${Math.abs(mean)} ms` : `you drag by ${mean} ms`;
  }

  // -------------------------------------------------------------------- the judge

  function judge(input) {
    const scoring = input.scoring || { kind: "free_play", params: {} };
    if (!SCORING_KINDS.includes(scoring.kind)) throw new Error(`Unknown scoring kind "${scoring.kind}"`);
    const bpm = input.bpm;
    const beatMs = 60000 / bpm;
    const beatsPerBar = input.chart.beatsPerBar || 4;
    const offset = Number(input.latencyOffsetMs) || 0;
    const swingRatio = input.swingRatio === undefined ? 0.5 : input.swingRatio;
    const gridKind = input.grid || "beat";
    const now = input.now === undefined ? Infinity : input.now - offset;
    const byQuality = new Map((input.qualities || []).map((q) => [q.symbol, q]));
    const tolerance = toleranceMs(bpm);

    // Note-ons, on the player's own clock, in order. Anything before the first downbeat by
    // more than half a beat was played during the count-in and is not judged.
    const ons = [];
    let ignored = 0;
    for (const e of input.events || []) {
      if (!e || e.type !== "on" || !Number.isInteger(e.note) || !Number.isFinite(e.t_ms)) continue;
      const t = e.t_ms - offset;
      if (t < -beatMs * LOOKAHEAD_BEATS) {
        ignored += 1;
        continue;
      }
      ons.push({ tMs: t, note: e.note, velocity: e.velocity });
    }
    ons.sort((a, b) => a.tMs - b.tMs);

    const lastMs = ons.length ? ons[ons.length - 1].tMs : 0;
    const grid = gridTimes(gridKind, bpm, swingRatio, lastMs);
    const beats = gridTimes("beat", bpm, swingRatio, lastMs);

    const noteQualities = [];
    const notes = ons.map((on, i) => {
      const chord = chordAt(input.chart, input.from, input.to, bpm, on.tMs);
      noteQualities.push(chord && chord.quality ? chord.quality : "");
      const tones = chord ? chordTones(chord, byQuality) : { pcs: new Set(), guides: new Set(), scale: new Set() };
      const pc = pcOf(on.note);
      let cls;
      if (tones.pcs.has(pc)) cls = "chord";
      else if (tones.scale.has(pc)) cls = "scale";
      else {
        // An approach note: a semitone from a chord tone, and that chord tone follows within a beat.
        const next = ons[i + 1];
        const neighbours = [pcOf(on.note + 1), pcOf(on.note - 1)].filter((n) => tones.pcs.has(n));
        if (next && next.tMs - on.tMs <= beatMs * APPROACH_BEATS + EPS) {
          cls = neighbours.includes(pcOf(next.note)) && Math.abs(next.note - on.note) === 1 ? "approach" : "outside";
        } else if (next || on.tMs + beatMs * APPROACH_BEATS <= now) {
          cls = "outside";
        } else {
          cls = "pending";
        }
      }
      const timing = nearest(on.tMs, grid);
      const onBeatPoint = nearest(on.tMs, beats);
      const beatInBar = (onBeatPoint.index % beatsPerBar) + 1;
      return {
        tMs: on.tMs,
        note: on.note,
        chord: chord ? chord.name : "",
        bar: chord ? chord.barIndex : null,
        class: cls,
        guide: cls === "chord" && tones.guides.has(pc),
        offsetMs: Math.round(timing.offsetMs),
        within: Math.abs(timing.offsetMs) <= tolerance + EPS,
        beat: beatInBar,
        onBeat: Math.abs(onBeatPoint.offsetMs) <= tolerance + EPS,
      };
    });

    const count = notes.length;
    const pct = (n) => (count ? Math.round((100 * n) / count) : 0);
    const share = (cls) => notes.filter((n) => n.class === cls).length;
    const offsets = notes.map((n) => n.offsetMs);
    const mean = count ? offsets.reduce((a, b) => a + b, 0) / count : null;
    const spread = count > 1 ? Math.sqrt(offsets.reduce((a, b) => a + (b - mean) ** 2, 0) / (count - 1)) : count ? 0 : null;
    const timing = {
      notes: count,
      meanMs: mean === null ? null : Math.round(mean),
      spreadMs: spread === null ? null : Math.round(spread),
      withinPct: pct(notes.filter((n) => n.within).length),
      toleranceMs: tolerance,
      grid: gridKind,
    };
    timing.words = timingWords(timing);

    // The same counts per kind of chord, so a take can say it goes outside over minor chords and
    // not dominant ones. A note still waiting on its approach counts as outside, as above.
    const perQuality = {};
    notes.forEach((n, i) => {
      const symbol = noteQualities[i];
      if (!symbol) return;
      const row = perQuality[symbol] || (perQuality[symbol] = { notes: 0, chord: 0, scale: 0, approach: 0, outside: 0 });
      row.notes += 1;
      row[n.class === "pending" ? "outside" : n.class] += 1;
    });

    const metrics = {
      notes: count,
      ignored,
      chordTonePct: pct(share("chord")),
      scalePct: pct(share("scale")),
      approachPct: pct(share("approach")),
      outsidePct: pct(share("outside") + share("pending")),
      guideTonePct: pct(notes.filter((n) => n.guide).length),
      meanOffsetMs: timing.meanMs,
      spreadMs: timing.spreadMs,
      withinPct: timing.withinPct,
      byQuality: perQuality,
    };

    const scored = scoreFor(scoring, notes, { beatsPerBar, beatMs, from: input.from, to: input.to, tolerance });
    return { version: JUDGE_VERSION, notes, metrics, timing, score: scored.score, scoring: scored.details };
  }

  // ------------------------------------------------------------------- the score

  // Each kind says what it counted beside the score, so a lesson can explain the mark.
  function scoreFor(scoring, notes, ctx) {
    const params = scoring.params || {};
    const share = (n, d) => (d ? Math.round((100 * n) / d) : 0);
    const kind = scoring.kind;

    if (kind === "free_play") return { score: null, details: { kind } };

    // Chord or scale tones. An approach note is outside the scale by definition, and this kind
    // asks the player to stay inside it.
    if (kind === "scale_only") {
      const inside = notes.filter((n) => n.class === "chord" || n.class === "scale").length;
      return { score: share(inside, notes.length), details: { kind, inside, notes: notes.length } };
    }

    // Of the notes that land on the named beats, the share that are chord tones.
    if (kind === "chord_tones_on_beats") {
      const named = namedBeats(params, ctx.beatsPerBar);
      const onNamed = notes.filter((n) => n.onBeat && named.includes(n.beat));
      const chordTones = onNamed.filter((n) => n.class === "chord").length;
      return { score: share(chordTones, onNamed.length), details: { kind, onBeats: onNamed.length, chordTones } };
    }

    // A point for every note that is a third or seventh, and a point for every chord change
    // where the last note before it and the first after it are both guide tones a step apart:
    // that is what "the guide tones connect" means at the piano.
    if (kind === "guide_tones") {
      const step = Number.isFinite(params.step) ? params.step : GUIDE_STEP;
      const guideTones = notes.filter((n) => n.guide).length;
      let changes = 0;
      let connections = 0;
      for (let i = 0; i + 1 < notes.length; i++) {
        if (notes[i].chord === notes[i + 1].chord) continue;
        changes += 1;
        if (notes[i].guide && notes[i + 1].guide && Math.abs(notes[i + 1].note - notes[i].note) <= step) connections += 1;
      }
      return {
        score: share(guideTones + connections, notes.length + changes),
        details: { kind, guideTones, notes: notes.length, connections, changes },
      };
    }

    // The targets are the chord tones that land on the named beats; a target is reached when
    // the note before it was an approach note, which the judge already requires to be a
    // semitone away and within a beat.
    if (kind === "approach_notes") {
      const named = namedBeats(params, ctx.beatsPerBar, [1]);
      let targets = 0;
      let reached = 0;
      notes.forEach((n, i) => {
        if (!(n.onBeat && named.includes(n.beat) && n.class === "chord")) return;
        targets += 1;
        if (i > 0 && notes[i - 1].class === "approach") reached += 1;
      });
      return { score: share(reached, targets), details: { kind, targets, reached } };
    }

    // The pattern is beats inside the bar, repeated every bar played. An onset is matched when
    // a note lands within the tolerance; extra notes count against, because hammering every
    // eighth would otherwise match any pattern.
    if (kind === "rhythm_motif") {
      const pattern = params.pattern;
      const ok =
        Array.isArray(pattern) &&
        pattern.length > 0 &&
        pattern.every((p) => Number.isFinite(p) && p >= 0 && p < ctx.beatsPerBar);
      if (!ok) throw new Error("rhythm_motif needs a pattern: a list of beats inside the bar, from 0");
      const bars = ctx.to - ctx.from;
      const expected = [];
      for (let b = 0; b < bars; b++) for (const p of pattern) expected.push((b * ctx.beatsPerBar + p) * ctx.beatMs);
      const free = notes.map((n) => n.tMs);
      let matched = 0;
      for (const at of expected) {
        let best = -1;
        for (let i = 0; i < free.length; i++) {
          if (free[i] === null) continue;
          if (Math.abs(free[i] - at) <= ctx.tolerance + EPS && (best < 0 || Math.abs(free[i] - at) < Math.abs(free[best] - at))) best = i;
        }
        if (best >= 0) {
          matched += 1;
          free[best] = null;
        }
      }
      return {
        score: share(matched, Math.max(expected.length, notes.length)),
        details: { kind, expected: expected.length, matched, played: notes.length },
      };
    }

    // The answer is what was played in the answer bar. Each onset of the phrase in time is a
    // point; each step of the phrase whose direction the answer follows is a point, or, when
    // exact notes are asked for, each note that is the same note (octaves apart or not).
    if (kind === "call_and_response") {
      const phrase = params.phrase;
      const ok =
        Array.isArray(phrase) &&
        phrase.length > 0 &&
        phrase.every((p) => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && p[0] >= 0 && Number.isInteger(p[1]));
      if (!ok) throw new Error("call_and_response needs a phrase: a list of [beat, note]");
      const answerBar = Number.isInteger(params.answerBar) ? params.answerBar : 1;
      const exact = Boolean(params.exact);
      const start = answerBar * ctx.beatsPerBar * ctx.beatMs;
      const answer = notes.filter((n) => n.bar !== null && n.bar - ctx.from === answerBar);
      const free = answer.map((n) => n.tMs);
      let onsetsMatched = 0;
      for (const [beat] of phrase) {
        const at = start + beat * ctx.beatMs;
        let best = -1;
        for (let i = 0; i < free.length; i++) {
          if (free[i] === null) continue;
          if (Math.abs(free[i] - at) <= ctx.tolerance + EPS && (best < 0 || Math.abs(free[i] - at) < Math.abs(free[best] - at))) best = i;
        }
        if (best >= 0) {
          onsetsMatched += 1;
          free[best] = null;
        }
      }
      const details = { kind, onsets: phrase.length, onsetsMatched, exact };
      let points = phrase.length;
      let earned = onsetsMatched;
      if (exact) {
        let same = 0;
        phrase.forEach(([, note], i) => {
          if (answer[i] && pcOf(answer[i].note) === pcOf(note)) same += 1;
        });
        details.notes = phrase.length;
        details.notesMatched = same;
        points += phrase.length;
        earned += same;
      } else {
        const shapes = Math.max(0, phrase.length - 1);
        let followed = 0;
        for (let i = 0; i + 1 < phrase.length; i++) {
          if (!answer[i] || !answer[i + 1]) continue;
          if (Math.sign(phrase[i + 1][1] - phrase[i][1]) === Math.sign(answer[i + 1].note - answer[i].note)) followed += 1;
        }
        details.shapes = shapes;
        details.shapesMatched = followed;
        points += shapes;
        earned += followed;
      }
      return { score: share(earned, points), details };
    }

    throw new Error(`Unknown scoring kind "${kind}"`);
  }

  function namedBeats(params, beatsPerBar, fallback) {
    if (Array.isArray(params.beats) && params.beats.length) return params.beats;
    return fallback || Array.from({ length: beatsPerBar }, (_, i) => i + 1);
  }

  return { judge, chordAt, gridTimes, toleranceMs, timingWords, JUDGE_VERSION, SCORING_KINDS };
});
