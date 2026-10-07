// improv: the Chords screen. Browser glue only: the mode, key and level, the piano's notes, the clock
// on each prompt and the record of each answer. The rules (the chords, the positions, the matching,
// the order of prompts, the words) live in drill.js, which is tested under Node. Only text is ever
// put on the page.
(function () {
  "use strict";
  const Drill = window.ImprovDrill;
  const Scale = window.ImprovScale;
  const Work = window.ImprovWork;
  const Keys = window.ImprovKeyboardView;
  const Midi = window.ImprovMidi;
  const Setup = window.ImprovSetup;
  const Rec = window.ImprovRecognize;
  const $ = (id) => document.getElementById(id);
  const host = $("chords");

  const KEY_FROM = 36;
  const KEY_TO = 96;
  const WRONG_AFTER_MS = 120;
  const ADVANCE_MS = 700;
  const SKIP_SHOW_MS = 1500;
  const CLOCK_MS = 100;
  const MODES = [["drill", "Drill: one key"], ["circle", "Circle: all twelve keys"], ["learn", "Learn: see the chords"]];
  const LEVELS = [[1, "1: triads, 3 positions"], [2, "2: sevenths, 4 positions"], [3, "3: sevenths and I7, IV7"]];

  const state = {
    profile: null,
    qualities: [],
    run: "idle", // idle | running | over
    prompts: [],
    index: 0,
    prompt: null,
    shownAt: 0,
    wrongTries: 0,
    hintUsed: false,
    called: "",
    lastNotes: [],
    locked: false,
    needRelease: false,
    wrongLatched: false,
    results: [],
    saved: 0,
    shown: null,
    held: [],
    keys: null,
    clock: null,
    wrongTimer: null,
    advanceTimer: null,
    midi: null,
    listening: null,
  };

  const say = (text) => ($("ch-status").textContent = text);

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
  const mode = () => $("ch-mode").value;
  const level = () => Number($("ch-level").value);
  const keyPc = () => Number($("ch-key").value);
  const running = () => state.run === "running";

  // ------------------------------------------------------------------ the keyboard

  function voicingLabels(prompt) {
    const tones = prompt.tones;
    return tones.map((_, i) => tones[(prompt.position - 1 + i) % tones.length]);
  }

  function paint() {
    if (!state.keys) return;
    const lit = [];
    const prompt = running() ? state.prompt : state.shown;
    const answer = prompt && (state.hintUsed || !running()) ? Drill.voicing(prompt) : [];
    const labels = prompt ? voicingLabels(prompt) : [];
    const held = new Set(state.held);
    answer.forEach((midi, i) => {
      lit.push({ midi, className: held.has(midi) ? "im-key-chord" : running() ? "im-key-pending" : "im-key-chord", step: labels[i] });
    });
    for (const midi of state.held) {
      if (answer.includes(midi)) continue;
      const inChord = prompt && prompt.pcs.includes(midi % 12);
      lit.push({ midi, className: running() ? (inChord ? "im-key-chord" : "im-key-outside") : "im-key-on" });
    }
    Keys.light(state.keys, lit);
  }

  // ------------------------------------------------------------------ the screen

  function buttons() {
    const on = running();
    const learning = mode() === "learn";
    $("ch-start").textContent = on ? "Stop" : "Start";
    $("ch-start").disabled = learning && !on;
    $("ch-hint").disabled = !on;
    $("ch-skip").disabled = !on;
    for (const id of ["ch-mode", "ch-level"]) $(id).disabled = on;
    $("ch-key").disabled = on || mode() === "circle";
  }

  function line() {
    const learning = mode() === "learn";
    const parts = [];
    if (learning) {
      parts.push("Pick any position to see it on the keyboard. Nothing is scored here.");
    } else if (mode() === "circle") {
      const count = Scale.CIRCLE.length * Drill.pool(keyPc(), level(), spelling()).length;
      parts.push(`All twelve keys from G round the circle of fifths: ${count} chords, one at a time.`);
    } else {
      const count = Drill.makeDrill(keyPc(), level(), spelling(), () => 0.5).length;
      parts.push(`${Drill.keyName(keyPc(), spelling())} major: ${count} prompts, every chord in every position.`);
    }
    if (!learning) parts.push("Play the chord in any octave, either hand; the lowest note must be the one the position asks for. Hint shows it, Skip moves on.");
    $("ch-line").textContent = parts.join(" ");
  }

  function showPlaceholder() {
    $("ch-progress").textContent = "";
    $("ch-prompt").textContent = mode() === "learn" ? "Pick a chord position" : "Press Start";
    $("ch-detail").textContent = "";
    $("ch-timer").textContent = "";
    $("ch-feedback").textContent = "";
    $("ch-feedback").removeAttribute("data-state");
  }

  function renderLearn() {
    const list = $("ch-learn");
    list.textContent = "";
    $("ch-learn-title").textContent = `The chords of ${Drill.keyName(keyPc(), spelling())} major`;
    for (const row of Drill.learnList(keyPc(), level(), spelling())) {
      const item = make("div", undefined, "im-learn-row");
      const tones = row.chord.tones.join(" ");
      item.append(make("strong", row.chord.name), make("span", `  ${row.chord.roman}, ${tones}`, "im-note-inline"), make("br"));
      for (const prompt of row.prompts) {
        const label = prompt.position === 1 ? "1st (root)" : `${["", "1st", "2nd", "3rd", "4th"][prompt.position]} (inv ${prompt.position - 1})`;
        const button = make("button", `${prompt.position}`, "im-btn im-btn-quiet");
        button.type = "button";
        button.title = `${prompt.title}: ${prompt.detail}`;
        button.setAttribute("aria-label", `${row.chord.name}, ${label}`);
        button.addEventListener("click", () => showLearn(prompt, button));
        item.appendChild(button);
      }
      list.appendChild(item);
    }
  }

  function showLearn(prompt, button) {
    state.shown = prompt;
    for (const b of $("ch-learn").querySelectorAll("button")) b.setAttribute("aria-pressed", b === button ? "true" : "false");
    $("ch-progress").textContent = `${prompt.key} major, ${prompt.roman}`;
    $("ch-prompt").textContent = prompt.title;
    $("ch-detail").textContent = `${prompt.detail}: ${voicingLabels(prompt).join(" ")}`;
    paint();
  }

  function chooseSetup() {
    if (running()) return;
    state.run = "idle";
    state.shown = null;
    state.hintUsed = false;
    const learning = mode() === "learn";
    $("ch-learn-box").hidden = !learning;
    $("ch-results-box").hidden = learning;
    host.dataset.mode = mode();
    if (learning) renderLearn();
    showPlaceholder();
    buttons();
    line();
    paint();
  }

  function renderResults() {
    const list = $("ch-results");
    list.textContent = "";
    if (!state.results.length) {
      list.appendChild(make("li", "No answers yet.", "im-list-item"));
      return;
    }
    for (const r of state.results) {
      const where = mode() === "circle" ? `${r.prompt.key}: ` : "";
      const how = r.skipped ? "skipped" : Drill.seconds(r.responseMs);
      const marks = [];
      if (r.wrongTries) marks.push(`${r.wrongTries} wrong`);
      if (r.hintUsed) marks.push("hint");
      list.appendChild(make("li", `${where}${r.prompt.title}: ${how}${marks.length ? ` (${marks.join(", ")})` : ""}`, "im-list-item"));
    }
  }

  function summary() {
    const done = state.results.length;
    if (!done) {
      $("ch-summary").textContent = "";
      return;
    }
    const clean = state.results.filter((r) => !r.skipped && !r.wrongTries && !r.hintUsed);
    const timed = state.results.filter((r) => !r.skipped);
    const mean = timed.length ? timed.reduce((sum, r) => sum + r.responseMs, 0) / timed.length : null;
    $("ch-summary").textContent = `${clean.length} of ${done} clean${mean === null ? "" : `, average ${Drill.seconds(mean)}`}.`;
  }

  // ------------------------------------------------------------------ the prompts

  function showPrompt(i) {
    state.index = i;
    state.prompt = state.prompts[i];
    const p = state.prompt;
    state.wrongTries = 0;
    state.hintUsed = false;
    state.called = "";
    state.lastNotes = [];
    state.wrongLatched = false;
    state.needRelease = state.held.length > 0;
    state.locked = false;
    state.shownAt = performance.now();
    if (mode() === "circle") $("ch-key").value = String(p.key_pc);
    $("ch-progress").textContent = `${p.key} major, chord ${i + 1} of ${state.prompts.length}`;
    $("ch-prompt").textContent = p.title;
    $("ch-detail").textContent = p.inversion;
    $("ch-timer").textContent = Drill.seconds(0);
    $("ch-feedback").textContent = "";
    $("ch-feedback").removeAttribute("data-state");
    host.dataset.hint = "no";
    host.dataset.promptJson = JSON.stringify(p);
    host.dataset.promptNumber = String(i + 1);
    paint();
  }

  function startClock() {
    stopClock();
    state.clock = window.setInterval(() => {
      if (running() && !state.locked) $("ch-timer").textContent = Drill.seconds(performance.now() - state.shownAt);
    }, CLOCK_MS);
  }

  function stopClock() {
    if (state.clock) window.clearInterval(state.clock);
    state.clock = null;
  }

  function clearTimers() {
    window.clearTimeout(state.wrongTimer);
    window.clearTimeout(state.advanceTimer);
    state.wrongTimer = null;
    state.advanceTimer = null;
  }

  function start() {
    if (running() || mode() === "learn") return;
    const lv = level();
    state.prompts = mode() === "circle" ? Drill.makeCircle(lv, spelling()) : Drill.makeDrill(keyPc(), lv, spelling());
    state.results = [];
    state.saved = 0;
    host.dataset.saved = "0";
    state.run = "running";
    host.dataset.running = "yes";
    buttons();
    renderResults();
    summary();
    say("Play the chord. Hint shows it, Skip moves on.");
    startClock();
    showPrompt(0);
  }

  function stop() {
    if (!running()) return;
    clearTimers();
    stopClock();
    state.run = "idle";
    state.prompt = null;
    state.hintUsed = false;
    host.dataset.running = "no";
    buttons();
    showPlaceholder();
    paint();
    say("Stopped. The answers so far were kept.");
  }

  function finish() {
    clearTimers();
    stopClock();
    state.run = "over";
    state.prompt = null;
    state.hintUsed = false;
    host.dataset.running = "no";
    buttons();
    $("ch-progress").textContent = "";
    $("ch-prompt").textContent = "Done";
    $("ch-detail").textContent = "";
    $("ch-timer").textContent = "";
    summary();
    say("That was the last one. Start again for another round.");
    paint();
  }

  async function record(prompt, outcome) {
    state.results.unshift({ prompt, ...outcome });
    renderResults();
    summary();
    try {
      await send("POST", host.dataset.apiAttempts, Drill.toAttempt(prompt, outcome));
      state.saved += 1;
      host.dataset.saved = String(state.saved);
      refreshWork();
    } catch (e) {
      say("An answer could not be saved. " + e.message);
    }
  }

  function outcome(skipped) {
    return {
      wrongTries: state.wrongTries,
      hintUsed: state.hintUsed,
      skipped,
      responseMs: performance.now() - state.shownAt,
      notes: state.lastNotes,
      called: state.called,
    };
  }

  function advanceSoon(delay) {
    state.locked = true;
    state.advanceTimer = window.setTimeout(() => {
      if (!running()) return;
      if (state.index + 1 >= state.prompts.length) finish();
      else showPrompt(state.index + 1);
    }, delay);
  }

  function right() {
    window.clearTimeout(state.wrongTimer);
    state.lastNotes = state.held.slice().sort((a, b) => a - b);
    const result = outcome(false);
    state.needRelease = true;
    $("ch-timer").textContent = Drill.seconds(result.responseMs);
    $("ch-feedback").textContent = `Right: ${state.prompt.slash}. ${Drill.seconds(result.responseMs)}.`;
    $("ch-feedback").dataset.state = "right";
    host.dataset.lastResult = "right";
    paint();
    record(state.prompt, result);
    advanceSoon(ADVANCE_MS);
  }

  function skip() {
    if (!running() || state.locked) return;
    window.clearTimeout(state.wrongTimer);
    const result = outcome(true);
    state.hintUsed = true;
    state.needRelease = true;
    $("ch-feedback").textContent = `Skipped. ${state.prompt.title} is ${voicingLabels(state.prompt).join(" ")}, ${state.prompt.inversion}.`;
    $("ch-feedback").dataset.state = "wrong";
    host.dataset.lastResult = "skipped";
    paint();
    record(state.prompt, result);
    advanceSoon(SKIP_SHOW_MS);
  }

  function hint() {
    if (!running() || state.locked) return;
    state.hintUsed = true;
    $("ch-detail").textContent = `${state.prompt.detail}: ${voicingLabels(state.prompt).join(" ")}`;
    host.dataset.hint = "yes";
    paint();
  }

  // ----------------------------------------------------------------------- the notes

  function calledName() {
    if (!Rec || !state.held.length) return "";
    const read = Rec.recognize(state.held, state.qualities, { spelling: spelling() });
    return read.kind === "chord" ? read.name : "";
  }

  function wrongNow() {
    state.wrongTimer = null;
    if (!running() || state.locked || state.needRelease || state.wrongLatched || !state.held.length) return;
    const result = Drill.judgeHeld(state.prompt, state.held);
    if (result.state === "right") {
      right();
      return;
    }
    if (result.state !== "wrong") return;
    state.wrongLatched = true;
    state.wrongTries += 1;
    state.lastNotes = state.held.slice().sort((a, b) => a - b);
    state.called = calledName();
    $("ch-feedback").textContent = Drill.wrongWords(state.prompt, result, state.called);
    $("ch-feedback").dataset.state = "wrong";
    host.dataset.wrongTries = String(state.wrongTries);
    host.dataset.lastResult = "wrong";
  }

  function judgeHeld() {
    if (!running() || state.locked) return;
    if (!state.held.length) {
      state.needRelease = false;
      state.wrongLatched = false;
      window.clearTimeout(state.wrongTimer);
      state.wrongTimer = null;
      return;
    }
    if (state.needRelease) return;
    const result = Drill.judgeHeld(state.prompt, state.held);
    if (result.state === "right") {
      right();
    } else if (result.state === "wrong" && !state.wrongLatched) {
      if (!state.wrongTimer) state.wrongTimer = window.setTimeout(wrongNow, WRONG_AFTER_MS);
    } else if (result.state === "incomplete") {
      window.clearTimeout(state.wrongTimer);
      state.wrongTimer = null;
    }
  }

  function onMidi(event) {
    const message = Midi.parse(event.data);
    if (!message || message.type === "pedal" || message.note >= Scale.CONTROL_FLOOR) return;
    if (message.type === "on") state.held = [...state.held.filter((n) => n !== message.note), message.note];
    else state.held = state.held.filter((n) => n !== message.note);
    paint();
    judgeHeld();
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
    $("ch-midi").textContent = choice ? `Listening to ${choice.name}.` : "No keyboard is connected. Plug the piano in by USB.";
    if (!choice || !state.listening || choice.id !== state.listening.id) attachInput(choice);
  }

  async function startMidi() {
    if (!navigator.requestMIDIAccess) {
      $("ch-midi").textContent = "This browser has no Web MIDI, so it cannot hear the piano. Use Chrome or Edge.";
      return;
    }
    try {
      state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      $("ch-midi").textContent = "MIDI was refused, so the piano cannot be heard. Allow it in the address bar.";
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
      const words = Work.chordWork(read, spelling());
      $("tr-work").textContent = words;
      host.dataset.work = words;
    } catch (e) {
      $("tr-work").textContent = "";
    }
  }

  async function init() {
    try {
      const [profile, qualities] = await Promise.all([getJson(host.dataset.apiPlayer), getJson(host.dataset.apiQualities)]);
      state.profile = profile;
      state.qualities = qualities;
    } catch (e) {
      say("The chords could not load. " + e.message);
      return;
    }
    const asked = new URLSearchParams(window.location.search);
    const askedKey = Number(asked.get("key"));
    const askedLevel = Number(asked.get("level"));
    const askedMode = asked.get("mode");
    fill($("ch-mode"), MODES, MODES.some(([v]) => v === askedMode) ? askedMode : "drill");
    fill($("ch-key"), Scale.CIRCLE.map((pc) => [pc, Drill.keyName(pc, spelling())]), asked.get("key") !== null && Scale.CIRCLE.includes(askedKey) ? askedKey : Scale.CIRCLE[0]);
    fill($("ch-level"), LEVELS, [1, 2, 3].includes(askedLevel) ? askedLevel : 1);
    host.dataset.running = "no";
    host.dataset.saved = "0";
    refreshWork();
    state.keys = Keys.draw($("ch-keyboard"), KEY_FROM, KEY_TO);
    chooseSetup();
    say("Pick a mode, a key and a level, then Start.");

    for (const id of ["ch-mode", "ch-key", "ch-level"]) $(id).addEventListener("change", chooseSetup);
    $("ch-start").addEventListener("click", () => (running() ? stop() : start()));
    $("ch-hint").addEventListener("click", hint);
    $("ch-skip").addEventListener("click", skip);
    renderResults();
    startMidi();
  }

  if (!Drill || !Scale || !Keys || !Midi || !Setup) say("The page's scripts did not load.");
  else init();
})();
