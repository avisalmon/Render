// improv: the rules behind the Lessons screens. Pure: no browser, runs under Node in the tests.
//
// A lesson is Read, Hear, Play. This file groups lessons by track, turns the explanation into
// blocks the page can draw as text, and turns a demo phrase into notes to sound over the band
// in the key the lesson is played in. It never builds markup, so nothing a lesson says can
// become anything but text on the page.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./chart.js"), require("./band.js"));
  else root.ImprovLessons = factory(root.ImprovChart, root.ImprovBand);
})(typeof self !== "undefined" ? self : this, function (chart, band) {
  // The order a player meets the tracks in. improv/teaching.py holds the same list; a test compares them.
  const TRACKS = [
    ["chord_tones", "Chord tones"],
    ["guide_tones", "Guide tones"],
    ["scales_modes", "Scales and modes"],
    ["approach_notes", "Approach notes"],
    ["rhythm_motifs", "Rhythm motifs"],
    ["call_and_response", "Call and response"],
    ["voicings_comping", "Voicings and comping"],
  ];
  const LEVELS = { 1: "Level 1", 2: "Level 2", 3: "Level 3" };
  const HEAR_COUNT_IN = 1;
  const MOST_BARS_HEARD = 16;

  function trackLabel(slug) {
    const found = TRACKS.find((t) => t[0] === slug);
    return found ? found[1] : slug;
  }

  // Lessons as the API gives them (already in track order) grouped under their track, tracks
  // with nothing in them left out.
  function groupByTrack(lessons) {
    const groups = [];
    for (const [slug, label] of TRACKS) {
      const own = (lessons || []).filter((l) => l.track === slug).sort((a, b) => a.order - b.order);
      if (own.length) groups.push({ track: slug, label, lessons: own });
    }
    const known = new Set(TRACKS.map((t) => t[0]));
    const rest = (lessons || []).filter((l) => !known.has(l.track));
    if (rest.length) groups.push({ track: "other", label: "Other", lessons: rest });
    return groups;
  }

  // "Level 1, after Guide tones." for the card's small line.
  function describe(lesson, lessons) {
    const parts = [LEVELS[lesson.level] || `Level ${lesson.level}`];
    const before = lesson.prerequisite && (lessons || []).find((l) => l.slug === lesson.prerequisite);
    if (before) parts.push(`after ${before.title}`);
    if (lesson.status === "draft") parts.push("draft, only you can see it");
    return parts.join(", ") + ".";
  }

  // What the page says about who wrote a lesson, so a draft nobody has read is never passed off as taught.
  function authorshipNote(lesson) {
    if (lesson.authorship === "avi_written") return "";
    if (lesson.authorship === "reviewed") return "Drafted by AI, then read and corrected.";
    return "Drafted by AI and not yet read by a person. Treat it as a draft.";
  }

  // ------------------------------------------------------------------ the text
  //
  // A small slice of markdown: ## and ### headings, paragraphs, "- " and "1. " lists, and
  // **bold**, *italic* and `code` inside a line. Anything else is plain text.

  function inlines(text) {
    const out = [];
    const pattern = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`/g;
    let last = 0;
    let m;
    while ((m = pattern.exec(text))) {
      if (m.index > last) out.push({ text: text.slice(last, m.index), style: null });
      if (m[1] !== undefined) out.push({ text: m[1], style: "strong" });
      else if (m[2] !== undefined) out.push({ text: m[2], style: "em" });
      else out.push({ text: m[3], style: "code" });
      last = m.index + m[0].length;
    }
    if (last < text.length) out.push({ text: text.slice(last), style: null });
    return out;
  }

  function parseText(source) {
    const blocks = [];
    let open = null;
    let paragraph = [];
    const closeParagraph = () => {
      if (paragraph.length) blocks.push({ type: "p", inlines: inlines(paragraph.join(" ")) });
      paragraph = [];
    };
    const closeList = () => {
      open = null;
    };
    for (const raw of String(source || "").replace(/\r\n?/g, "\n").split("\n")) {
      const line = raw.trim();
      const heading = /^(#{2,3})\s+(.+)$/.exec(line);
      const bullet = /^[-*]\s+(.+)$/.exec(line);
      const numbered = /^\d+[.)]\s+(.+)$/.exec(line);
      if (!line) {
        closeParagraph();
        closeList();
      } else if (heading) {
        closeParagraph();
        closeList();
        blocks.push({ type: "h", level: heading[1].length, text: heading[2] });
      } else if (bullet || numbered) {
        closeParagraph();
        const type = bullet ? "ul" : "ol";
        if (!open || open.type !== type) {
          open = { type, items: [] };
          blocks.push(open);
        }
        open.items.push(inlines((bullet || numbered)[1]));
      } else {
        closeList();
        paragraph.push(line);
      }
    }
    closeParagraph();
    return blocks;
  }

  // ------------------------------------------------------------------- the demo

  // Semitones from the key the phrase was written in to the key it is played in, the short way round.
  function transposeBy(writtenKey, playedKey) {
    const from = chart.parseKey(writtenKey || "C");
    const to = chart.parseKey(playedKey || writtenKey || "C");
    if (!from || !to) return 0;
    const up = (((to.pc - from.pc) % 12) + 12) % 12;
    return up > 6 ? up - 12 : up;
  }

  // The notes of a phrase as notes to sound: when (audio seconds), how long, how loud (0 to 1),
  // moved to the key it is played in and swung the way the band swings, so an eighth note in the
  // phrase lands where the band's eighth lands. `downbeat` is the audio time of the phrase's beat 0.
  function demoNotes(phrase, options) {
    const o = options || {};
    const shift = transposeBy(phrase.written_in_key, o.playedKey);
    const ratio = Number.isFinite(o.swingRatio) ? o.swingRatio : 0.5;
    const beatSeconds = 60 / o.bpm;
    return (phrase.notes || [])
      .map((n) => {
        const start = band.swingBeat(n.beat, ratio);
        const end = band.swingBeat(n.beat + n.length, ratio);
        return {
          note: Math.min(127, Math.max(0, n.midi + shift)),
          when: o.downbeat + start * beatSeconds,
          seconds: Math.max(0.05, (end - start) * beatSeconds),
          velocity: Math.min(1, Math.max(0.05, n.velocity / 127)),
        };
      })
      .sort((a, b) => a.when - b.when || a.note - b.note);
  }

  // The Play settings that put the band under the demo: the lesson's own chart in its home key,
  // from the first bar for as many bars as the phrase lasts, never past the end of the chart.
  function hearSettings(phrase, progression, barCount, beatsPerBar, swing) {
    const length = phrase ? Number(phrase.length_beats) : 0;
    const wanted = Math.max(1, Math.ceil(length / beatsPerBar));
    const last = Math.min(barCount, MOST_BARS_HEARD, wanted);
    return {
      key: progression.home_key,
      countIn: HEAR_COUNT_IN,
      first: "1",
      last: String(last),
      swing: swing || "swing",
      metronome: false,
    };
  }

  // ------------------------------------------------------------------ progress

  // The small tag on a lesson card: where the player stands in it. A lesson with nothing to play
  // is only read, so it carries none.
  function stateLabel(lesson) {
    if (lesson.state === "locked") return "Locked";
    if (!lesson.exercises_total) return "";
    if (lesson.state === "done") return "Done";
    return `${lesson.exercises_done} of ${lesson.exercises_total} passed`;
  }

  // Why a lesson is shut, naming the lesson that opens it.
  function lockedReason(lesson, lessons) {
    const before = lesson.prerequisite && (lessons || []).find((l) => l.slug === lesson.prerequisite);
    return before ? `Pass every exercise in ${before.title} to open this.` : "Pass the lesson before this one to open it.";
  }

  // The one line the Lessons screen leads with: level, XP, and what the next level asks.
  function levelLine(summary) {
    if (!summary) return "";
    const head = `Level ${summary.level}, ${summary.xp} XP`;
    if (summary.next_level_at === null || summary.next_level_at === undefined) return head + ".";
    return `${head}. ${summary.next_level_at - summary.xp} XP to level ${summary.level + 1}.`;
  }

  function lessonsDoneLine(summary) {
    if (!summary || !summary.lessons_total) return "";
    return `${summary.lessons_done} of ${summary.lessons_total} ${summary.lessons_total === 1 ? "lesson" : "lessons"} done.`;
  }

  // The mark on an exercise: passed, locked, or nothing yet.
  function exerciseMark(exercise) {
    if (exercise.completed) return "Passed";
    if (exercise.locked) return "Locked";
    return "";
  }

  // ------------------------------------------------------------------ the exercises

  function exerciseLine(exercise) {
    const bars = `${exercise.bars} ${exercise.bars === 1 ? "bar" : "bars"}`;
    return `${bars} in ${exercise.key} at ${exercise.tempo} bpm. Pass at ${exercise.pass_score}, worth ${exercise.xp} XP.`;
  }

  function exerciseUrl(playUrl, slug) {
    return `${playUrl}?exercise=${encodeURIComponent(slug)}`;
  }

  return {
    TRACKS,
    trackLabel,
    groupByTrack,
    describe,
    authorshipNote,
    parseText,
    transposeBy,
    demoNotes,
    hearSettings,
    stateLabel,
    lockedReason,
    levelLine,
    lessonsDoneLine,
    exerciseMark,
    exerciseLine,
    exerciseUrl,
    HEAR_COUNT_IN,
  };
});
