// improv: one lesson, Read, Hear, Play. Browser glue only: draw the explanation, play the demo
// phrase over the lesson's own band, and link each exercise to Play. The rules live in
// lessons.js, play.js, band.js and scheduler.js, which are tested under Node. Only text is ever
// put on the page.
(function () {
  "use strict";
  const L = window.ImprovLessons;
  const P = window.ImprovPlay;
  const Sched = window.ImprovScheduler;
  const Synth = window.ImprovSynth;
  const View = window.ImprovChartView;
  const M = window.ImprovMidi;
  const S = window.ImprovSetup;
  const Timing = window.ImprovTiming;
  const $ = (id) => document.getElementById(id);
  const host = $("lesson");

  const state = {
    lesson: null,
    lessons: [],
    summary: null,
    exercises: [],
    phrase: null,
    progression: null,
    style: null,
    styles: [],
    qualities: [],
    profile: null,
    ctx: null,
    synth: null,
    scheduler: null,
    midi: null,
    hearing: null,
    cells: [],
    frame: 0,
  };

  const say = (text) => ($("lesson-status").textContent = text);

  function showError(text) {
    $("hear-error").textContent = text;
    $("hear-error").hidden = !text;
  }

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  // ------------------------------------------------------------------- read

  function drawInlines(parent, parts) {
    for (const part of parts) {
      if (!part.style) parent.appendChild(document.createTextNode(part.text));
      else parent.appendChild(make(part.style, "", part.text));
    }
  }

  function drawText(source) {
    const box = $("lesson-text");
    box.textContent = "";
    for (const block of L.parseText(source)) {
      if (block.type === "h") {
        box.appendChild(make(block.level === 2 ? "h3" : "h4", "im-h3", block.text));
      } else if (block.type === "p") {
        const p = make("p", "im-prose-p");
        drawInlines(p, block.inlines);
        box.appendChild(p);
      } else {
        const list = make(block.type, "im-prose-list");
        for (const item of block.items) {
          const li = make("li");
          drawInlines(li, item);
          list.appendChild(li);
        }
        box.appendChild(list);
      }
    }
  }

  function drawExercises() {
    const list = $("lesson-exercises");
    list.textContent = "";
    for (const ex of state.exercises) {
      const li = make("li", "im-take");
      li.dataset.slug = ex.slug;
      const head = make("div", "im-take-head");
      head.appendChild(make("span", "im-take-title", ex.title));
      const mark = L.exerciseMark(ex);
      if (mark) head.appendChild(make("span", ex.completed ? "im-state im-state-done" : "im-state", mark));
      li.appendChild(head);
      li.appendChild(make("p", "im-take-summary", ex.instructions));
      li.appendChild(make("p", "im-note", L.exerciseLine(ex)));
      if (!ex.locked) {
        const actions = make("div", "im-card-actions");
        const go = make("a", "im-btn im-btn-link", ex.completed ? "Play it again" : "Play it");
        go.dataset.keyItem = "yes";
        go.href = L.exerciseUrl(host.dataset.playUrl, ex.slug);
        actions.appendChild(go);
        li.appendChild(actions);
      }
      list.appendChild(li);
    }
    $("lesson-no-exercises").hidden = state.exercises.length > 0;
  }

  // ------------------------------------------------------------------- hear

  function ensureAudio() {
    if (state.ctx) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    state.ctx = new Ctx({ latencyHint: "interactive" });
    state.synth = Synth.createSynth(state.ctx);
    state.scheduler = Sched.createScheduler({
      now: () => state.ctx.currentTime,
      setTimer: (fn, ms) => window.setTimeout(fn, ms),
      clearTimer: (h) => window.clearTimeout(h),
      onEvent: (event, when, seconds) => state.synth.play(event, when, seconds),
    });
  }

  async function outputFor() {
    if (!state.profile || state.profile.demo_output !== "piano" || !navigator.requestMIDIAccess) return null;
    try {
      if (!state.midi) state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      return null;
    }
    const choice = S.pickOutput(S.inputChoices(Array.from(state.midi.outputs.values())), state.profile.midi_input_name);
    return choice ? state.midi.outputs.get(choice.id) : null;
  }

  function buildHear() {
    const whole = P.buildPlan({ progression: state.progression, style: state.style, qualities: state.qualities, settings: { key: state.progression.home_key, countIn: 0 } });
    if (!whole.ok) return whole;
    const swing = P.defaultSwingMode(state.style);
    const settings = L.hearSettings(state.phrase, state.progression, whole.chart.bars.length, whole.plan.beatsPerBar, swing);
    const built = P.buildPlan({ progression: state.progression, style: state.style, qualities: state.qualities, settings });
    return built.ok ? { ...built, swing } : built;
  }

  async function startHear() {
    stopHear();
    showError("");
    const built = buildHear();
    if (!built.ok) {
      showError(built.error);
      return;
    }
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    const output = await outputFor();
    const bpm = P.clampTempo(state.style, state.progression.default_tempo);
    const beatSeconds = 60 / bpm;
    const at = state.ctx.currentTime + 0.3;
    const downbeat = at + built.countInBars * built.plan.beatsPerBar * beatSeconds;
    const notes = L.demoNotes(state.phrase, { playedKey: built.key, bpm, swingRatio: P.swingRatioFor(state.style, built.swing), downbeat });
    const bars = built.to - built.from;
    state.scheduler.start(built.plan, { bpm, loop: true, loopFrom: built.loopFrom, at });
    state.hearing = { built, output, notes, sent: false, endsAt: downbeat + bars * built.plan.beatsPerBar * beatSeconds };

    $("hear-status").textContent = `One bar of count-in, then the phrase in ${built.key} at ${bpm} bpm.`;
    $("hear-output").textContent = output ? `The phrase goes to ${output.name} over MIDI.` : "The phrase sounds as a plain tone from the laptop.";
    $("hear-toggle").textContent = "Stop";
    state.cells = View.draw($("hear-chart"), P.layoutBars(built.chart, built.from, built.to));
    if (!output) {
      for (const n of notes) state.synth.play({ voice: "demo", midi: n.note, velocity: n.velocity }, n.when, n.seconds);
      state.hearing.sent = true;
    }
    if (!state.frame) state.frame = requestAnimationFrame(frame);
  }

  // MIDI out needs the anchor between the two clocks, which exists only once sound is coming
  // out; the count-in bar is time enough to get it and send every note with its timestamp.
  function sendToPiano() {
    const h = state.hearing;
    if (!h || h.sent || !h.output) return;
    let anchor;
    try {
      anchor = Timing.makeAnchor(state.ctx.getOutputTimestamp());
    } catch (e) {
      return;
    }
    for (const n of h.notes) {
      h.output.send(M.noteOnBytes(n.note, n.velocity), Timing.heardAt(anchor, n.when));
      h.output.send(M.noteOffBytes(n.note), Timing.heardAt(anchor, n.when + n.seconds));
    }
    h.sent = true;
  }

  function frame() {
    state.frame = 0;
    const h = state.hearing;
    if (!h) return;
    sendToPiano();
    const now = state.ctx.currentTime;
    if (now >= h.endsAt) {
      stopHear();
      $("hear-status").textContent = "Done. Hear it again, or play it.";
      return;
    }
    const lit = P.litFor(h.built, state.scheduler.barAt(now));
    for (const c of state.cells) if (c) c.el.classList.remove("im-bar-lit");
    if (lit && !lit.countIn && state.cells[lit.bar]) {
      const c = state.cells[lit.bar];
      c.el.classList.add("im-bar-lit");
      c.beat.style.width = Math.min(100, (lit.beat / h.built.plan.beatsPerBar) * 100) + "%";
    }
    state.frame = requestAnimationFrame(frame);
  }

  function stopHear() {
    if (state.scheduler) state.scheduler.stop();
    if (state.frame) cancelAnimationFrame(state.frame);
    state.frame = 0;
    if (state.hearing && state.hearing.output) {
      for (const n of state.hearing.notes) state.hearing.output.send(M.noteOffBytes(n.note));
    }
    state.hearing = null;
    for (const c of state.cells) if (c) c.el.classList.remove("im-bar-lit");
    $("hear-toggle").textContent = "Hear it";
  }

  // ------------------------------------------------------------------ start

  function ready() {
    $("lesson-title").textContent = state.lesson.title;
    $("lesson-meta").textContent = `${L.trackLabel(state.lesson.track)}. ${L.describe(state.lesson, state.lessons)}`;
    $("lesson-level").textContent = L.levelLine(state.summary);
    const locked = state.lesson.state === "locked";
    $("lesson-lock").textContent = locked ? L.lockedReason(state.lesson, state.lessons) + " You can read and hear it now; plays count once it is open." : "";
    $("lesson-lock").hidden = !locked;
    const note = L.authorshipNote(state.lesson);
    $("lesson-authorship").textContent = note;
    $("lesson-authorship").hidden = !note;
    drawText(state.lesson.explanation);
    drawExercises();
    $("lesson-body").hidden = false;
    const hearable = state.phrase && state.progression && state.style;
    $("hear-toggle").disabled = !hearable;
    $("hear-status").textContent = hearable ? "Press Hear it to listen to the idea over the band." : "This lesson has no demo to hear yet.";
    $("hear-toggle").addEventListener("click", () => {
      if (state.hearing) {
        stopHear();
        $("hear-status").textContent = "Stopped.";
      } else startHear().catch((e) => showError("The sound could not start: " + e.message));
    });
    window.addEventListener("pagehide", stopHear);
    say(state.exercises.length ? "Read it, hear it, then play it." : "Read it and hear it.");
  }

  async function init() {
    const slug = host.dataset.lesson;
    try {
      const [lessons, exercises, phrases, progressions, styles, qualities, profile] = await Promise.all([
        getJson(host.dataset.apiLessons),
        getJson(host.dataset.apiExercises + "?lesson=" + encodeURIComponent(slug)),
        getJson(host.dataset.apiPhrases),
        getJson(host.dataset.apiProgressions),
        getJson(host.dataset.apiStyles),
        getJson(host.dataset.apiQualities),
        getJson(host.dataset.apiPlayer),
      ]);
      state.lessons = lessons;
      state.lesson = lessons.find((l) => l.slug === slug) || null;
      state.exercises = exercises;
      state.summary = await getJson(host.dataset.apiSummary).catch(() => null);
      state.styles = styles;
      state.qualities = qualities;
      state.profile = profile;
      if (state.lesson) {
        state.phrase = phrases.find((p) => p.id === state.lesson.demo_phrase) || null;
        state.progression = progressions.find((p) => p.id === state.lesson.progression) || null;
        state.style = (state.progression && (styles.find((s) => s.id === state.lesson.style) || P.pickStyle(state.progression, styles))) || null;
      }
    } catch (e) {
      say("The lesson could not be loaded. " + e.message);
      return;
    }
    if (!state.lesson) {
      $("lesson-title").textContent = "No such lesson";
      say("There is no lesson by that name.");
      return;
    }
    ready();
  }

  if (!L || !P || !Sched || !Synth || !View || !M || !S || !Timing) say("The page's scripts did not load.");
  else init();
})();
