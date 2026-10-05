// improv: the Setup screen. Browser glue only: ask for MIDI, list the keyboards, read the
// fields, save them. The rules live in setup.js and midi.js, which are tested under Node.
// Only text is ever put on the page.
(function () {
  "use strict";
  const S = window.ImprovSetup;
  const M = window.ImprovMidi;
  const Rec = window.ImprovRecognize;
  const Cal = window.ImprovCalibrate;
  const Timing = window.ImprovTiming;
  const Synth = window.ImprovSynth;
  const $ = (id) => document.getElementById(id);
  const RUN_SECONDS = 4;
  const host = $("setup");

  const state = {
    profile: null,
    saved: null,
    qualities: [],
    scales: [],
    run: [],
    midi: null,
    choices: null,
    listening: null,
    held: [],
    saving: false,
    ctx: null,
    synth: null,
    cal: null,
    found: null,
  };

  const say = (text) => ($("setup-status").textContent = text);

  function showError(text) {
    $("setup-error").textContent = text;
    $("setup-error").hidden = !text;
  }

  function make(tag, text) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function fillOptions(select, items, selected) {
    select.textContent = "";
    for (const [value, label] of items) {
      const option = make("option", label);
      option.value = String(value);
      select.appendChild(option);
    }
    if (selected !== undefined && selected !== null) select.value = String(selected);
  }

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  // ---------------------------------------------------------------- the fields

  function writeFields(profile) {
    fillOptions($("note-names"), S.NOTE_NAME_CHOICES, profile.note_names);
    fillOptions($("demo-output"), S.DEMO_OUTPUT_CHOICES, profile.demo_output);
    $("daily-goal").value = profile.daily_goal_minutes;
    $("timezone").value = profile.timezone;
    showLatency(profile.latency_offset_ms);
  }

  function showLatency(ms) {
    const number = Number(ms);
    $("latency").textContent = number
      ? `Calibrated: your notes are shifted by ${number} ms before they are judged.`
      : "Not calibrated yet.";
  }

  function readFields() {
    return {
      ...state.profile,
      note_names: $("note-names").value,
      demo_output: $("demo-output").value,
      daily_goal_minutes: $("daily-goal").value,
      timezone: $("timezone").value,
      midi_input_name: state.listening ? state.listening.name : state.profile.midi_input_name,
    };
  }

  function update() {
    const clean = S.cleanProfile(readFields());
    const list = Object.values(clean.problems);
    $("setup-problems").hidden = list.length === 0;
    $("setup-problems").textContent = list.join(" ");
    $("save").disabled = state.saving || !clean.ok || !S.isDirty(readFields(), state.saved);
    return clean;
  }

  async function save() {
    const clean = update();
    if ($("save").disabled || !clean.ok) return;
    state.saving = true;
    $("save").disabled = true;
    say("Saving.");
    try {
      const response = await fetch(host.dataset.apiPlayer, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": host.dataset.csrf },
        body: JSON.stringify(S.toBody(clean.profile)),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data ? Object.values(data).flat().join(" ") : "The server refused it.");
      state.profile = data;
      state.saved = S.cleanProfile(data).profile;
      writeFields(data);
      say("Saved.");
    } catch (e) {
      say("It was not saved. " + e.message);
    }
    state.saving = false;
    update();
  }

  // ------------------------------------------------------------------ the piano

  // What is being held, named. The notes are shown too, so a player can see the app heard
  // exactly what they pressed, and the name is spelled the way they asked for.
  function heard() {
    const spelling = $("note-names").value;
    const read = Rec.recognize(state.held, state.qualities, { spelling });
    const notes = $("heard-notes");
    if (read.kind === "none") {
      $("heard").textContent = "Nothing yet.";
      notes.textContent = "";
      return;
    }
    if (read.kind === "notes") {
      $("heard").textContent = read.guesses.length ? read.guesses.join(" or ") : read.text;
      notes.textContent = read.guesses.length ? read.text : "";
      return;
    }
    $("heard").textContent = read.name + (read.exact ? "" : "?");
    const parts = [read.notes.join(" ")];
    if (!read.exact) parts.push(read.alternatives.length ? "or " + read.alternatives.join(", ") : "a best guess");
    notes.textContent = parts.join("    ");
  }

  // A run of single notes, named. The window is the recognizer's, so the Play screen will
  // show the same thing from the same code when it starts listening too.
  function showScaleFits() {
    const now = performance.now() / 1000;
    state.run = state.run.filter((e) => e.at > now - RUN_SECONDS);
    const played = Rec.recentNotes(state.run, now, RUN_SECONDS);
    const got = Rec.scaleFits(played, state.scales, { spelling: $("note-names").value });
    const line = $("scale-fits");
    if (!played.length) {
      line.textContent = "Play a run of single notes and the scales they fit are named here.";
      return;
    }
    if (!got.ready) {
      line.textContent = `${got.needed} more ${got.needed === 1 ? "note" : "notes"} and the scales they fit are named here.`;
      return;
    }
    line.textContent = got.fits.length ? "Fits " + got.fits.map((f) => f.name).join(", ") : "That run fits no scale in the table.";
  }

  function attach(choice) {
    for (const port of state.midi ? state.midi.inputs.values() : []) port.onmidimessage = null;
    state.listening = choice || null;
    state.held = [];
    state.run = [];
    heard();
    showScaleFits();
    if (!choice) return;
    const port = state.midi.inputs.get(choice.id);
    if (!port) return;
    port.onmidimessage = (event) => {
      const message = M.parse(event.data);
      if (!message) return;
      if (message.type === "on") {
        state.held = [...state.held.filter((n) => n !== message.note), message.note];
        state.run.push({ note: message.note, at: performance.now() / 1000 });
        if (state.cal) {
          state.cal.taps.push(event.timeStamp);
          showCalibrationCount();
        }
      } else if (message.type === "off") {
        state.held = state.held.filter((n) => n !== message.note);
      } else return;
      heard();
      showScaleFits();
    };
    update();
  }

  function listInputs() {
    const before = state.choices;
    state.choices = S.inputChoices(Array.from(state.midi.inputs.values()));
    const news = S.describeChange(S.changes(before, state.choices), state.listening ? state.listening.name : "");

    // A port that is listed but unplugged cannot be played, so there is nothing to offer.
    const remembered = state.listening ? state.listening.name : state.profile.midi_input_name;
    const choice = S.pickInput(state.choices, remembered);
    $("midi-row").hidden = !choice;
    if (choice) {
      fillOptions($("midi-input"), state.choices.map((c) => [c.id, c.label]), choice.id);
    }
    const sentence = choice
      ? `Listening to ${choice.name}.`
      : "No keyboard is connected. Plug the piano in by USB.";
    $("midi-state").textContent = news ? `${sentence} ${news}` : sentence;
    if (!choice || !state.listening || choice.id !== state.listening.id) attach(choice);
    else if (news) update();
  }

  async function startMidi() {
    if (!navigator.requestMIDIAccess) {
      $("midi-state").textContent = "This browser has no Web MIDI, so it cannot read the piano. Use Chrome or Edge.";
      $("midi-help").hidden = false;
      $("midi-help").textContent = "Everything else on this page works, and so does the band.";
      return;
    }
    try {
      state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      $("midi-state").textContent = "MIDI was refused, so the piano cannot be read.";
      $("midi-allow").hidden = false;
      $("midi-help").hidden = false;
      $("midi-help").textContent = "Allow MIDI for this site in the address bar, then press Allow MIDI.";
      return;
    }
    $("midi-allow").hidden = true;
    $("midi-help").hidden = true;
    state.midi.onstatechange = listInputs;
    listInputs();
  }

  // --------------------------------------------------------------- calibration

  // The click leaves on the audio clock; the piano arrives on the performance clock. The
  // anchor is what ties the two together, and it only exists once sound is actually coming
  // out, so the clicks are placed where they are HEARD rather than where they were asked for.
  function anchorWhenReady(onReady) {
    let tries = 0;
    const look = () => {
      tries += 1;
      try {
        onReady(Timing.makeAnchor(state.ctx.getOutputTimestamp()));
        return;
      } catch (e) {
        if (tries > 120) {
          showError("This browser will not say when its sound comes out, so calibration cannot be measured here.");
          stopCalibration();
          return;
        }
      }
      requestAnimationFrame(look);
    };
    look();
  }

  async function startCalibration() {
    if (state.cal) return;
    showError("");
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) {
      showError("This browser has no Web Audio, so there is no click to tap against.");
      return;
    }
    if (!state.ctx) state.ctx = new Ctx();
    await state.ctx.resume();
    if (!state.synth) state.synth = Synth.createSynth(state.ctx);

    const plan = Cal.clickPlan(Cal.DEFAULT_BPM);
    const begin = state.ctx.currentTime + 0.4;
    const audioTimes = Timing.beatTimes(begin, Cal.DEFAULT_BPM, plan.count);
    for (let i = 0; i < audioTimes.length; i++) {
      state.synth.play({ voice: "click", velocity: 1, accent: i % 4 === 0 }, audioTimes[i], 0.05);
    }
    state.cal = { plan, audioTimes, taps: [], anchor: null, endsAt: audioTimes[audioTimes.length - 1] + 0.25 };
    $("calibrate").disabled = true;
    $("cal-save").hidden = true;
    $("cal-result").textContent = "Listen to the first four clicks, then tap with the click.";
    $("cal-warning").hidden = true;
    showCalibrationCount();

    const note = Cal.latencyNote(state.ctx.outputLatency);
    if (note) {
      $("cal-warning").hidden = false;
      $("cal-warning").textContent = note;
    }
    anchorWhenReady((anchor) => {
      if (state.cal) state.cal.anchor = anchor;
    });
    watchCalibration();
  }

  function showCalibrationCount() {
    const wanted = Cal.TAPS_WANTED;
    $("cal-count").textContent = state.cal ? `${Math.min(state.cal.taps.length, wanted)} of ${wanted} taps` : "";
  }

  function watchCalibration() {
    if (!state.cal) return;
    if (state.ctx.currentTime >= state.cal.endsAt) {
      finishCalibration();
      return;
    }
    requestAnimationFrame(watchCalibration);
  }

  function stopCalibration() {
    state.cal = null;
    $("calibrate").disabled = false;
    $("cal-count").textContent = "";
  }

  function finishCalibration() {
    const run = state.cal;
    stopCalibration();
    if (!run || !run.anchor) {
      $("cal-result").textContent = "The click could not be timed. Try again.";
      return;
    }
    // Only the clicks after the count-in are measured against, and only taps from that point on.
    const counted = run.audioTimes.slice(run.plan.countIn).map((t) => Timing.heardAt(run.anchor, t));
    const gapMs = run.plan.gapSeconds * 1000;
    const taps = run.taps.filter((t) => t >= counted[0] - gapMs / 2);
    const found = Cal.result(Cal.collect(taps, counted).offsets);
    state.found = found;
    $("cal-result").textContent = Cal.describe(found);
    $("cal-save").hidden = !found.usable;
  }

  async function saveOffset() {
    if (!state.found || !state.found.usable) return;
    $("cal-save").disabled = true;
    const was = state.profile.latency_offset_ms;
    state.profile.latency_offset_ms = state.found.offsetMs;
    const clean = S.cleanProfile(readFields());
    if (!clean.ok) {
      state.profile.latency_offset_ms = was;
      $("cal-save").disabled = false;
      return;
    }
    await save();
    $("cal-save").disabled = false;
    $("cal-save").hidden = true;
  }

  // --------------------------------------------------------------------- start

  async function init() {
    try {
      const [profile, qualities, scales] = await Promise.all([
        getJson(host.dataset.apiPlayer),
        getJson(host.dataset.apiQualities),
        getJson(host.dataset.apiScales),
      ]);
      state.profile = profile;
      state.qualities = qualities;
      state.scales = scales;
    } catch (e) {
      say("Your setup could not be loaded. " + e.message);
      return;
    }
    state.saved = S.cleanProfile(state.profile).profile;
    writeFields(state.profile);
    say("Choose your keyboard, then Save.");
    update();

    for (const id of ["note-names", "demo-output", "daily-goal", "timezone"]) {
      $(id).addEventListener("input", update);
      $(id).addEventListener("change", update);
    }
    $("note-names").addEventListener("change", () => {
      heard();
      showScaleFits();
    });
    $("save").addEventListener("click", save);
    $("calibrate").addEventListener("click", startCalibration);
    $("cal-save").addEventListener("click", saveOffset);
    $("midi-allow").addEventListener("click", startMidi);
    $("midi-input").addEventListener("change", () => {
      showError("");
      attach((state.choices || []).find((c) => c.id === $("midi-input").value) || null);
      if (state.listening) $("midi-state").textContent = `Listening to ${state.listening.name}.`;
    });
    startMidi();
  }

  if (!S || !M || !Rec || !Cal || !Timing || !Synth) say("The page's scripts did not load.");
  else init();
})();
