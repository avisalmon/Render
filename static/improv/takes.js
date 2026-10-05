// improv: the rules behind the Takes screen. Pure: no browser, runs under Node in the tests.
//
// A take is replayed from its own snapshot and nothing else: the chart text, the key it is
// written in, the key it was played in, the bar length, the tempo and the feel are all in
// the row, so a progression edited or deleted since cannot change what is heard.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovTakes = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const REPLAY_COUNT_IN = 1;
  const UNMATCHED_SECONDS = 0.5;
  const LONGEST_NOTE_SECONDS = 20;

  // The progression a take is replayed as: made of the take's own snapshot.
  function replayProgression(take, title) {
    return {
      id: take.progression,
      title: title || "Free chart",
      chart: take.chart,
      home_key: take.home_key,
      time_signature: take.time_signature,
      default_tempo: take.tempo,
    };
  }

  // The Play settings that put the band back where it was: the key, the bars, the feel.
  function replaySettings(take) {
    return {
      key: take.key,
      countIn: REPLAY_COUNT_IN,
      first: String(take.loop_from + 1),
      last: String(take.loop_to),
      swing: Number(take.swing_ratio) > 0.5 ? "swing" : "straight",
      metronome: false,
    };
  }

  // Note-ons paired with their note-offs, as notes to sound: when (ms from the first judged
  // downbeat), how long, how loud (0 to 1). A note never let go is held for a moment and
  // dropped; a note-off with no note-on is nothing.
  function noteSpans(events) {
    const open = new Map();
    const spans = [];
    for (const e of events || []) {
      if (!e || !Number.isFinite(e.t_ms) || !Number.isInteger(e.note)) continue;
      if (e.type === "on") {
        if (open.has(e.note)) finish(open.get(e.note), e.t_ms);
        const span = { note: e.note, atMs: e.t_ms, seconds: UNMATCHED_SECONDS, velocity: Math.min(1, Math.max(0.05, (e.velocity || 0) / 127)) };
        open.set(e.note, span);
        spans.push(span);
      } else if (e.type === "off" && open.has(e.note)) {
        finish(open.get(e.note), e.t_ms);
        open.delete(e.note);
      }
    }
    return spans.sort((a, b) => a.atMs - b.atMs || a.note - b.note);

    function finish(span, endMs) {
      span.seconds = Math.min(LONGEST_NOTE_SECONDS, Math.max(0.05, (endMs - span.atMs) / 1000));
    }
  }

  // The audio-clock moment each note sounds, given where the first judged downbeat falls.
  function scheduleAt(spans, downbeatAudio) {
    return spans.map((s) => ({ ...s, when: downbeatAudio + s.atMs / 1000 }));
  }

  // How long the replay runs: the last note let go, rounded up to a whole bar, plus one.
  function replayBars(take, spans) {
    const beatMs = 60000 / take.tempo;
    const beats = Number(String(take.time_signature).split("/")[0]) || 4;
    const barMs = beatMs * beats;
    const lastMs = spans.reduce((m, s) => Math.max(m, s.atMs + s.seconds * 1000), take.duration_ms || 0);
    return Math.max(take.bars, Math.ceil(lastMs / barMs)) + 1;
  }

  // ------------------------------------------------------------------ the list

  function describe(take, options) {
    const opts = options || {};
    const title = opts.titles && opts.titles[take.progression] ? opts.titles[take.progression] : "Free chart";
    const notes = take.metrics && Number.isFinite(take.metrics.notes) ? take.metrics.notes : countOns(take.events);
    const when = formatWhen(take.started_at, opts.now);
    const feel = Number(take.swing_ratio) > 0.5 ? "swing" : "straight";
    return {
      id: take.id,
      title,
      when,
      summary: `${take.key}, ${take.tempo} bpm, ${feel}, ${take.bars} ${take.bars === 1 ? "bar" : "bars"}`,
      notes,
      verdict: verdictWords(take),
      kept: Boolean(take.is_kept),
      score: take.score,
    };
  }

  function countOns(events) {
    return (events || []).filter((e) => e && e.type === "on").length;
  }

  function verdictWords(take) {
    const m = take.metrics || {};
    const parts = [];
    if (Number.isFinite(m.chordTonePct)) parts.push(`${m.chordTonePct}% chord tones`);
    if (Number.isFinite(m.outsidePct) && m.outsidePct) parts.push(`${m.outsidePct}% outside`);
    if (Number.isFinite(m.meanOffsetMs) && m.meanOffsetMs !== null) {
      const mean = Math.round(m.meanOffsetMs);
      parts.push(Math.abs(mean) <= 5 ? "on the beat" : mean < 0 ? `rushing by ${-mean} ms` : `dragging by ${mean} ms`);
    }
    if (take.score !== null && take.score !== undefined) parts.unshift(`score ${take.score}`);
    return parts.join(", ") || "no notes";
  }

  // "Today 14:05", "Yesterday 09:30", else the date.
  function formatWhen(iso, now) {
    const at = new Date(iso);
    if (Number.isNaN(at.getTime())) return "";
    const ref = now ? new Date(now) : new Date();
    const day = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    const yesterday = new Date(ref.getTime() - 24 * 3600 * 1000);
    const time = `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
    if (day(at) === day(ref)) return `Today ${time}`;
    if (day(at) === day(yesterday)) return `Yesterday ${time}`;
    return `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, "0")}-${String(at.getDate()).padStart(2, "0")} ${time}`;
  }

  // Newest first, kept ones unaffected: the list is a log, not a ranking.
  function order(takes) {
    return [...(takes || [])].sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
  }

  // A take not kept loses its notes after thirty days (the server clears them). It keeps its score.
  function cleared(take) {
    return !take || !Array.isArray(take.events) || take.events.length === 0;
  }

  function clearedNote(take) {
    return cleared(take) && !take.is_kept ? "The notes were cleared after 30 days. The score stays." : "";
  }

  return {
    cleared,
    clearedNote,
    replayProgression,
    replaySettings,
    noteSpans,
    scheduleAt,
    replayBars,
    describe,
    order,
    formatWhen,
    REPLAY_COUNT_IN,
  };
});
