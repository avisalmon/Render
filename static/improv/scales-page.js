// improv: the Scales screen. Browser glue only: the key, the level and the tempo, a count-in click,
// the piano's notes against the clock, and the judge's answer. The rules (the plan, the judge, the
// words) live in scale.js, which is tested under Node. Only text is ever put on the page.
(function () {
  "use strict";
  const Scale = window.ImprovScale;
  const Work = window.ImprovWork;
  const Keys = window.ImprovKeyboardView;
  const Timing = window.ImprovTiming;
  const Synth = window.ImprovSynth;
  const Midi = window.ImprovMidi;
  const Setup = window.ImprovSetup;
  const $ = (id) => document.getElementById(id);
  const host = $("scales");
  const TICK_MS = 25;
  const AHEAD_S = 0.2;
  const LEAD_S = 0.3;
  const TAIL_MS = 150;

  const state = {
    profile: null,
    fingerings: [],
    runs: [],
    plan: null,
    clock: null,
    mode: "idle", // idle | running | over
    ctx: null,
    synth: null,
    anchor: null,
    startAudio: 0,
    nextBeat: 0,
    beats: 0,
    events: [],
    held: [],
    judged: null,
    cells: [],
    keys: null,
    range: null,
    timer: null,
    midi: null,
    listening: null,
    tempoSaved: Scale.TEMPO_DEFAULT,
  };

  const say = (text) => ($("sc-status").textContent = text);

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
  const rootPc = () => Number($("sc-key").value);
  const level = () => Number($("sc-level").value);
  const tempo = () => Scale.clampTempo($("sc-tempo").value);

  // --------------------------------------------------------------- the plan on the screen

  function drawKeyboard() {
    const range = Scale.keyboardRange(state.plan);
    const from = range.from - (range.from % 12);
    if (!state.keys || !state.range || state.range.from !== from || state.range.to !== range.to) {
      state.keys = Keys.draw($("sc-keyboard"), from, range.to);
      state.range = { from, to: range.to };
    }
  }

  function drawStrip() {
    const strip = $("sc-strip");
    strip.textContent = "";
    state.cells = state.plan.steps.map((step) => {
      const cell = make("div", undefined, "im-sc-cell");
      cell.append(
        make("span", step.name, "im-sc-note"),
        make("span", step.leftFinger === null ? "-" : String(step.leftFinger), "im-sc-finger"),
        make("span", step.rightFinger === null ? "-" : String(step.rightFinger), "im-sc-finger")
      );
      cell.title = Scale.fingerWords(step);
      strip.appendChild(cell);
      return cell;
    });
  }

  function lightKeys(stepIndex) {
    if (!state.keys) return;
    const step = state.mode === "running" && stepIndex !== null ? state.plan.steps[stepIndex] : null;
    Keys.light(state.keys, Scale.litNotes(step, state.held));
  }

  function line() {
    const info = Scale.levelInfo(level());
    const clock = Scale.timeline(tempo(), info.perBeat);
    const seconds = Math.round((Scale.runMs(state.plan, clock) + clock.countInMs) / 1000);
    const parts = [
      `${Scale.levelLabel(level())} at ${tempo()} bpm: four clicks, then ${state.plan.steps.length} notes up and down, about ${seconds} seconds. Top row of each cell is the note, then the left finger, then the right.`,
    ];
    if (Scale.needsFullKeyboard(info.octaves)) parts.push("Four octaves needs an 88-key piano.");
    if (!state.plan.hasFingering) parts.push("No fingering is stored for this key yet.");
    $("sc-line").textContent = parts.join(" ");
  }

  function chooseScale() {
    if (state.mode === "running") return;
    state.plan = Scale.plan(rootPc(), Scale.levelInfo(level()).octaves, spelling(), state.fingerings);
    $("sc-name").textContent = `${state.plan.key} major, both hands, ${Scale.levelLabel(level())}`;
    drawKeyboard();
    drawStrip();
    lightKeys(null);
    line();
    showBest();
  }

  function showBest() {
    const best = Scale.bestOf(state.runs, rootPc(), Scale.levelInfo(level()).octaves);
    $("sc-best").textContent = best
      ? `Your best here: ${best.score}${best.passed ? ", passed" : ""}, at ${best.tempo} bpm.`
      : "You have not played this key at this level yet.";
  }

  function paintCells(judged, current) {
    judged.steps.forEach((s, i) => {
      const cell = state.cells[i];
      if (!cell) return;
      cell.dataset.state = s.state;
      cell.classList.toggle("im-sc-now", i === current);
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

  // The performance-clock time at which step 0 is heard.
  function runStartPerf() {
    if (state.anchor) return Timing.heardAt(state.anchor, state.startAudio);
    return performance.now() + (state.startAudio - state.ctx.currentTime) * 1000;
  }

  function runNow() {
    return performance.now() - runStartPerf();
  }

  function schedule() {
    tryAnchor();
    const horizon = state.ctx.currentTime + AHEAD_S;
    const beatS = state.clock.beatMs / 1000;
    const firstClick = state.startAudio - state.clock.countInBeats * beatS;
    while (state.nextBeat < state.beats) {
      const when = firstClick + state.nextBeat * beatS;
      if (when > horizon) break;
      const inCount = state.nextBeat < state.clock.countInBeats;
      const accent = inCount ? state.nextBeat === 0 : (state.nextBeat - state.clock.countInBeats) % 4 === 0;
      state.synth.play({ voice: "click", accent, velocity: 1 }, when, 0.05);
      state.nextBeat += 1;
    }
  }

  function currentStep(now) {
    const at = Math.floor((now + state.clock.stepMs / 2) / state.clock.stepMs);
    if (at < 0) return null;
    return Math.min(at, state.plan.steps.length - 1);
  }

  function judgeNow(final) {
    const info = Scale.levelInfo(level());
    const now = final ? undefined : runNow();
    state.judged = Scale.judge({
      steps: state.plan.steps,
      tempo: state.clock.tempo,
      perBeat: info.perBeat,
      events: state.events,
      latencyMs: state.profile ? state.profile.latency_offset_ms : 0,
      now,
    });
    const at = final ? null : currentStep(now);
    paintCells(state.judged, at);
    lightKeys(at);
    return state.judged;
  }

  function tick() {
    if (state.mode !== "running") return;
    schedule();
    host.dataset.runStart = String(Math.round(runStartPerf()));
    const lastDue = (state.plan.steps.length - 1) * state.clock.stepMs;
    const now = runNow();
    if (now > lastDue + state.clock.stepMs / 2 + TAIL_MS) {
      finish();
      return;
    }
    say(now < 0 ? `Count-in: ${Math.max(1, Math.ceil(-now / state.clock.beatMs))}` : "Play.");
    judgeNow(false);
  }

  // ------------------------------------------------------------------ run and finish

  async function start() {
    if (state.mode === "running" || !state.plan) return;
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    const info = Scale.levelInfo(level());
    const bpm = tempo();
    $("sc-tempo").value = bpm;
    state.clock = { ...Scale.timeline(bpm, info.perBeat), tempo: bpm };
    state.beats = state.clock.countInBeats + Math.ceil(Scale.runBeats(state.plan, info.perBeat));
    state.nextBeat = 0;
    state.startAudio = state.ctx.currentTime + LEAD_S + state.clock.countInMs / 1000;
    state.anchor = null;
    state.events = [];
    state.held = [];
    state.judged = null;
    state.mode = "running";
    host.dataset.runStart = String(Math.round(runStartPerf()));
    host.dataset.running = "yes";
    lock(true);
    clearResult();
    state.timer = window.setInterval(tick, TICK_MS);
    tick();
  }

  function stop() {
    if (state.mode !== "running") return;
    window.clearInterval(state.timer);
    state.mode = "idle";
    host.dataset.running = "no";
    lock(false);
    state.held = [];
    for (const cell of state.cells) {
      delete cell.dataset.state;
      cell.classList.remove("im-sc-now");
    }
    lightKeys(null);
    say("Stopped. Nothing was saved.");
  }

  async function finish() {
    window.clearInterval(state.timer);
    const result = judgeNow(true);
    state.mode = "over";
    host.dataset.running = "no";
    lock(false);
    state.held = [];
    lightKeys(null);
    const info = Scale.levelInfo(level());
    $("sc-verdict").textContent = Scale.verdict(result);
    $("sc-feel").textContent = Scale.feelWords(result);
    const missed = Scale.missedWords(state.plan, result);
    $("sc-misses").textContent = missed.length ? `Missed: ${missed.join(", ")}.` : "No note was missed.";
    say(result.passed ? "Passed. Next key when you are ready." : "Not yet. Start again, or slow the tempo.");
    const record = Scale.toRecord(result, { rootPc: rootPc(), octaves: info.octaves, perBeat: info.perBeat, tempo: state.clock.tempo });
    state.mode = "idle";
    try {
      const saved = await send("POST", host.dataset.apiRuns, record);
      state.runs.unshift(saved);
      listRuns();
      showBest();
      host.dataset.saved = "yes";
      refreshWork();
    } catch (e) {
      say("The run could not be saved. " + e.message);
    }
  }

  function clearResult() {
    for (const id of ["sc-verdict", "sc-feel", "sc-misses"]) $(id).textContent = "";
    host.dataset.saved = "no";
    showBest();
  }

  function lock(running) {
    for (const id of ["sc-key", "sc-level", "sc-tempo"]) $(id).disabled = running;
    $("sc-start").textContent = running ? "Stop" : "Start";
    $("sc-next").disabled = running;
  }

  function nextKey() {
    if (state.mode === "running") return;
    $("sc-key").value = String(Scale.nextKey(rootPc()));
    chooseScale();
  }

  // ------------------------------------------------------------------ the runs list

  function listRuns() {
    const list = $("sc-runs");
    list.textContent = "";
    if (!state.runs.length) {
      list.appendChild(make("li", "No runs yet.", "im-list-item"));
      return;
    }
    for (const run of state.runs.slice(0, 12)) {
      const text = `${Scale.keyName(run.root_pc, spelling())}, ${run.octaves} octaves, ${run.tempo_bpm} bpm: ${run.score}${run.passed ? " (passed)" : ""}`;
      list.appendChild(make("li", text, "im-list-item"));
    }
  }

  // --------------------------------------------------------------------- the tempo

  async function saveTempo() {
    const bpm = tempo();
    $("sc-tempo").value = bpm;
    line();
    if (bpm === state.tempoSaved) return;
    try {
      await send("PATCH", host.dataset.apiPlayer, { trainer_tempo: bpm });
      state.tempoSaved = bpm;
      state.profile.trainer_tempo = bpm;
    } catch (e) {
      say("The tempo could not be saved. " + e.message);
    }
  }

  // ---------------------------------------------------------------------- the piano

  function onMidi(event) {
    const message = Midi.parse(event.data);
    if (!message || message.type === "pedal" || message.note >= Scale.CONTROL_FLOOR) return;
    if (message.type === "on") state.held = [...state.held.filter((n) => n !== message.note), message.note];
    else state.held = state.held.filter((n) => n !== message.note);
    if (state.mode === "running") {
      if (message.type === "on") state.events.push({ t_ms: Math.round(event.timeStamp - runStartPerf()), type: "on", note: message.note });
      judgeNow(false);
    } else {
      lightKeys(null);
    }
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
    $("sc-midi").textContent = choice ? `Listening to ${choice.name}.` : "No keyboard is connected. Plug the piano in by USB.";
    if (!choice || !state.listening || choice.id !== state.listening.id) attachInput(choice);
  }

  async function startMidi() {
    if (!navigator.requestMIDIAccess) {
      $("sc-midi").textContent = "This browser has no Web MIDI, so it cannot hear the piano. Use Chrome or Edge.";
      return;
    }
    try {
      state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      $("sc-midi").textContent = "MIDI was refused, so the piano cannot be heard. Allow it in the address bar.";
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

  async function refreshWork() {
    try {
      const read = await getJson(host.dataset.apiTrainer);
      const words = Work.scaleWork(read, spelling());
      $("tr-work").textContent = words;
      host.dataset.work = words;
    } catch (e) {
      $("tr-work").textContent = "";
    }
  }

  async function init() {
    try {
      const [profile, fingerings, runs] = await Promise.all([
        getJson(host.dataset.apiPlayer),
        getJson(host.dataset.apiFingerings),
        getJson(host.dataset.apiRuns),
      ]);
      state.profile = profile;
      state.fingerings = fingerings;
      state.runs = runs;
    } catch (e) {
      say("The scales could not load. " + e.message);
      return;
    }
    state.tempoSaved = Scale.clampTempo(state.profile.trainer_tempo);
    const asked = new URLSearchParams(window.location.search);
    const askedKey = Number(asked.get("key"));
    const askedLevel = Number(asked.get("level"));
    fill($("sc-key"), Scale.CIRCLE.map((pc) => [pc, Scale.keyName(pc, spelling())]), asked.get("key") !== null && Scale.CIRCLE.includes(askedKey) ? askedKey : Scale.CIRCLE[0]);
    fill($("sc-level"), [1, 2, 3].map((n) => [n, Scale.levelLabel(n)]), [1, 2, 3].includes(askedLevel) ? askedLevel : 1);
    $("sc-tempo").value = state.tempoSaved;
    chooseScale();
    listRuns();
    refreshWork();
    $("sc-start").disabled = false;
    $("sc-next").disabled = false;
    say("Pick the key, then Start. Four clicks, then play both hands.");

    $("sc-key").addEventListener("change", chooseScale);
    $("sc-level").addEventListener("change", chooseScale);
    $("sc-tempo").addEventListener("change", saveTempo);
    $("sc-start").addEventListener("click", () => (state.mode === "running" ? stop() : start()));
    $("sc-next").addEventListener("click", nextKey);
    startMidi();
  }

  if (!Scale || !Keys || !Timing || !Synth || !Midi || !Setup) say("The page's scripts did not load.");
  else init();
})();
