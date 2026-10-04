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
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    const bpm = P.clampTempo(state.style, $("bpm").value);
    $("bpm").value = bpm;
    state.scheduler.start(state.built.plan, { bpm, loop: true, loopFrom: state.built.loopFrom });
    state.playing = true;
    lockSettings(true);
    $("play-toggle").textContent = "Stop";
    say(state.built.metronome ? "Metronome." : `${state.style.name}, ${bpm} bpm, ${state.built.key}.`);
    if (!state.frame) state.frame = requestAnimationFrame(frame);
  }

  function stop() {
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
      const [progressions, styles, qualities] = await Promise.all([
        getJson(host.dataset.apiProgressions),
        getJson(host.dataset.apiStyles),
        getJson(host.dataset.apiQualities),
      ]);
      state.progressions = progressions;
      state.styles = styles;
      state.qualities = qualities;
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
    say("Ready. Press Play, or Space.");
    setupOutput();

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

  if (!P || !Band || !Sched || !Synth || !View || !Out) say("The page's scripts did not load.");
  else init();
})();
