// improv: the Pieces screen. Browser glue only, built like the reading screen: the piece and the rung, the tempo,
// the mode, a count-in click, the piano's notes against the clock, and the judge's answer drawn on the staff.
// What is played is a stretch cut from the piece (repertoire.js); the judge is the reading judge (reading.js);
// the drawing is staff-view.js; which rung passes is the server's call. Only text is ever put on the page.
(function () {
  "use strict";
  const R = window.ImprovReading;
  const P = window.ImprovRepertoire;
  const Staff = window.ImprovStaffView;
  const Keys = window.ImprovKeyboardView;
  const Input = window.ImprovInput;
  const Timing = window.ImprovTiming;
  const Synth = window.ImprovSynth;
  const Midi = window.ImprovMidi;
  const Setup = window.ImprovSetup;
  const $ = (id) => document.getElementById(id);
  const host = $("repertoire");
  const TICK_MS = 25;
  const AHEAD_S = 0.2;
  const LEAD_S = 0.3;
  const TAIL_MS = 200;
  const SHOW_ME_BEATS = 1;

  const state = {
    profile: null,
    report: null,
    pieces: [],
    takes: [],
    piece: null,
    entry: null,
    rung: null,
    exercise: null,
    layout: null,
    keys: null,
    keyRange: null,
    mode: "idle", // idle | running | showing | over
    kind: "flow",
    ctx: null,
    synth: null,
    anchor: null,
    startAudio: 0,
    nextBeat: 0,
    beats: 0,
    count: 4,
    events: [],
    held: [],
    judged: null,
    step: null,
    timer: null,
    midi: null,
    listening: null,
    pendingFresh: false,
  };

  const say = (text) => ($("rp-status").textContent = text);

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
  const tempo = () => R.clampTempo($("rp-tempo").value);
  const beatMs = () => 60000 / tempo();
  const curtainOn = () => $("rp-curtain").checked;
  const isDrill = () => $("rp-rung").value === P.DRILL;
  const requiredBpm = () => (state.rung && state.rung.key !== P.DRILL ? P.bpmOf(state.rung, state.piece) : null);

  // The rung on the screen: one of the piece's ladder, or a drill of any bars named in the drill fields.
  function chosenRung() {
    if (isDrill()) {
      const last = state.piece.bars;
      const first = Math.min(last, Math.max(1, Number($("rp-from").value) || 1));
      const to = Math.min(last, Math.max(first, Number($("rp-to").value) || first));
      return { key: P.DRILL, kind: "drill", hands: $("rp-hands").value, first_bar: first, last_bar: to, tempo: "slow", line: 80, phrase: null };
    }
    return state.entry.rungs.find((r) => r.key === $("rp-rung").value) || state.entry.rungs[0];
  }

  // --------------------------------------------------------------- the stretch on the screen

  function fresh() {
    if (state.mode === "running" || state.mode === "showing") return;
    state.pendingFresh = false;
    state.rung = chosenRung();
    state.judged = null;
    state.step = null;
    state.exercise = P.exerciseFor(state.piece, state.rung);
    const key = state.exercise.key;
    state.layout = Staff.draw($("rp-staff"), state.exercise, {
      right: "right hand",
      left: "left hand",
      key: `${key} major`,
      signature: R.keyWords(key),
    });
    state.layout.show(0);
    wireHover();
    drawKeyboard();
    lightKeys();
    host.dataset.piece = state.piece.slug;
    host.dataset.rung = state.rung.key;
    host.dataset.saved = "no";
    const active = R.activeNotes(state.exercise).length;
    $("rp-name").textContent = `${state.piece.title}, ${state.piece.composer}`;
    $("rp-rung-line").textContent = `${P.rungWords(state.rung)}. ${active} notes in ${state.exercise.bars} ${state.exercise.bars === 1 ? "bar" : "bars"}.`;
    $("rp-path").textContent = P.pathLine(state.entry, state.rung);
    $("rp-advice").textContent = P.advice(state.rung, state.piece);
    clearResult();
    line();
  }

  function line() {
    const mode = $("rp-mode").value === "step" ? "Step: it waits for you" : "Flow: a bar of clicks, then the pulse never waits";
    const need = requiredBpm();
    const pace = need ? ` To pass, play at ${need} bpm or faster.` : "";
    $("rp-line").textContent = `${tempo()} bpm, ${mode}.${pace} ${curtainOn() ? "The curtain hides what is behind the cursor." : ""}`.trim();
  }

  function drawKeyboard() {
    const range = R.keyboardRange(state.exercise);
    if (!state.keys || !state.keyRange || state.keyRange.from !== range.from || state.keyRange.to !== range.to) {
      state.keys = Keys.draw($("rp-keyboard"), range.from, range.to);
      state.keyRange = range;
    }
  }

  function dueNow() {
    if (state.mode === "running" && state.kind === "step" && state.step) return state.step.waiting();
    if (state.mode === "running" && state.kind === "flow") {
      const beat = runNow() / beatMs();
      return state.exercise.notes
        .filter((n) => Math.abs(n.beat - beat) < Math.min(0.25, n.dur / 2) && state.judged && state.judged.results[n.index].state === "pending")
        .map((n) => n.index);
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
        $("rp-line").textContent = P.noteWords(state.exercise, i, state.judged, spelling());
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
    const firstClick = state.startAudio - state.count * beatS;
    while (state.nextBeat < state.beats) {
      const when = firstClick + state.nextBeat * beatS;
      if (when > horizon) break;
      const inCount = state.nextBeat < state.count;
      const accent = inCount ? state.nextBeat % state.exercise.beats === 0 : (state.nextBeat - state.count) % state.exercise.beats === 0;
      state.synth.play({ voice: "click", accent, velocity: inCount ? 1 : 0.7 }, when, 0.05);
      state.nextBeat += 1;
    }
  }

  function judgeNow(final) {
    const now = final ? undefined : runNow();
    const notes = R.activeNotes(state.exercise);
    const judged = R.judge({ notes, tempo: tempo(), events: state.events, latencyMs: state.profile ? state.profile.latency_offset_ms : 0, now });
    // The hand not being asked for is "out" in the full-length result the staff is painted from.
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
    const endMs = state.exercise.bars * state.exercise.beats * beatMs();
    if (now > endMs + TAIL_MS) {
      finish();
      return;
    }
    say(now < 0 ? `Count-in: ${Math.max(1, Math.ceil(-now / beatMs()))}` : "Play.");
    state.layout.place(Math.max(0, now / beatMs()), curtainOn(), 0);
    judgeNow(false);
  }

  // ------------------------------------------------------------------ run, step, show, finish

  async function start() {
    if (state.mode === "running" || state.mode === "showing" || !state.exercise) return;
    if (state.pendingFresh || isDrill()) fresh();
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    state.kind = $("rp-mode").value === "step" ? "step" : "flow";
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
      state.step = R.createStepRun(state.exercise.notes, [0, state.exercise.bars - 1], state.exercise.hands);
      state.step.arrive(performance.now());
      Staff.paint(state.layout, state.step.summary(), state.step.waiting());
      state.layout.place(state.step.target(), curtainOn(), 0);
      host.dataset.target = String(state.step.target());
      lightKeys();
      say("Step: play what is under the cursor. It waits for you.");
      return;
    }
    const bpm = tempo();
    $("rp-tempo").value = bpm;
    state.count = P.countIn(state.exercise.beats);
    state.beats = state.count + state.exercise.bars * state.exercise.beats;
    state.nextBeat = 0;
    state.startAudio = state.ctx.currentTime + LEAD_S + (state.count * beatMs()) / 1000;
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
    state.layout.show(0);
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
    const rung = state.rung;
    const exercise = state.exercise;
    $("rp-verdict").textContent = P.verdict({ ...result, passed: result.score >= rung.line && result.mode === "flow" && tempo() >= (requiredBpm() || 0) && rung.key !== P.DRILL }, rung);
    $("m-pitch").textContent = `${Math.round(result.pitchAccuracy * 100)}%`;
    $("m-time").textContent = `${Math.round(result.timingAccuracy * 100)}%`;
    $("m-score").textContent = String(result.score);
    const spots = $("rp-spots");
    spots.textContent = "";
    for (const text of R.spotWords(exercise, result)) spots.appendChild(make("li", text, "im-list-item"));
    const fix = $("rp-fix");
    fix.textContent = "";
    for (const bar of P.badBars(exercise, result).slice(0, 4)) {
      const button = make("button", `Drill bar ${bar}`, "im-btn im-btn-quiet im-btn-small");
      button.type = "button";
      button.title = "Step mode, this bar only, the same hands";
      button.addEventListener("click", () => drillBar(bar));
      fix.appendChild(button);
    }
    const before = state.entry.next;
    const record = P.toRecord(state.piece, rung, exercise, result, { tempo: tempo(), curtain: curtainOn(), events: state.events });
    state.mode = "idle";
    try {
      const saved = await send("POST", host.dataset.apiTakes, record);
      state.takes.unshift(saved);
      listTakes();
      showBest();
      host.dataset.saved = "yes";
      if (saved.passed) $("rp-verdict").textContent = P.verdict({ ...result, passed: true }, rung);
      await refreshReport();
      if (saved.passed && rung.key === before) advance();
      else if (saved.passed) say("Passed. The path is still at an earlier step.");
      else if (result.mode === "flow" && rung.key !== P.DRILL) say(notYet(result, rung));
      else if (result.mode === "step") say("Saved. Step mode is for fixing; pass the rung in Flow to move on.");
      else say("Saved. A drill is for fixing; it never counts as a pass.");
    } catch (e) {
      say("The take could not be saved. " + e.message);
    }
  }

  function notYet(result, rung) {
    const need = requiredBpm();
    if (result.score >= rung.line && need && tempo() < need) return `A good score, but this rung counts at ${need} bpm or faster.`;
    return "Not yet. Play it again, or slow the tempo.";
  }

  // A pass on the path's own rung moves the path on. The result stays on the staff to be looked at; the next
  // rung is drawn at the next Start or Next.
  function advance() {
    const next = state.entry.next;
    if (!next) {
      say("Passed. This piece is finished. Try another, or play it again as a performance.");
      return;
    }
    $("rp-rung").value = next;
    setTempoFor(state.entry.rungs.find((r) => r.key === next));
    state.pendingFresh = true;
    host.dataset.rung = next;
    const rung = state.entry.rungs.find((r) => r.key === next);
    say(`Passed. Next: ${P.rungWords(rung)}. Press Start when you are ready.`);
  }

  function drillBar(bar) {
    if (state.mode === "running" || state.mode === "showing") return;
    $("rp-rung").value = P.DRILL;
    $("rp-hands").value = state.exercise.hands;
    $("rp-from").value = bar;
    $("rp-to").value = bar;
    $("rp-mode").value = "step";
    showDrillFields();
    fresh();
    start();
  }

  async function showMe() {
    if (state.mode === "running" || state.mode === "showing" || !state.exercise) return;
    if (state.pendingFresh || isDrill()) fresh();
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    state.mode = "showing";
    host.dataset.running = "yes";
    lock(true);
    const beatS = beatMs() / 1000;
    state.startAudio = state.ctx.currentTime + LEAD_S + SHOW_ME_BEATS * beatS;
    state.anchor = null;
    const heard = R.activeNotes(state.exercise);
    for (const n of heard) state.synth.play({ voice: "demo", midi: n.midi, velocity: 0.75 }, state.startAudio + n.beat * beatS, (n.hold || n.dur) * beatS * 0.9);
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
      const on = heard.filter((n) => beat >= n.beat && beat < n.beat + (n.hold || n.dur)).map((n) => n.index);
      Staff.light(state.layout, on);
      if (state.keys) Keys.light(state.keys, on.map((i) => ({ midi: state.exercise.notes[i].midi, className: "im-key-chord" })));
      state.layout.place(Math.max(0, beat), false, 0);
    }, TICK_MS);
  }

  function clearResult() {
    $("rp-verdict").textContent = "";
    $("rp-spots").textContent = "";
    $("rp-fix").textContent = "";
    for (const id of ["m-pitch", "m-time", "m-score"]) $(id).textContent = "-";
    showBest();
  }

  function showBest() {
    const mine = state.takes.filter((t) => t.piece === state.piece.slug && t.rung === state.rung.key && t.mode === "flow");
    if (state.rung.key === P.DRILL) {
      $("rp-best").textContent = "A drill is not scored toward the path.";
      return;
    }
    if (!mine.length) {
      $("rp-best").textContent = "You have not played this rung in Flow yet.";
      return;
    }
    const best = mine.reduce((a, b) => (b.score > a.score ? b : a));
    $("rp-best").textContent = `Your best here: ${best.score}${best.passed ? ", passed" : ""}, at ${best.tempo_bpm} bpm.`;
  }

  function lock(running) {
    for (const id of ["rp-piece", "rp-rung", "rp-hands", "rp-from", "rp-to", "rp-tempo", "rp-mode", "rp-curtain"]) $(id).disabled = running;
    $("rp-start").textContent = running ? "Stop" : "Start";
    $("rp-show").disabled = running;
    $("rp-next").disabled = running;
  }

  function listTakes() {
    const list = $("rp-takes");
    list.textContent = "";
    const mine = state.takes.filter((t) => t.piece === state.piece.slug);
    if (!mine.length) {
      list.appendChild(make("li", "No takes of this piece yet.", "im-list-item"));
      return;
    }
    for (const t of mine.slice(0, 10)) {
      const rung = t.rung === P.DRILL ? { key: P.DRILL, hands: t.hands, first_bar: t.first_bar, last_bar: t.last_bar } : state.entry.rungs.find((r) => r.key === t.rung);
      const words = rung ? P.rungWords(rung) : t.rung;
      list.appendChild(make("li", `${words}, ${t.mode}, ${t.tempo_bpm} bpm: ${t.score}${t.passed ? " (passed)" : ""}`, "im-list-item"));
    }
  }

  async function refreshReport() {
    try {
      state.report = await getJson(host.dataset.apiRepertoire);
      state.entry = state.report.pieces.find((p) => p.slug === state.piece.slug) || state.entry;
      fillPieces();
      fillRungs(true);
      $("rp-path").textContent = P.pathLine(state.entry, state.rung);
    } catch (e) {
      // the line keeps what it had
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
        state.layout.place(state.step.target(), curtainOn(), 0);
        host.dataset.target = String(state.step.target());
        say(outcome.right ? "Play." : "Not that one. Look again.");
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
    $("rp-midi").textContent = choice ? `Listening to ${choice.name}.` : "No keyboard is connected. Plug the piano in by USB.";
    if (!choice || !state.listening || choice.id !== state.listening.id) attachInput(choice);
  }

  function stopMidi() {
    if (state.midi) state.midi.onstatechange = null;
    attachInput(null);
  }

  async function startMidi() {
    if (!navigator.requestMIDIAccess) {
      $("rp-midi").textContent = "This browser has no Web MIDI, so it cannot hear the piano. Use Chrome or Edge.";
      return;
    }
    try {
      state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      $("rp-midi").textContent = "MIDI was refused, so the piano cannot be heard. Allow it in the address bar.";
      return;
    }
    state.midi.onstatechange = listInputs;
    listInputs();
  }

  // ----------------------------------------------------------------------- the controls

  function fillPieces() {
    const select = $("rp-piece");
    const keep = state.piece ? state.piece.slug : select.value;
    select.textContent = "";
    for (const entry of state.report.pieces) {
      const option = make("option", P.pieceLine(entry));
      option.value = entry.slug;
      select.appendChild(option);
    }
    if (keep) select.value = keep;
  }

  // The rung list, grouped the way a teacher groups the work: each phrase, then the joins and the whole piece.
  function fillRungs(keepChoice) {
    const select = $("rp-rung");
    const keep = keepChoice ? select.value : null;
    select.textContent = "";
    const groups = new Map();
    for (const rung of state.entry.rungs) {
      const g = P.groupOf(rung, state.piece);
      if (!groups.has(g.id)) {
        const el = document.createElement("optgroup");
        el.label = g.label;
        groups.set(g.id, el);
        select.appendChild(el);
      }
      const mark = rung.passed ? `, passed ${rung.best === null ? "" : rung.best}`.trim() : rung.key === state.entry.next ? ", next" : "";
      const option = make("option", `${P.rungWords(rung)}${mark}`);
      option.value = rung.key;
      groups.get(g.id).appendChild(option);
    }
    const drill = document.createElement("optgroup");
    drill.label = "Mending";
    const option = make("option", "Drill any bars and hands (never passes)");
    option.value = P.DRILL;
    drill.appendChild(option);
    select.appendChild(drill);
    const wanted = keep && [...select.options].some((o) => o.value === keep) ? keep : state.entry.next || state.entry.rungs[0].key;
    select.value = wanted;
  }

  function showDrillFields() {
    $("rp-drill").hidden = !isDrill();
  }

  function setTempoFor(rung) {
    if (rung) $("rp-tempo").value = P.bpmOf(rung, state.piece);
  }

  function choosePiece(slug, rungKey) {
    state.piece = state.pieces.find((p) => p.slug === slug) || state.pieces[0];
    state.entry = state.report.pieces.find((p) => p.slug === state.piece.slug);
    $("rp-from").max = String(state.piece.bars);
    $("rp-to").max = String(state.piece.bars);
    $("rp-from").value = "1";
    $("rp-to").value = String(Math.min(4, state.piece.bars));
    fillRungs(false);
    if (rungKey && [...$("rp-rung").options].some((o) => o.value === rungKey)) $("rp-rung").value = rungKey;
    showDrillFields();
    setTempoFor(isDrill() ? { tempo: "slow" } : state.entry.rungs.find((r) => r.key === $("rp-rung").value));
    fresh();
    listTakes();
  }

  function nextRung() {
    if (state.mode === "running" || state.mode === "showing") return;
    const options = [...$("rp-rung").options].map((o) => o.value).filter((v) => v !== P.DRILL);
    const at = options.indexOf($("rp-rung").value);
    if (at < 0 || at >= options.length - 1) {
      say("That is the last rung of this piece.");
      return;
    }
    $("rp-rung").value = options[at + 1];
    onRungChange();
  }

  function onRungChange() {
    showDrillFields();
    setTempoFor(isDrill() ? { tempo: "slow" } : state.entry.rungs.find((r) => r.key === $("rp-rung").value));
    if (isDrill()) $("rp-mode").value = "step";
    fresh();
  }

  async function init() {
    try {
      const [profile, pieces, takes, report] = await Promise.all([getJson(host.dataset.apiPlayer), getJson(host.dataset.apiPieces), getJson(host.dataset.apiTakes), getJson(host.dataset.apiRepertoire)]);
      state.profile = profile;
      state.pieces = pieces;
      state.takes = takes;
      state.report = report;
    } catch (e) {
      say("The pieces could not load. " + e.message);
      return;
    }
    if (!state.pieces.length || !state.report.pieces.length) {
      say("There are no pieces yet.");
      return;
    }
    const asked = new URLSearchParams(window.location.search);
    fillPieces();
    const first = state.report.pieces.find((p) => !p.done) || state.report.pieces[0];
    const slug = state.report.pieces.some((p) => p.slug === asked.get("piece")) ? asked.get("piece") : first.slug;
    $("rp-piece").value = slug;
    if (asked.get("mode") === "step") $("rp-mode").value = "step";
    choosePiece(slug, asked.get("rung"));
    $("rp-start").disabled = false;
    $("rp-show").disabled = false;
    $("rp-next").disabled = false;
    say(state.piece.blurb || "Pick a piece, then Start.");

    $("rp-piece").addEventListener("change", () => {
      choosePiece($("rp-piece").value, null);
      say(state.piece.blurb || "");
    });
    $("rp-rung").addEventListener("change", onRungChange);
    for (const id of ["rp-hands", "rp-from", "rp-to"]) $(id).addEventListener("change", () => fresh());
    $("rp-mode").addEventListener("change", () => {
      fresh();
    });
    $("rp-curtain").addEventListener("change", () => line());
    $("rp-tempo").addEventListener("change", () => {
      $("rp-tempo").value = tempo();
      line();
    });
    $("rp-start").addEventListener("click", () => (state.mode === "running" || state.mode === "showing" ? stop() : start()));
    $("rp-show").addEventListener("click", showMe);
    $("rp-next").addEventListener("click", nextRung);
    if (Input) Input.attach({ status: $("rp-midi"), deliver: onMidi, midiStart: startMidi, midiStop: stopMidi }).start();
    else startMidi();
  }

  // For the tests and the console: the stretch on the screen, and a note as if the piano sent it.
  window.ImprovRepertoirePage = {
    exercise: () => state.exercise,
    rung: () => state.rung,
    active: () => R.activeNotes(state.exercise),
    press: (midi) => onMidi({ data: Uint8Array.from([0x90, midi, 90]), timeStamp: performance.now() }),
  };
  if (!R || !P || !Staff || !Keys || !Timing || !Synth || !Midi || !Setup) say("The page's scripts did not load.");
  else init();
})();
