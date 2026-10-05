// improv: the Play screen. Browser glue only: read the controls, call ImprovPlay, draw.
// The rules live in play.js, band.js and scheduler.js, which are tested under Node.
(function () {
  "use strict";
  const P = window.ImprovPlay;
  const Band = window.ImprovBand;
  const Sched = window.ImprovScheduler;
  const Synth = window.ImprovSynth;
  const View = window.ImprovChartView;
  const Out = window.ImprovOutput;
  const M = window.ImprovMidi;
  const S = window.ImprovSetup;
  const Rec = window.ImprovRecognize;
  const Timing = window.ImprovTiming;
  const J = window.ImprovJudge;
  const Pr = window.ImprovPractice;
  const Keys = window.ImprovKeyboardView;
  const FIRST_KEY = 36; // C2
  const LAST_KEY = 96; // C7
  const JUDGE_EVERY_FRAMES = 6;
  const $ = (id) => document.getElementById(id);

  const host = $("play");
  const state = {
    progressions: [],
    styles: [],
    qualities: [],
    progression: null,
    style: null,
    built: null,
    ctx: null,
    synth: null,
    scheduler: null,
    playing: false,
    frame: 0,
    cells: [],
    pending: null,
    sinkId: "",
    outputs: [],
    profile: null,
    midi: null,
    listening: null,
    inputs: null,
    keys: null,
    held: [],
    take: null,
    judged: null,
    frames: 0,
    session: null,
    sessionPromise: null,
    exercise: null,
    clock: Pr.createClock(),
    lastActiveAt: 0,
    reportedSeconds: -1,
  };

  const MIX = [
    { name: "drums", label: "Drums" },
    { name: "bass", label: "Bass" },
    { name: "comp", label: "Comping" },
    { name: "click", label: "Click" },
  ];
  const mix = { drums: { level: 0.8, muted: false }, bass: { level: 0.9, muted: false }, comp: { level: 0.7, muted: false }, click: { level: 0.8, muted: false } };

  const say = (text) => ($("play-status").textContent = text);

  function showError(text) {
    $("play-error").hidden = !text;
    $("play-error").textContent = text || "";
  }

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  // ------------------------------------------------------------------ settings

  function readSettings() {
    return {
      key: $("key").value,
      bpm: $("bpm").value,
      swing: $("swing").value,
      first: $("first").value,
      last: $("last").value,
      countIn: Number($("countin").value),
      metronome: $("metronome").checked,
    };
  }

  function fillOptions(select, items, selected) {
    select.textContent = "";
    for (const [value, label] of items) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    }
    if (selected !== undefined) select.value = selected;
  }

  function fillProgressions() {
    const select = $("progression");
    select.textContent = "";
    const byGenre = new Map();
    for (const p of state.progressions) {
      if (!byGenre.has(p.genre)) byGenre.set(p.genre, []);
      byGenre.get(p.genre).push(p);
    }
    for (const [genre, list] of byGenre) {
      const group = document.createElement("optgroup");
      group.label = genre.charAt(0).toUpperCase() + genre.slice(1);
      for (const p of list) {
        const option = document.createElement("option");
        option.value = p.slug;
        option.textContent = p.title;
        group.appendChild(option);
      }
      select.appendChild(group);
    }
  }

  function fillStyles() {
    const wanted = state.progression.time_signature;
    const fits = state.styles.filter((s) => s.time_signature === wanted);
    fillOptions($("style"), fits.map((s) => [String(s.id), s.name]));
  }

  // Choosing a progression sets everything that came with it; later edits are the player's.
  function chooseProgression(slug) {
    state.progression = state.progressions.find((p) => p.slug === slug) || state.progressions[0];
    if (!state.progression) return;
    $("progression").value = state.progression.slug;
    fillStyles();
    const style = P.pickStyle(state.progression, state.styles);
    state.style = style;
    if (style) $("style").value = String(style.id);
    const settings = P.defaultSettings(state.progression, style);
    fillOptions($("key"), P.keyOptions(state.progression.home_key).map((k) => [k, k]), settings.key);
    $("bpm").value = settings.bpm;
    $("swing").value = settings.swing;
    $("first").value = "";
    $("last").value = "";
    $("metronome").checked = false;
    refresh();
  }

  function chooseStyle() {
    state.style = state.styles.find((s) => String(s.id) === $("style").value) || null;
    if (state.playing) {
      // A new band mid-take keeps the player's tempo and feel; only the tempo is held to its range.
      const bpm = P.clampTempo(state.style, $("bpm").value);
      $("bpm").value = bpm;
      state.scheduler.setBpm(bpm);
      applyLive(`${state.style.name} from the next bar.`);
      return;
    }
    if (state.style) {
      $("bpm").value = P.clampTempo(state.style, state.style.default_tempo);
      $("swing").value = P.defaultSwingMode(state.style);
    }
    refresh();
  }

  // ------------------------------------------------------------------- drawing

  function drawChart() {
    state.cells = [];
    $("chart").textContent = "";
    if (!state.built || !state.built.ok) return;
    const rows = P.layoutBars(state.built.chart, state.built.from, state.built.to);
    state.cells = View.draw($("chart"), rows);
  }

  function clearLit() {
    for (const c of state.cells) {
      if (!c) continue;
      c.el.classList.remove("im-bar-lit");
      c.beat.style.width = "0";
    }
    const box = $("count-in");
    box.hidden = true;
    box.textContent = "";
  }

  function frame() {
    state.frame = 0;
    if (!state.playing) return;
    if (state.pending && state.ctx.currentTime >= state.pending.at) {
      state.built = state.pending.built;
      state.pending = null;
      $("chart-title").textContent = `${state.progression.title}, ${state.built.key}`;
      drawChart();
    }
    anchorTake();
    state.frames += 1;
    if (state.frames % JUDGE_EVERY_FRAMES === 0 && state.take && state.take.events.length) judgeLive(false);
    const lit = P.litFor(state.built, state.scheduler.barAt(state.ctx.currentTime));
    for (const c of state.cells) if (c) c.el.classList.remove("im-bar-lit");
    const box = $("count-in");
    if (lit && lit.countIn) {
      box.hidden = false;
      box.textContent = `Count-in ${lit.number}/${lit.of}: ${Math.min(state.built.plan.beatsPerBar, Math.floor(lit.beat) + 1)}`;
    } else {
      box.hidden = true;
      if (lit && state.cells[lit.bar]) {
        const c = state.cells[lit.bar];
        c.el.classList.add("im-bar-lit");
        c.beat.style.width = Math.min(100, (lit.beat / state.built.plan.beatsPerBar) * 100) + "%";
        c.el.scrollIntoView({ block: "nearest" });
      }
    }
    state.frame = requestAnimationFrame(frame);
  }

  function refresh() {
    if (!state.progression || !state.style) {
      state.built = null;
      showError(state.progression ? "No band fits this progression's bar length." : "");
      drawChart();
      $("play-toggle").disabled = true;
      return;
    }
    const settings = readSettings();
    state.built = P.buildPlan({ progression: state.progression, style: state.style, qualities: state.qualities, settings });
    showError(state.built.ok ? "" : state.built.error);
    $("chart-title").textContent = `${state.progression.title}, ${settings.key}`;
    drawChart();
    $("play-toggle").disabled = !state.built.ok;
    showExercise();
  }

  // ---------------------------------------------------------------- exercise

  // Say whether what is on the screen is still the exercise. The result line is the judge's own.
  function showExercise() {
    if (!state.exercise) return;
    const on = P.exerciseApplies(state.exercise, state.progression, state.built);
    $("exercise-goal").textContent = P.exerciseGoalLine(state.exercise, on);
    if (!on) $("exercise-result").textContent = "";
  }

  // Put the band where the exercise asks for it: its chart and band, its key and tempo, its bars.
  async function openExercise(slug) {
    let found;
    try {
      found = (await getJson(host.dataset.apiExercises)).find((e) => e.slug === slug);
    } catch (e) {
      showError("The exercise could not be loaded, so this is free play. " + e.message);
      return;
    }
    if (!found) {
      showError("There is no exercise by that name, so this is free play.");
      return;
    }
    state.exercise = found;
    chooseProgression(found.progression_slug);
    if (state.progression.id !== found.progression) {
      state.exercise = null;
      showError("The exercise's chart is not in the library, so this is free play.");
      return;
    }
    const style = state.styles.find((s) => s.id === found.style);
    if (style && style.time_signature === state.progression.time_signature) {
      state.style = style;
      $("style").value = String(style.id);
    }
    if ($("key").value !== found.key) {
      const option = document.createElement("option");
      option.value = found.key;
      option.textContent = found.key;
      $("key").appendChild(option);
      $("key").value = found.key;
    }
    $("bpm").value = P.clampTempo(state.style, found.tempo);
    $("swing").value = P.defaultSwingMode(state.style);
    refresh();
    if (state.built && state.built.ok) {
      const range = P.exerciseRange(found, state.built.chart.bars.length);
      $("first").value = range.first;
      $("last").value = range.last;
      refresh();
    }
    $("exercise-title").textContent = found.title;
    $("exercise-instructions").textContent = found.instructions;
    if (found.lesson) $("exercise-back").href = `/improv/lessons/${encodeURIComponent(found.lesson)}/`;
    $("exercise-panel").hidden = false;
    showExercise();
  }

  // A change made while it plays: build the new plan, hand it to the scheduler for the next bar
  // line, and redraw the chart when that bar line arrives so the screen and the sound agree.
  function applyLive(message) {
    const settings = readSettings();
    const next = P.buildPlan({ progression: state.progression, style: state.style, qualities: state.qualities, settings });
    if (!next.ok) {
      showError(next.error);
      return false;
    }
    if (!P.canGoLive(state.built, next)) {
      showError("That change has to wait until you stop.");
      return false;
    }
    const at = state.scheduler.setPlan(next.plan);
    if (at === null) {
      showError("That change has to wait until you stop.");
      return false;
    }
    showError("");
    state.pending = { at: state.pending ? Math.min(state.pending.at, at) : at, built: next };
    say(message);
    return true;
  }

  function settingChanged() {
    if (!state.playing) {
      refresh();
      return;
    }
    const settings = readSettings();
    applyLive(`${settings.swing === "swing" ? "Swing" : "Straight"} feel, ${settings.key}: from the next bar.`);
  }

  function tempoChanged() {
    const bpm = P.clampTempo(state.style, $("bpm").value);
    $("bpm").value = bpm;
    if (!state.playing) return;
    state.scheduler.setBpm(bpm);
    say(`${bpm} bpm from the next bar.`);
  }

  // ------------------------------------------------------------------- you

  // The take being recorded: every MIDI event on the take's own clock, and the anchor that
  // ties the piano's clock to the band's. The judge runs over it live, with `now`, and the
  // same events are what SPR-I.4.3 posts.
  function newTake() {
    return { events: [], anchor: null, startedAt: new Date().toISOString() };
  }

  async function send(method, url, body) {
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      keepalive: true,
      headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": host.dataset.csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data ? Object.values(data).flat().join(" ") : `${url} answered ${response.status}`);
    return data;
  }

  // One sitting is one session: opened the first time the band starts or a note is played, and
  // closed when the page goes or after thirty idle minutes. Its active seconds are what the
  // timer counted, the band running or a note in the last ten seconds, which is what the daily
  // goal counts. The page reports them every thirty seconds.
  const clockNow = () => performance.now();

  function ensureSession() {
    if (!state.sessionPromise) {
      state.sessionPromise = send("POST", host.dataset.apiSessions, {}).then(
        (row) => (state.session = row),
        (e) => {
          state.sessionPromise = null;
          throw e;
        }
      );
    }
    return state.sessionPromise;
  }

  // Before anything is counted: if the last sitting went cold, close it and start afresh.
  function rollSittingIfCold() {
    const t = clockNow();
    if (!state.session || state.playing || !Pr.sittingIsOver(state.lastActiveAt, t)) return;
    closeSession(new Date(Date.now() - (t - state.lastActiveAt)));
    state.session = null;
    state.sessionPromise = null;
    state.clock = Pr.createClock();
    state.reportedSeconds = -1;
  }

  function closeSession(endedAt) {
    if (!state.session) return;
    send("PATCH", `${host.dataset.apiSessions}${state.session.id}/`, {
      active_seconds: state.clock.seconds(clockNow()),
      ended_at: (endedAt || new Date()).toISOString(),
    }).catch(() => {});
  }

  async function reportSession() {
    if (!state.session) return;
    const seconds = state.clock.seconds(clockNow());
    if (seconds === state.reportedSeconds) return;
    state.reportedSeconds = seconds;
    try {
      await send("PATCH", `${host.dataset.apiSessions}${state.session.id}/`, { active_seconds: seconds });
      await showPractice();
    } catch (e) {
      state.reportedSeconds = -1;
    }
  }

  async function showPractice() {
    if (!host.dataset.apiPractice) return;
    try {
      const response = await fetch(host.dataset.apiPractice, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) return;
      const report = await response.json();
      const streak = report.streak ? ` Streak: ${report.streak} ${report.streak === 1 ? "day" : "days"}.` : "";
      $("practice-line").textContent = Pr.goalLine(report) + streak;
    } catch (e) {
      // The line is a convenience; the page works without it.
    }
  }

  function noteActivity() {
    rollSittingIfCold();
    state.clock.notePlayed(clockNow());
    state.lastActiveAt = clockNow();
    ensureSession().catch(() => {});
  }

  // Every play-through with a note in it is recorded, whole, with the chart, key, tempo and
  // feel it was played over, and the verdict the judge gave it (spec ch. 5 and 6).
  async function postTake(take, judged, built, bpm, swingRatio) {
    const last = take.events.length ? take.events[take.events.length - 1].t_ms : 0;
    const body = {
      session: (await ensureSession()).id,
      progression: state.progression ? state.progression.id : null,
      style: state.style ? state.style.id : null,
      exercise: P.exerciseApplies(state.exercise, state.progression, state.built) ? state.exercise.slug : null,
      chart: state.progression.chart,
      home_key: state.progression.home_key,
      key: built.key,
      time_signature: state.progression.time_signature,
      tempo: bpm,
      swing_ratio: swingRatio.toFixed(2),
      loop_from: built.from,
      loop_to: built.to,
      started_at: take.startedAt,
      duration_ms: Math.max(0, Math.round(Math.max(last, take.endedAtMs || 0))),
      bars: built.to - built.from,
      events: take.events,
      score: judged.score,
      metrics: judged.metrics,
      judge_version: judged.version,
    };
    $("take-status").textContent = "Saving the take.";
    try {
      const saved = await send("POST", host.dataset.apiTakes, body);
      const earned = P.completionNote(saved);
      $("take-status").textContent = `Take ${saved.id} saved: ${judged.metrics.notes} notes.` + (earned ? " " + earned : "");
      if (earned && state.exercise) {
        state.exercise.completed = true;
        showExercise();
      }
    } catch (e) {
      $("take-status").textContent = "The take was not saved. " + e.message;
    }
  }

  function swingRatioNow() {
    return $("swing").value === "swing" && state.style ? Number(state.style.swing_ratio) : 0.5;
  }

  function takeNow() {
    if (!state.playing || !state.scheduler) return null;
    return P.takeTimeMs(state.scheduler.barAt(state.ctx.currentTime), state.built, state.scheduler.bpm);
  }

  function takeTimeOf(perfMs) {
    if (!state.playing || !state.take || !state.take.anchor) return null;
    const audio = Timing.audioAt(state.take.anchor, perfMs);
    return P.takeTimeMs(state.scheduler.barAt(audio), state.built, state.scheduler.bpm);
  }

  function anchorTake() {
    if (!state.take || state.take.anchor || !state.ctx) return;
    try {
      state.take.anchor = Timing.makeAnchor(state.ctx.getOutputTimestamp());
    } catch (e) {
      // not producing sound yet; try again next frame
    }
  }

  function judgeLive(final) {
    if (!state.take || !state.built || !state.built.ok) return;
    const now = final ? undefined : takeNow();
    state.judged = J.judge({
      events: state.take.events,
      chart: state.built.chart,
      from: state.built.from,
      to: state.built.to,
      bpm: state.scheduler.bpm,
      swingRatio: swingRatioNow(),
      qualities: state.qualities,
      scoring: P.exerciseScoring(P.exerciseApplies(state.exercise, state.progression, state.built) ? state.exercise : null, J.SCORING_KINDS),
      latencyOffsetMs: state.profile ? state.profile.latency_offset_ms : 0,
      grid: "beat",
      now: now === null ? undefined : now,
    });
    $("feedback").textContent = P.liveSummary(state.judged);
    if (state.exercise && P.exerciseApplies(state.exercise, state.progression, state.built)) {
      $("exercise-result").textContent = P.exerciseVerdict(state.judged.score, state.exercise.pass_score);
    }
    lightKeys();
  }

  // Each held key wears the colour of the last judgement of that note.
  function lightKeys() {
    const latest = new Map();
    for (const n of state.judged ? state.judged.notes : []) latest.set(n.note, n);
    Keys.light(
      state.keys,
      state.held.map((midi) => ({ midi, className: P.keyClassFor(latest.get(midi)) }))
    );
    const spelling = state.profile ? state.profile.note_names : "sharps";
    const read = Rec.recognize(state.held, state.qualities, { spelling });
    $("heard").textContent = read.kind === "chord" ? read.name + (read.exact ? "" : "?") : read.kind === "notes" ? read.text : "";
  }

  function onMidi(event) {
    const message = M.parse(event.data);
    if (!message || message.type === "pedal") return;
    if (message.type === "on") noteActivity();
    if (message.type === "on") state.held = [...state.held.filter((n) => n !== message.note), message.note];
    else state.held = state.held.filter((n) => n !== message.note);
    const t = takeTimeOf(event.timeStamp);
    if (state.take && t !== null) {
      state.take.events.push({ t_ms: Math.round(t), type: message.type, note: message.note, velocity: message.velocity || 0 });
      judgeLive(false);
    } else {
      lightKeys();
    }
  }

  function attachInput(choice) {
    for (const port of state.midi ? state.midi.inputs.values() : []) port.onmidimessage = null;
    state.listening = choice || null;
    state.held = [];
    lightKeys();
    if (!choice) return;
    const port = state.midi.inputs.get(choice.id);
    if (port) port.onmidimessage = onMidi;
  }

  function listInputs() {
    const before = state.inputs;
    state.inputs = S.inputChoices(Array.from(state.midi.inputs.values()));
    const news = S.describeChange(S.changes(before, state.inputs), state.listening ? state.listening.name : "");
    const remembered = state.listening ? state.listening.name : state.profile ? state.profile.midi_input_name : "";
    const choice = S.pickInput(state.inputs, remembered);
    const sentence = choice ? `Listening to ${choice.name}.` : "No keyboard is connected. Plug the piano in by USB.";
    $("midi-state").textContent = news ? `${sentence} ${news}` : sentence;
    if (!choice || !state.listening || choice.id !== state.listening.id) attachInput(choice);
  }

  async function startMidi() {
    if (!navigator.requestMIDIAccess) {
      $("midi-state").textContent = "This browser has no Web MIDI, so it cannot hear the piano. Use Chrome or Edge.";
      return;
    }
    try {
      state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      $("midi-state").textContent = "MIDI was refused, so the piano cannot be heard. Allow it in the address bar.";
      return;
    }
    state.midi.onstatechange = listInputs;
    listInputs();
  }

  // ----------------------------------------------------------------- the mix

  function buildMix() {
    const box = $("mix");
    for (const part of MIX) {
      const row = document.createElement("div");
      row.className = "im-mix-row";
      const label = document.createElement("span");
      label.className = "im-mix-name";
      label.textContent = part.label;
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = "0";
      slider.max = "100";
      slider.value = String(Math.round(mix[part.name].level * 100));
      slider.setAttribute("aria-label", part.label + " level");
      const mute = document.createElement("label");
      mute.className = "im-check";
      const check = document.createElement("input");
      check.type = "checkbox";
      mute.appendChild(check);
      mute.appendChild(document.createTextNode(" Mute"));
      slider.addEventListener("input", () => {
        mix[part.name].level = Number(slider.value) / 100;
        applyMix();
      });
      check.addEventListener("change", () => {
        mix[part.name].muted = check.checked;
        applyMix();
      });
      row.append(label, slider, mute);
      box.appendChild(row);
    }
  }

  function applyMix() {
    if (!state.synth) return;
    for (const part of MIX) {
      state.synth.setLevel(part.name, mix[part.name].level);
      state.synth.setMuted(part.name, mix[part.name].muted);
    }
  }

  // ---------------------------------------------------------------- transport

  function lockSettings(locked) {
    for (const id of P.LOCKED_CONTROLS) $(id).disabled = locked;
  }

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
    applyMix();
    if (state.sinkId) applySink().catch(sinkFailed);
  }

  async function start() {
    refresh();
    if (!state.built || !state.built.ok) return;
    rollSittingIfCold();
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    const bpm = P.clampTempo(state.style, $("bpm").value);
    $("bpm").value = bpm;
    state.scheduler.start(state.built.plan, { bpm, loop: true, loopFrom: state.built.loopFrom });
    state.playing = true;
    state.take = newTake();
    state.judged = null;
    state.clock.bandStarted(clockNow());
    state.lastActiveAt = clockNow();
    $("feedback").textContent = "Play something.";
    $("take-status").textContent = "";
    ensureSession().catch((e) => ($("take-status").textContent = "No session could be opened. " + e.message));
    lockSettings(true);
    $("play-toggle").textContent = "Stop";
    say(state.built.metronome ? "Metronome." : `${state.style.name}, ${bpm} bpm, ${state.built.key}.`);
    if (!state.frame) state.frame = requestAnimationFrame(frame);
  }

  function stop() {
    if (state.take && state.take.events.length) {
      state.take.endedAtMs = takeNow() || 0;
      judgeLive(true);
      postTake(state.take, state.judged, state.built, state.scheduler.bpm, swingRatioNow());
    }
    state.clock.bandStopped(clockNow());
    state.lastActiveAt = clockNow();
    reportSession();
    state.take = null;
    if (state.scheduler) state.scheduler.stop();
    state.playing = false;
    state.pending = null;
    if (state.frame) cancelAnimationFrame(state.frame);
    state.frame = 0;
    clearLit();
    lockSettings(false);
    refresh();
    $("play-toggle").textContent = "Play";
    say("Stopped.");
  }

  function toggle() {
    if ($("play-toggle").disabled) return;
    if (state.playing) stop();
    else start().catch((e) => showError("The sound could not start: " + e.message));
  }

  // ------------------------------------------------------------------- output

  async function applySink() {
    if (state.ctx) await state.ctx.setSinkId(state.sinkId);
  }

  function sinkFailed(e) {
    state.sinkId = "";
    $("output").value = "";
    if (state.ctx) state.ctx.setSinkId("").catch(() => {});
    showError("That output could not be used, so the sound stays on the system default. " + e.message);
  }

  async function listOutputs() {
    let devices = [];
    try {
      devices = await navigator.mediaDevices.enumerateDevices();
    } catch (e) {
      devices = [];
    }
    state.outputs = Out.choices(devices);
    if (!Out.stillThere(state.outputs, state.sinkId)) {
      state.sinkId = "";
      applySink().catch(sinkFailed);
      say("That output is gone. The sound is back on the system default.");
    }
    fillOptions($("output"), state.outputs.map((c) => [c.id, c.label]), state.sinkId);
    const note = $("output-note");
    note.hidden = Out.hasNames(devices);
    note.textContent = note.hidden ? "" : "The browser hides output names until a microphone is allowed for this site, so they are numbered.";
  }

  async function setupOutput() {
    const supported = Out.supported(window.AudioContext && window.AudioContext.prototype, navigator.mediaDevices);
    if (!supported) {
      $("output-note").hidden = false;
      $("output-note").textContent = "This browser plays through the system output. Choose it in the device's sound settings.";
      return;
    }
    $("output-row").hidden = false;
    await listOutputs();
    $("output").addEventListener("change", async () => {
      state.sinkId = $("output").value;
      showError("");
      try {
        await applySink();
        say(state.ctx ? "Sound moved." : "Sound will start there.");
      } catch (e) {
        sinkFailed(e);
      }
    });
    navigator.mediaDevices.addEventListener("devicechange", listOutputs);
  }

  // -------------------------------------------------------------------- start

  async function init() {
    buildMix();
    try {
      const [progressions, styles, qualities, profile] = await Promise.all([
        getJson(host.dataset.apiProgressions),
        getJson(host.dataset.apiStyles),
        getJson(host.dataset.apiQualities),
        getJson(host.dataset.apiPlayer),
      ]);
      state.progressions = progressions;
      state.styles = styles;
      state.qualities = qualities;
      state.profile = profile;
    } catch (e) {
      say("The library could not be loaded.");
      showError(e.message);
      return;
    }
    if (!state.progressions.length) {
      say("The library is empty. Run seed_improv_library.");
      return;
    }
    fillProgressions();
    const asked = new URLSearchParams(window.location.search).get("p");
    chooseProgression(asked);
    const exercise = new URLSearchParams(window.location.search).get("exercise");
    if (exercise) await openExercise(exercise);
    say("Ready. Press Play, or Space.");
    state.keys = Keys.draw($("keys"), FIRST_KEY, LAST_KEY);
    setupOutput();
    startMidi();
    window.addEventListener("pagehide", () => {
      if (state.playing) state.clock.bandStopped(clockNow());
      closeSession();
    });
    setInterval(reportSession, Pr.REPORT_EVERY_MS);
    showPractice();

    $("progression").addEventListener("change", () => chooseProgression($("progression").value));
    $("style").addEventListener("change", chooseStyle);
    for (const id of ["key", "swing", "countin", "first", "last", "metronome"]) $(id).addEventListener("change", settingChanged);
    $("bpm").addEventListener("change", tempoChanged);
    $("play-toggle").addEventListener("click", toggle);
    document.addEventListener("keydown", (e) => {
      if (e.code !== "Space" || e.repeat) return;
      const tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || tag === "BUTTON") return;
      e.preventDefault();
      toggle();
    });
  }

  if (!P || !Band || !Sched || !Synth || !View || !Out || !M || !S || !Rec || !Timing || !J || !Keys) say("The page's scripts did not load.");
  else init();
})();
