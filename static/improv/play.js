// improv: the Play screen's logic, with no page in it. Settings go in, a playable plan and
// a chart layout come out. The page (play-page.js) only reads the controls, calls this,
// and draws the answer, so every rule below is tested under Node.
//
//   const built = ImprovPlay.buildPlan({ progression, style, qualities, settings });
//   if (!built.ok) show(built.error);
//   scheduler.start(built.plan, { bpm: settings.bpm, loopFrom: built.loopFrom });
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./chart.js"), require("./band.js"));
  } else root.ImprovPlay = factory(root.ImprovChart, root.ImprovBand);
})(typeof self !== "undefined" ? self : this, function (chart, band) {
  const MAX_COUNT_IN = 2;
  const FALLBACK_SWING = 0.62;
  const PER_ROW = 4;

  function beatsPerBarOf(signature) {
    const m = /^(\d+)\/4$/.exec(signature || "");
    return m ? Number(m[1]) : null;
  }

  function swingRatioOf(style) {
    const ratio = Number(style && style.swing_ratio);
    return ratio >= 0.5 && ratio <= 0.75 ? ratio : 0.5;
  }

  // "swing" uses the groove's own ratio, or a medium one when the groove is straight;
  // "straight" takes the swing out of any groove.
  function swingRatioFor(style, mode) {
    if (mode === "straight") return 0.5;
    const own = swingRatioOf(style);
    return own > 0.5 ? own : FALLBACK_SWING;
  }

  function defaultSwingMode(style) {
    return swingRatioOf(style) > 0.5 ? "swing" : "straight";
  }

  function clampTempo(style, bpm) {
    const low = Math.max(20, Number(style && style.min_tempo) || 20);
    const high = Math.min(300, Number(style && style.max_tempo) || 300);
    const value = bpm === null || bpm === undefined || String(bpm).trim() === "" ? NaN : Math.round(Number(bpm));
    if (!Number.isFinite(value)) return Math.min(high, Math.max(low, Number(style && style.default_tempo) || 100));
    return Math.min(high, Math.max(low, value));
  }

  // The style the progression asks for, or the first one that fits its bar length.
  function pickStyle(progression, styles) {
    const list = styles || [];
    const wanted = list.find((s) => s.id === progression.default_style);
    if (wanted) return wanted;
    return list.find((s) => s.time_signature === progression.time_signature) || null;
  }

  // The twelve keys, in the quality (major or minor) of the progression's home key, with
  // the home key's own spelling kept as written.
  function keyOptions(homeKey) {
    const home = chart.parseKey(homeKey);
    const suffix = home && home.minor ? "m" : "";
    const names = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
    const list = names.map((n) => n + suffix);
    if (home && !list.includes(home.name)) {
      const i = list.findIndex((n) => chart.parseKey(n).pc === home.pc);
      list[i] = home.name;
    }
    return list;
  }

  function defaultSettings(progression, style) {
    return {
      key: progression.home_key,
      bpm: clampTempo(style, progression.default_tempo || (style && style.default_tempo)),
      swing: defaultSwingMode(style),
      first: null,
      last: null,
      countIn: 1,
      metronome: false,
    };
  }

  // The bar range the player typed, 1-based and inclusive, into the 0-based half-open
  // range the band wants. Blank on both sides means the whole chart.
  function rangeOf(first, last, count) {
    const blank = (v) => v === null || v === undefined || v === "";
    if (blank(first) && blank(last)) return { ok: true, from: 0, to: count, whole: true };
    const a = blank(first) ? 1 : Number(first);
    const b = blank(last) ? count : Number(last);
    if (!Number.isInteger(a) || !Number.isInteger(b)) return { ok: false, error: "Bar numbers are whole numbers." };
    if (a < 1 || b < 1 || a > count || b > count) return { ok: false, error: `This chart has bars 1 to ${count}.` };
    if (a > b) return { ok: false, error: "The first bar of the loop comes before the last." };
    return { ok: true, from: a - 1, to: b, whole: a === 1 && b === count };
  }

  function clickBar(index, beats, countIn) {
    const events = [];
    for (let b = 0; b < beats; b++) events.push({ voice: "click", beat: b, beats: 0.1, velocity: b === 0 ? 1 : 0.65, accent: b === 0 });
    return { index, source: null, beats, countIn, events };
  }

  function countInBars(count, beats) {
    const bars = [];
    for (let i = 0; i < count; i++) bars.push(clickBar(i, beats, true));
    return bars;
  }

  // Everything the page needs to start a take, or the reason it cannot.
  //
  //   plan       bars for the scheduler: the count-in first, then the chosen range
  //   loopFrom   the bar the scheduler returns to after the last one (past the count-in)
  //   chart      the parsed chart in the chosen key, for drawing
  //   from, to   the range in played bars
  function buildPlan({ progression, style, qualities, settings }) {
    const beatsPerBar = beatsPerBarOf(progression && progression.time_signature);
    if (!beatsPerBar) return { ok: false, error: `The band cannot play ${progression && progression.time_signature}.` };
    const parsed = chart.parseChart(progression.chart, qualities, { beatsPerBar, homeKey: progression.home_key });
    if (!parsed.ok) {
      const e = parsed.error;
      return { ok: false, error: `${e.message} (line ${e.line}, column ${e.column})` };
    }
    let shown = parsed;
    const key = settings.key || progression.home_key;
    if (!chart.parseKey(key)) return { ok: false, error: `"${key}" is not a key.` };
    if (key !== progression.home_key) shown = chart.transposeToKey(parsed, progression.home_key, key);

    const range = rangeOf(settings.first, settings.last, shown.bars.length);
    if (!range.ok) return { ok: false, error: range.error };

    let core;
    if (settings.metronome) {
      core = shown.bars.slice(range.from, range.to).map((_, i) => clickBar(i, beatsPerBar, false));
    } else {
      const planned = band.planBand(shown, style, qualities, {
        swingRatio: swingRatioFor(style, settings.swing),
        from: range.from,
        to: range.to,
        loop: true,
      });
      if (!planned.ok) return { ok: false, error: planned.error };
      core = planned.bars;
    }

    const lead = Math.min(MAX_COUNT_IN, Math.max(0, Math.round(Number(settings.countIn) || 0)));
    const bars = [...countInBars(lead, beatsPerBar), ...core.map((b, i) => ({ ...b, index: lead + i, countIn: false }))];
    return {
      ok: true,
      plan: { ok: true, beatsPerBar, bars },
      loopFrom: lead,
      countInBars: lead,
      chart: shown,
      from: range.from,
      to: range.to,
      key,
      metronome: Boolean(settings.metronome),
    };
  }

  // What may change while it plays, and what may not. A change goes live only if the take
  // keeps its shape (the same bars, the same count-in, the same loop), so the place in the
  // loop is still the place; everything that would reshape it stays locked until Stop.
  // A note's time on the take's own clock: milliseconds from the first judged downbeat, which
  // is the start of the first bar after the count-in. The count-in is negative time, so the
  // judge can leave it out; the second time round the loop carries on counting.
  function takeTimeMs(position, built, bpm) {
    if (!position || !built || !built.plan) return null;
    const beatsPerBar = built.plan.beatsPerBar;
    const lead = built.countInBars || 0;
    const loopBars = built.plan.bars.length - lead;
    const bars = position.pass * loopBars + (position.index - lead);
    return (bars * beatsPerBar + position.beat) * (60000 / bpm);
  }

  // The colour a judged note gets on the keys (spec ch. 5): chord tones green with the guide
  // tones brighter, scale tones blue, approach notes amber, outside red and soft.
  const KEY_CLASSES = {
    chord: "im-key-chord",
    guide: "im-key-guide",
    scale: "im-key-scale",
    approach: "im-key-approach",
    pending: "im-key-pending",
    outside: "im-key-outside",
  };

  function keyClassFor(note) {
    if (!note) return "im-key-on";
    if (note.class === "chord") return note.guide ? KEY_CLASSES.guide : KEY_CLASSES.chord;
    return KEY_CLASSES[note.class] || "im-key-on";
  }

  function liveSummary(judged) {
    const m = judged.metrics;
    if (!m.notes) return "Play something.";
    const parts = [`${m.notes} ${m.notes === 1 ? "note" : "notes"}`, `${m.chordTonePct}% chord tones`];
    if (m.scalePct) parts.push(`${m.scalePct}% scale tones`);
    if (m.approachPct) parts.push(`${m.approachPct}% approach notes`);
    if (m.outsidePct) parts.push(`${m.outsidePct}% outside`);
    return `${parts.join(", ")}. ${judged.timing.words.charAt(0).toUpperCase()}${judged.timing.words.slice(1)}.`;
  }

  const LIVE_CONTROLS = ["style", "key", "bpm", "swing"];
  const LOCKED_CONTROLS = ["progression", "countin", "first", "last", "metronome"];

  function canGoLive(current, next) {
    if (!current || !next || !current.ok || !next.ok) return false;
    return (
      current.plan.bars.length === next.plan.bars.length &&
      current.plan.beatsPerBar === next.plan.beatsPerBar &&
      current.loopFrom === next.loopFrom &&
      current.countInBars === next.countInBars &&
      current.from === next.from &&
      current.to === next.to &&
      current.metronome === next.metronome
    );
  }

  // What the screen lights for a scheduler position { index, pass, beat }.
  function litFor(built, position) {
    if (!position) return null;
    const bar = built.plan.bars[position.index];
    if (!bar) return null;
    if (bar.countIn) return { countIn: true, number: position.index + 1, of: built.countInBars, beat: position.beat, bar: null, pass: 0 };
    return { countIn: false, bar: built.from + (bar.index - built.countInBars), beat: position.beat, pass: position.pass };
  }

  // The chart as rows of bars for drawing: chord names, the written bar number, the key
  // when it changes, and whether the bar is inside the loop.
  function layoutBars(parsed, from, to) {
    let lastKey = null;
    const cells = parsed.bars.map((bar, i) => {
      const keyName = bar.key ? bar.key.name : null;
      const keyChange = keyName !== null && keyName !== lastKey && lastKey !== null ? keyName : null;
      lastKey = keyName !== null ? keyName : lastKey;
      return {
        index: i,
        number: i + 1,
        chords: bar.chords.map((c) => c.name),
        keyChange,
        inLoop: i >= from && i < to,
        pass: bar.pass,
      };
    });
    const rows = [];
    for (let i = 0; i < cells.length; i += PER_ROW) rows.push(cells.slice(i, i + PER_ROW));
    return rows;
  }

  // ------------------------------------------------------------ exercises (SPR-I.5.1)
  //
  // Play can be opened for an exercise: the chart, key, tempo and bars it asks for, scored the
  // way it asks. A take counts for the exercise only while the player is still playing what it
  // asked for; change the chart or the bars and it is free play again.

  function exerciseScoring(exercise, kinds) {
    if (!exercise || !(kinds || []).includes(exercise.scoring_kind)) return { kind: "free_play", params: {} };
    return { kind: exercise.scoring_kind, params: exercise.scoring_params || {} };
  }

  // The loop the exercise asks for: from bar 1, as many bars as it says, never past the chart.
  function exerciseRange(exercise, barCount) {
    return { first: "1", last: String(Math.max(1, Math.min(exercise.bars, barCount))) };
  }

  function exerciseApplies(exercise, progression, built) {
    if (!exercise || !progression || !built || !built.ok || built.metronome) return false;
    return progression.id === exercise.progression && built.from === 0 && built.to === Math.min(exercise.bars, built.chart.bars.length);
  }

  function exerciseVerdict(score, passScore) {
    if (score === null || score === undefined) return "";
    return score >= passScore ? `Score ${score}. That passes (${passScore} needed).` : `Score ${score}. ${passScore} needed to pass.`;
  }

  // The line under the exercise's name: what it asks, or why this play-through is not it.
  // `applies` is exerciseApplies for what is on the screen now.
  function exerciseGoalLine(exercise, applies) {
    if (!applies) return "You changed the chart or the bars, so this is free play and will not count for the exercise.";
    const ask = `${exercise.bars} ${exercise.bars === 1 ? "bar" : "bars"}, pass at ${exercise.pass_score}`;
    if (exercise.ahead) return `${ask}. This lesson builds on one you have not finished; a take here counts all the same, and Today will follow you here.`;
    if (exercise.completed) return `${ask}. You have passed this one already, so it earns no more XP.`;
    return `${ask}, worth ${exercise.xp} XP.`;
  }

  // What the server says about a take it has just saved: the XP it earned, if it earned any.
  function completionNote(saved) {
    const done = saved && saved.completion;
    return done ? `Passed. +${done.xp_awarded} XP.` : "";
  }

  return {
    exerciseScoring,
    exerciseRange,
    exerciseApplies,
    exerciseVerdict,
    exerciseGoalLine,
    completionNote,
    buildPlan,
    litFor,
    layoutBars,
    takeTimeMs,
    keyClassFor,
    liveSummary,
    KEY_CLASSES,
    canGoLive,
    LIVE_CONTROLS,
    LOCKED_CONTROLS,
    rangeOf,
    clampTempo,
    pickStyle,
    defaultSettings,
    defaultSwingMode,
    keyOptions,
    swingRatioFor,
    countInBars,
    clickBar,
    MAX_COUNT_IN,
    PER_ROW,
  };
});
