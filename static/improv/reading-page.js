// improv: the Reading screen. Browser glue only: the stage, the tempo, the mode, a count-in click, the
// piano's notes against the clock, and the judge's answer drawn on the staff. The rules (the ladder of
// stages, the generator, the judge, the words) live in reading.js, which is tested under Node, and the
// drawing in staff-view.js. Only text is ever put on the page.
(function () {
  "use strict";
  const R = window.ImprovReading;
  const Staff = window.ImprovStaffView;
  const Keys = window.ImprovKeyboardView;
  const Input = window.ImprovInput;
  const Timing = window.ImprovTiming;
  const Synth = window.ImprovSynth;
  const Midi = window.ImprovMidi;
  const Setup = window.ImprovSetup;
  const $ = (id) => document.getElementById(id);
  const host = $("reading");
  const TICK_MS = 25;
  const AHEAD_S = 0.2;
  const LEAD_S = 0.3;
  const TAIL_MS = 200;
  const COUNT_IN_BEATS = 4;
  const SHOW_ME_BEATS = 1;

  const state = {
    profile: null,
    report: null,
    takes: [],
    stage: null,
    exercise: null,
    layout: null,
    keys: null,
    keyRange: null,
    mode: "idle", // idle | running | showing | over
    kind: "flow",
    range: null,
    ctx: null,
    synth: null,
    anchor: null,
    startAudio: 0,
    nextBeat: 0,
    beats: 0,
    events: [],
    held: [],
    judged: null,
    step: null,
    timer: null,
    midi: null,
    listening: null,
    tempoSaved: R.TEMPO_DEFAULT,
    pendingStage: false,
  };

  const say = (text) => ($("rd-status").textContent = text);

  function make(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  async function send(method, url, body) {
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      keepalive: true,
      headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": host.dataset.csrf },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  const spelling = () => (state.profile ? state.profile.note_names : "sharps");
  const tempo = () => R.clampTempo($("rd-tempo").value);
  const beatMs = () => 60000 / tempo();
  const curtainOn = () => $("rd-curtain").checked;
  const chosenStage = () => R.stageOf(R.stageIndex($("rd-key").value, $("rd-hands").value));

  // --------------------------------------------------------------- the exercise on the screen

  const newSeed = () => (Date.now() ^ (Math.random() * 0x7fffffff)) >>> 0;

  // The seed names the piece. It stays through a change of hands (and a pass to the next hand), so the
  // piece practised with one hand is the piece played with both; only Next or a new visit changes it.
  function fresh(seed) {
    if (state.mode === "running" || state.mode === "showing") return;
    state.pendingStage = false;
    state.stage = chosenStage();
    state.range = null;
    state.judged = null;
    state.step = null;
    const focus = state.report && state.report.focus ? state.report.focus : [];
    const keep = seed === undefined && state.exercise ? state.exercise.seed : seed;
    state.exercise = R.generate(state.stage, keep === undefined ? newSeed() : keep, focus);
    const key = state.exercise.key;
    state.layout = Staff.draw($("rd-staff"), state.exercise, {
      right: "right hand",
      left: "left hand",
      key: `${key} major`,
      signature: R.keyWords(key),
    });
    wireHover();
    drawKeyboard();
    lightKeys();
    host.dataset.stage = String(state.stage.index);
    host.dataset.seed = String(state.exercise.seed);
    host.dataset.saved = "no";
    const active = R.activeNotes(state.exercise).length;
    $("rd-name").textContent = state.stage.hands === "B"
      ? `${R.stageTitle(state.stage)}, ${active} notes in ${state.exercise.bars} bars`
      : `${R.stageTitle(state.stage)}, ${active} notes in ${state.exercise.bars} bars; the other hand is shown, not asked for`;
    $("rd-stage-line").textContent = R.stageLine(state.report, state.stage);
    $("rd-work").textContent = R.workWords(state.report);
    clearResult();
    line();
  }

  function line() {
    const mode = $("rd-mode").value === "step" ? "Step: it waits for you" : "Flow: four clicks, then the pulse never waits";
    $("rd-line").textContent = `${tempo()} bpm, ${mode}. ${curtainOn() ? "The curtain hides what is behind the cursor." : ""}`.trim();
  }

  function drawKeyboard() {
    const range = R.keyboardRange(state.exercise);
    if (!state.keys || !state.keyRange || state.keyRange.from !== range.from || state.keyRange.to !== range.to) {
      state.keys = Keys.draw($("rd-keyboard"), range.from, range.to);
      state.keyRange = range;
    }
  }

  function dueNow() {
    if (state.mode === "running" && state.kind === "step" && state.step) return state.step.waiting();
    if (state.mode === "running" && state.kind === "flow") {
      const beat = runNow() / beatMs();
      return state.exercise.notes.filter((n) => Math.abs(n.beat - beat) < 0.25 && state.judged && state.judged.results[n.index].state === "pending").map((n) => n.index);
    }
    return [];
  }

  function lightKeys() {
    if (!state.keys) return;
    Keys.light(state.keys, state.mode === "running" ? R.litNotes(state.exercise, state.judged, dueNow(), state.held) : state.held.map((midi) => ({ midi, className: "im-key-on" })));
  }

  function wireHover() {
    state.layout.groups.forEach((g, i) => {
      g.addEventListener("pointerenter", () => {
        if (state.mode === "running" || state.mode === "showing") return;
        $("rd-line").textContent = R.noteWords(state.exercise, i, state.judged, spelling());
        ensureAudio();
        if (state.ctx.state !== "running") return;
        const n = state.exercise.notes[i];
        const r = state.judged ? state.judged.results[i] : null;
        state.synth.play({ voice: "demo", midi: n.midi, velocity: 0.6 }, state.ctx.currentTime, 0.5);
        if (r && r.played !== null && r.played !== undefined && r.played !== n.midi) state.synth.play({ voice: "demo", midi: r.played, velocity: 0.45 }, state.ctx.currentTime + 0.5, 0.5);
      });
    });
  }

  // ----------------------------------------------------------------- the clock

  function ensureAudio() {
    if (state.ctx) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    state.ctx = new Ctx({ latencyHint: "interactive" });
    state.synth = Synth.createSynth(state.ctx);
  }

  function tryAnchor() {
    if (state.anchor || !state.ctx) return;
    try {
      state.anchor = Timing.makeAnchor(state.ctx.getOutputTimestamp());
    } catch (e) {
      // not producing sound yet; try again next tick
    }
  }

  function runStartPerf() {
    if (state.anchor) return Timing.heardAt(state.anchor, state.startAudio);
    return performance.now() + (state.startAudio - state.ctx.currentTime) * 1000;
  }

  function runNow() {
    return performance.now() - runStartPerf();
  }

  function scheduleClicks() {
    tryAnchor();
    const horizon = state.ctx.currentTime + AHEAD_S;
    const beatS = beatMs() / 1000;
    const firstClick = state.startAudio - COUNT_IN_BEATS * beatS;
    while (state.nextBeat < state.beats) {
      const when = firstClick + state.nextBeat * beatS;
      if (when > horizon) break;
      const inCount = state.nextBeat < COUNT_IN_BEATS;
      const accent = inCount ? state.nextBeat === 0 : (state.nextBeat - COUNT_IN_BEATS) % state.exercise.beats === 0;
      state.synth.play({ voice: "click", accent, velocity: inCount ? 1 : 0.7 }, when, 0.05);
      state.nextBeat += 1;
    }
  }

  function rangeStartBeat() {
    return state.range ? state.range[0] * state.exercise.beats : 0;
  }

  function judgeNow(final) {
    const now = final ? undefined : runNow();
    const notes = R.activeNotes(state.exercise).filter((n) => !state.range || (n.bar >= state.range[0] && n.bar <= state.range[1]));
    const shifted = notes.map((n) => ({ ...n, beat: n.beat - rangeStartBeat() }));
    const judged = R.judge({ notes: shifted, tempo: tempo(), events: state.events, latencyMs: state.profile ? state.profile.latency_offset_ms : 0, now });
    // Notes outside a drilled range are "out" in the full-length result the staff is painted from.
    const results = state.exercise.notes.map(() => ({ state: "out", timing: null, offset_ms: null, played: null }));
    notes.forEach((n, i) => (results[n.index] = judged.results[i]));
    state.judged = { ...judged, results };
    Staff.paint(state.layout, state.judged, final ? [] : dueNow());
    for (const [i, r] of results.entries()) if (r.state === "wrong" && !state.layout.groups[i].dataset.ghosted) {
      state.layout.groups[i].dataset.ghosted = "yes";
      state.layout.ghost(i, r.played);
    }
    lightKeys();
    return state.judged;
  }

  function tick() {
    if (state.mode !== "running") return;
    scheduleClicks();
    host.dataset.runStart = String(Math.round(runStartPerf()));
    const now = runNow();
    const lastBeat = state.range ? (state.range[1] + 1) * state.exercise.beats : state.exercise.bars * state.exercise.beats;
    const endMs = (lastBeat - rangeStartBeat()) * beatMs();
    if (now > endMs + TAIL_MS) {
      finish();
      return;
    }
    say(now < 0 ? `Count-in: ${Math.max(1, Math.ceil(-now / beatMs()))}` : "Read.");
    state.layout.place(Math.max(rangeStartBeat(), rangeStartBeat() + now / beatMs()), curtainOn(), state.range ? state.range[0] : 0);
    judgeNow(false);
  }

  // ------------------------------------------------------------------ run, step, show, finish

  async function start() {
    if (state.mode === "running" || state.mode === "showing" || !state.exercise) return;
    if (state.pendingStage) fresh();
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    state.kind = $("rd-mode").value === "step" ? "step" : "flow";
    state.events = [];
    state.held = [];
    state.judged = null;
    state.step = null;
    state.layout.clearGhosts();
    for (const g of state.layout.groups) delete g.dataset.ghosted;
    clearResult();
    state.mode = "running";
    host.dataset.running = "yes";
    host.dataset.mode = state.kind;
    lock(true);
    if (state.kind === "step") {
      state.step = R.createStepRun(state.exercise.notes, state.range, state.exercise.hands);
      state.step.arrive(performance.now());
      Staff.paint(state.layout, state.step.summary(), state.step.waiting());
      state.layout.place(state.step.target(), curtainOn(), state.range ? state.range[0] : 0);
      host.dataset.target = String(state.step.target());
      lightKeys();
      say("Step: play what is under the cursor. It waits for you.");
      return;
    }
    const bpm = tempo();
    $("rd-tempo").value = bpm;
    state.beats = COUNT_IN_BEATS + (state.range ? (state.range[1] - state.range[0] + 1) : state.exercise.bars) * state.exercise.beats;
    state.nextBeat = 0;
    state.startAudio = state.ctx.currentTime + LEAD_S + (COUNT_IN_BEATS * beatMs()) / 1000;
    state.anchor = null;
    host.dataset.runStart = String(Math.round(runStartPerf()));
    state.timer = window.setInterval(tick, TICK_MS);
    tick();
  }

  function stop() {
    if (state.mode !== "running" && state.mode !== "showing") return;
    if (state.timer) window.clearInterval(state.timer);
    state.timer = null;
    const was = state.mode;
    state.mode = "idle";
    host.dataset.running = "no";
    lock(false);
    state.held = [];
    state.layout.hide();
    Staff.light(state.layout, []);
    if (was === "showing") {
      Staff.paint(state.layout, state.judged, []);
      say("That was it. Now you.");
    } else {
      Staff.paint(state.layout, null, []);
      say("Stopped. Nothing was saved.");
    }
    lightKeys();
  }

  async function finish() {
    if (state.timer) window.clearInterval(state.timer);
    state.timer = null;
    const result = state.kind === "step" ? state.step.summary() : judgeNow(true);
    if (state.kind === "step") {
      state.judged = result;
      Staff.paint(state.layout, result, []);
    }
    state.mode = "over";
    host.dataset.running = "no";
    lock(false);
    state.held = [];
    state.layout.hide();
    lightKeys();
    $("rd-verdict").textContent = R.verdict(result);
    $("m-pitch").textContent = `${Math.round(result.pitchAccuracy * 100)}%`;
    $("m-time").textContent = `${Math.round(result.timingAccuracy * 100)}%`;
    $("m-score").textContent = String(result.score);
    const spots = $("rd-spots");
    spots.textContent = "";
    for (const line of R.spotWords(state.exercise, result)) spots.appendChild(make("li", line, "im-list-item"));
    const fix = $("rd-fix");
    fix.textContent = "";
    for (const bar of R.badBars(state.exercise, result)) {
      const button = make("button", `Drill bar ${bar + 1}`, "im-btn im-btn-quiet im-btn-small");
      button.type = "button";
      button.title = "Step mode, this bar only";
      button.addEventListener("click", () => drillBar(bar));
      fix.appendChild(button);
    }
    const record = R.toRecord(state.exercise, result, { tempo: tempo(), curtain: curtainOn(), events: state.events });
    const wasFull = !state.range;
    state.range = null;
    state.mode = "idle";
    try {
      const saved = await send("POST", host.dataset.apiTakes, record);
      state.takes.unshift(saved);
      listTakes();
      showBest();
      host.dataset.saved = "yes";
      await refreshReport();
      if (saved.passed && wasFull) advance();
      else if (result.mode === "flow" && !saved.passed) say("Not yet. Read it again, or slow the tempo.");
      else if (result.mode === "step") say("Saved. Step mode is for fixing; pass it in Flow to move on.");
    } catch (e) {
      say("The take could not be saved. " + e.message);
    }
  }

  // A pass on the path's own stage moves the key and hands on. The result stays on the staff to be looked at;
  // the next stage's exercise is made at the next Start or Next.
  function advance() {
    const next = state.report && state.report.stage ? state.report.stage : null;
    if (!next || next.done) {
      say("Passed. Every stage is done; read on at a faster tempo.");
      return;
    }
    if (next.index <= state.stage.index) {
      say(`Passed. The path is at stage ${next.index + 1}.`);
      return;
    }
    $("rd-key").value = next.key;
    $("rd-hands").value = next.hands;
    state.pendingStage = true;
    host.dataset.stage = String(next.index);
    say(`Passed. Next: ${R.stageTitle(R.stageOf(next.index))}. Press Start when you are ready.`);
  }

  function drillBar(bar) {
    if (state.mode === "running" || state.mode === "showing") return;
    $("rd-mode").value = "step";
    state.range = [bar, bar];
    start();
  }

  async function showMe() {
    if (state.mode === "running" || state.mode === "showing" || !state.exercise) return;
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    state.mode = "showing";
    host.dataset.running = "yes";
    lock(true);
    const beatS = beatMs() / 1000;
    state.startAudio = state.ctx.currentTime + LEAD_S + SHOW_ME_BEATS * beatS;
    state.anchor = null;
    for (const n of state.exercise.notes) state.synth.play({ voice: "demo", midi: n.midi, velocity: 0.75 }, state.startAudio + n.beat * beatS, n.dur * beatS * 0.9);
    say("Watch the staff and the keys together.");
    state.timer = window.setInterval(() => {
      if (state.mode !== "showing") return;
      tryAnchor();
      const beat = runNow() / beatMs();
      const total = state.exercise.bars * state.exercise.beats;
      if (beat > total + 0.3) {
        stop();
        return;
      }
      const on = state.exercise.notes.filter((n) => beat >= n.beat && beat < n.beat + n.dur).map((n) => n.index);
      Staff.light(state.layout, on);
      if (state.keys) Keys.light(state.keys, on.map((i) => ({ midi: state.exercise.notes[i].midi, className: "im-key-chord" })));
      state.layout.place(Math.max(0, beat), false, 0);
    }, TICK_MS);
  }

  function clearResult() {
    $("rd-verdict").textContent = "";
    $("rd-spots").textContent = "";
    $("rd-fix").textContent = "";
    for (const id of ["m-pitch", "m-time", "m-score"]) $(id).textContent = "-";
    showBest();
  }

  function showBest() {
    const stage = state.stage;
    const mine = state.takes.filter((t) => t.key === stage.key && t.hands === stage.hands && t.mode === "flow");
    if (!mine.length) {
      $("rd-best").textContent = "You have not read this stage in Flow yet.";
      return;
    }
    const best = mine.reduce((a, b) => (b.score > a.score ? b : a));
    $("rd-best").textContent = `Your best here: ${best.score}${best.passed ? ", passed" : ""}, at ${best.tempo_bpm} bpm.`;
  }

  function lock(running) {
    for (const id of ["rd-key", "rd-hands", "rd-tempo", "rd-mode", "rd-curtain"]) $(id).disabled = running;
    $("rd-start").textContent = running ? "Stop" : "Start";
    $("rd-show").disabled = running;
    $("rd-next").disabled = running;
  }

  function listTakes() {
    const list = $("rd-takes");
    list.textContent = "";
    if (!state.takes.length) {
      list.appendChild(make("li", "No takes yet.", "im-list-item"));
      return;
    }
    for (const t of state.takes.slice(0, 10)) {
      const text = `${t.key} major, ${R.HAND_WORDS[t.hands]}, ${t.mode}, ${t.tempo_bpm} bpm: ${t.score}${t.passed ? " (passed)" : ""}`;
      list.appendChild(make("li", text, "im-list-item"));
    }
  }

  async function refreshReport() {
    try {
      state.report = await getJson(host.dataset.apiReading);
      $("rd-stage-line").textContent = R.stageLine(state.report, state.stage);
      $("rd-work").textContent = R.workWords(state.report);
    } catch (e) {
      // the stage line keeps what it had
    }
  }

  async function saveTempo() {
    const bpm = tempo();
    $("rd-tempo").value = bpm;
    line();
    if (bpm === state.tempoSaved) return;
    try {
      await send("PATCH", host.dataset.apiPlayer, { reading_tempo: bpm });
      state.tempoSaved = bpm;
      state.profile.reading_tempo = bpm;
    } catch (e) {
      say("The tempo could not be saved. " + e.message);
    }
  }

  // ---------------------------------------------------------------------- the piano

  function onMidi(event) {
    const message = Midi.parse(event.data);
    if (!message || (message.type !== "on" && message.type !== "off") || message.note >= R.CONTROL_FLOOR) return;
    if (message.type === "on") state.held = [...state.held.filter((n) => n !== message.note), message.note];
    else state.held = state.held.filter((n) => n !== message.note);
    if (state.mode === "running" && message.type === "on") {
      if (state.kind === "flow") {
        state.events.push({ t_ms: Math.round(event.timeStamp - runStartPerf()), type: "on", note: message.note, velocity: message.velocity || 64 });
        judgeNow(false);
      } else {
        const outcome = state.step.press(message.note, event.timeStamp);
        state.events.push({ t_ms: Math.round(event.timeStamp), type: "on", note: message.note, velocity: message.velocity || 64 });
        const summary = state.step.summary();
        state.judged = summary;
        for (const [i, r] of summary.results.entries()) if (r.played !== null && r.played !== undefined && !state.layout.groups[i].dataset.ghosted) {
          state.layout.groups[i].dataset.ghosted = "yes";
          state.layout.ghost(i, r.played);
        }
        if (outcome.done) {
          finish();
          return;
        }
        Staff.paint(state.layout, summary, state.step.waiting());
        state.layout.place(state.step.target(), curtainOn(), state.range ? state.range[0] : 0);
        host.dataset.target = String(state.step.target());
        say(outcome.right ? "Read." : "Not that one. Look again.");
      }
    }
    lightKeys();
  }

  function attachInput(choice) {
    for (const port of state.midi ? state.midi.inputs.values() : []) port.onmidimessage = null;
    state.listening = choice || null;
    state.held = [];
    if (!choice) return;
    const port = state.midi.inputs.get(choice.id);
    if (port) port.onmidimessage = onMidi;
  }

  function listInputs() {
    const inputs = Setup.inputChoices(Array.from(state.midi.inputs.values()));
    const remembered = state.listening ? state.listening.name : state.profile ? state.profile.midi_input_name : "";
    const choice = Setup.pickInput(inputs, remembered);
    $("rd-midi").textContent = choice ? `Listening to ${choice.name}.` : "No keyboard is connected. Plug the piano in by USB.";
    if (!choice || !state.listening || choice.id !== state.listening.id) attachInput(choice);
  }

  function stopMidi() {
    if (state.midi) state.midi.onstatechange = null;
    attachInput(null);
  }

  async function startMidi() {
    if (!navigator.requestMIDIAccess) {
      $("rd-midi").textContent = "This browser has no Web MIDI, so it cannot hear the piano. Use Chrome or Edge.";
      return;
    }
    try {
      state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      $("rd-midi").textContent = "MIDI was refused, so the piano cannot be heard. Allow it in the address bar.";
      return;
    }
    state.midi.onstatechange = listInputs;
    listInputs();
  }

  // ----------------------------------------------------------------------- start

  function fill(select, items, selected) {
    select.textContent = "";
    for (const [value, text] of items) {
      const option = make("option", text);
      option.value = String(value);
      select.appendChild(option);
    }
    select.value = String(selected);
  }

  async function init() {
    try {
      const [profile, takes, report] = await Promise.all([getJson(host.dataset.apiPlayer), getJson(host.dataset.apiTakes), getJson(host.dataset.apiReading)]);
      state.profile = profile;
      state.takes = takes;
      state.report = report;
    } catch (e) {
      say("The reading trainer could not load. " + e.message);
      return;
    }
    state.tempoSaved = R.clampTempo(state.profile.reading_tempo);
    const asked = new URLSearchParams(window.location.search);
    const here = state.report.stage;
    const askedKey = R.keyInfo(asked.get("key") || "") ? asked.get("key") : null;
    const askedHands = R.HANDS.includes(asked.get("hands") || "") ? asked.get("hands") : null;
    fill($("rd-key"), R.KEYS.map((k) => [k.name, `${k.name} major`]), askedKey || here.key);
    fill($("rd-hands"), R.HANDS.map((h) => [h, R.HAND_WORDS[h]]), askedHands || here.hands);
    $("rd-tempo").value = state.tempoSaved;
    if (asked.get("mode") === "step") $("rd-mode").value = "step";
    fresh(asked.get("seed") !== null && /^\d+$/.test(asked.get("seed")) ? Number(asked.get("seed")) : undefined);
    listTakes();
    $("rd-start").disabled = false;
    $("rd-show").disabled = false;
    $("rd-next").disabled = false;
    say("Pick the stage, then Start. Four clicks, then read.");

    $("rd-key").addEventListener("change", () => fresh());
    $("rd-hands").addEventListener("change", () => fresh());
    $("rd-mode").addEventListener("change", () => fresh(state.exercise.seed));
    $("rd-curtain").addEventListener("change", () => fresh(state.exercise.seed));
    $("rd-tempo").addEventListener("change", saveTempo);
    $("rd-start").addEventListener("click", () => (state.mode === "running" || state.mode === "showing" ? stop() : start()));
    $("rd-show").addEventListener("click", showMe);
    $("rd-next").addEventListener("click", () => fresh(newSeed()));
    if (Input) Input.attach({ status: $("rd-midi"), deliver: onMidi, midiStart: startMidi, midiStop: stopMidi }).start();
    else startMidi();
  }

  // For the tests and the console: the exercise on the screen, and a note as if the piano sent it.
  window.ImprovReadingPage = {
    exercise: () => state.exercise,
    active: () => R.activeNotes(state.exercise),
    press: (midi) => onMidi({ data: Uint8Array.from([0x90, midi, 90]), timeStamp: performance.now() }),
  };
  if (!R || !Staff || !Keys || !Timing || !Synth || !Midi || !Setup) say("The page's scripts did not load.");
  else init();
})();
