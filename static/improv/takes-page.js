// improv: the Takes screen. Browser glue only: list the takes, keep or delete one, and replay
// one over the same band through the demo output. The rules live in takes.js, play.js,
// band.js and scheduler.js, which are tested under Node. Only text is ever put on the page.
(function () {
  "use strict";
  const T = window.ImprovTakes;
  const P = window.ImprovPlay;
  const Sched = window.ImprovScheduler;
  const Synth = window.ImprovSynth;
  const View = window.ImprovChartView;
  const M = window.ImprovMidi;
  const S = window.ImprovSetup;
  const Timing = window.ImprovTiming;
  const $ = (id) => document.getElementById(id);
  const host = $("takes");
  const DISARM_MS = 5000;

  const state = {
    takes: [],
    titles: {},
    styles: [],
    qualities: [],
    profile: null,
    ctx: null,
    synth: null,
    scheduler: null,
    midi: null,
    output: null,
    replay: null,
    cells: [],
    frame: 0,
    armed: null,
    armTimer: 0,
  };

  const say = (text) => ($("takes-status").textContent = text);

  function showError(text) {
    $("replay-error").textContent = text;
    $("replay-error").hidden = !text;
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

  async function send(method, url, body) {
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": host.dataset.csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data ? Object.values(data).flat().join(" ") : `${url} answered ${response.status}`);
    return data;
  }

  // ------------------------------------------------------------------ the list

  function shown() {
    const kept = $("f-kept").checked;
    return T.order(state.takes).filter((t) => !kept || t.is_kept);
  }

  function row(take) {
    const d = T.describe(take, { titles: state.titles });
    const li = make("li", "im-take" + (take.is_kept ? " im-take-kept" : ""));
    li.dataset.id = String(take.id);
    const head = make("div", "im-take-head");
    head.appendChild(make("span", "im-take-title", d.title));
    head.appendChild(make("span", "im-take-when", d.when));
    li.appendChild(head);
    li.appendChild(make("p", "im-take-summary", `${d.summary}. ${d.notes} ${d.notes === 1 ? "note" : "notes"}: ${d.verdict}.`));
    const actions = make("div", "im-card-actions");
    const replay = make("button", "im-btn", "Replay");
    replay.type = "button";
    replay.addEventListener("click", () => startReplay(take));
    const keep = make("button", "im-btn im-btn-quiet", take.is_kept ? "Kept" : "Keep");
    keep.type = "button";
    keep.dataset.action = "keep";
    keep.addEventListener("click", () => toggleKept(take));
    const remove = make("button", "im-btn im-btn-quiet im-btn-danger", "Delete");
    remove.type = "button";
    remove.dataset.action = "delete";
    remove.addEventListener("click", () => removeTake(take, remove));
    remove.addEventListener("blur", disarm);
    if (take.progression && state.titles[take.progression]) {
      const again = make("a", "im-btn im-btn-quiet im-btn-link", "Play it again");
      again.href = host.dataset.playUrl + "?p=" + encodeURIComponent(state.slugs[take.progression]);
      actions.appendChild(again);
    }
    if (T.cleared(take)) {
      replay.disabled = true;
      if (!take.is_kept) keep.disabled = true;
      li.dataset.cleared = "yes";
    }
    actions.append(replay, keep, remove);
    li.appendChild(actions);
    const note = T.clearedNote(take);
    if (note) li.appendChild(make("p", "im-note", note));
    return li;
  }

  function draw() {
    const list = $("takes-list");
    list.textContent = "";
    const takes = shown();
    for (const take of takes) list.appendChild(row(take));
    $("takes-empty").hidden = takes.length > 0;
    $("takes-count").textContent = `${takes.length} ${takes.length === 1 ? "take" : "takes"}.`;
  }

  async function toggleKept(take) {
    try {
      const saved = await send("PATCH", `${host.dataset.apiTakes}${take.id}/`, { is_kept: !take.is_kept });
      Object.assign(take, saved);
      draw();
      say(take.is_kept ? "Kept." : "No longer kept.");
    } catch (e) {
      say("That was not saved. " + e.message);
    }
  }

  function disarm() {
    if (state.armed) state.armed.textContent = "Delete";
    state.armed = null;
    window.clearTimeout(state.armTimer);
  }

  async function removeTake(take, button) {
    if (state.armed !== button) {
      disarm();
      state.armed = button;
      button.textContent = "Click again to delete";
      state.armTimer = window.setTimeout(disarm, DISARM_MS);
      return;
    }
    disarm();
    try {
      await send("DELETE", `${host.dataset.apiTakes}${take.id}/`);
      state.takes = state.takes.filter((t) => t.id !== take.id);
      draw();
      say("Deleted.");
    } catch (e) {
      say("That was not deleted. " + e.message);
    }
  }

  // ---------------------------------------------------------------- the replay

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

  function styleFor(take) {
    const named = state.styles.find((s) => s.id === take.style);
    if (named && named.time_signature === take.time_signature) return named;
    return P.pickStyle(T.replayProgression(take), state.styles);
  }

  // The piano's own output, when the profile asks for it and the browser has it.
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

  async function startReplay(take) {
    stopReplay();
    showError("");
    const style = styleFor(take);
    if (!style) {
      showError("No band fits this take's bar length.");
      return;
    }
    const built = P.buildPlan({ progression: T.replayProgression(take, state.titles[take.progression]), style, qualities: state.qualities, settings: T.replaySettings(take) });
    if (!built.ok) {
      showError(built.error);
      return;
    }
    ensureAudio();
    if (state.ctx.state !== "running") await state.ctx.resume();
    const output = await outputFor();
    const spans = T.noteSpans(take.events);
    const bars = T.replayBars(take, spans);
    const beatSeconds = 60 / take.tempo;
    const at = state.ctx.currentTime + 0.3;
    const downbeat = at + built.countInBars * built.plan.beatsPerBar * beatSeconds;
    state.scheduler.start(built.plan, { bpm: take.tempo, loop: true, loopFrom: built.loopFrom, at });
    state.replay = { take, built, output, endsAt: downbeat + bars * built.plan.beatsPerBar * beatSeconds, notes: T.scheduleAt(spans, downbeat), sent: false };

    $("replay-panel").hidden = false;
    $("replay-title").textContent = `Replay: ${T.describe(take, { titles: state.titles }).title}, ${take.key}, ${take.tempo} bpm`;
    $("replay-status").textContent = `One bar of count-in, then your ${spans.length} ${spans.length === 1 ? "note" : "notes"}.`;
    $("replay-output").textContent = output ? `Your notes go to ${output.name} over MIDI.` : "Your notes sound as a plain tone from the laptop.";
    state.cells = View.draw($("replay-chart"), P.layoutBars(built.chart, built.from, built.to));
    if (!output) {
      for (const n of state.replay.notes) state.synth.play({ voice: "demo", midi: n.note, velocity: n.velocity }, n.when, n.seconds);
      state.replay.sent = true;
    }
    if (!state.frame) state.frame = requestAnimationFrame(frame);
  }

  // MIDI out needs the anchor between the two clocks, which exists only once sound is coming
  // out; the count-in bar is time enough to get it and send every note with its timestamp.
  function sendToPiano() {
    const r = state.replay;
    if (!r || r.sent || !r.output) return;
    let anchor;
    try {
      anchor = Timing.makeAnchor(state.ctx.getOutputTimestamp());
    } catch (e) {
      return;
    }
    for (const n of r.notes) {
      r.output.send(M.noteOnBytes(n.note, n.velocity), Timing.heardAt(anchor, n.when));
      r.output.send(M.noteOffBytes(n.note), Timing.heardAt(anchor, n.when + n.seconds));
    }
    r.sent = true;
  }

  function frame() {
    state.frame = 0;
    const r = state.replay;
    if (!r) return;
    sendToPiano();
    const now = state.ctx.currentTime;
    if (now >= r.endsAt) {
      stopReplay();
      $("replay-status").textContent = "Done.";
      return;
    }
    const lit = P.litFor(r.built, state.scheduler.barAt(now));
    for (const c of state.cells) if (c) c.el.classList.remove("im-bar-lit");
    if (lit && !lit.countIn && state.cells[lit.bar]) {
      const c = state.cells[lit.bar];
      c.el.classList.add("im-bar-lit");
      c.beat.style.width = Math.min(100, (lit.beat / r.built.plan.beatsPerBar) * 100) + "%";
    }
    state.frame = requestAnimationFrame(frame);
  }

  function stopReplay() {
    if (state.scheduler) state.scheduler.stop();
    if (state.frame) cancelAnimationFrame(state.frame);
    state.frame = 0;
    if (state.replay && state.replay.output) {
      for (const n of state.replay.notes) state.replay.output.send(M.noteOffBytes(n.note));
    }
    state.replay = null;
    for (const c of state.cells) if (c) c.el.classList.remove("im-bar-lit");
  }

  // --------------------------------------------------------------------- start

  async function init() {
    try {
      const [takes, progressions, styles, qualities, profile] = await Promise.all([
        getJson(host.dataset.apiTakes),
        getJson(host.dataset.apiProgressions),
        getJson(host.dataset.apiStyles),
        getJson(host.dataset.apiQualities),
        getJson(host.dataset.apiPlayer),
      ]);
      state.takes = takes;
      state.styles = styles;
      state.qualities = qualities;
      state.profile = profile;
      state.titles = {};
      state.slugs = {};
      for (const p of progressions) {
        state.titles[p.id] = p.title;
        state.slugs[p.id] = p.slug;
      }
    } catch (e) {
      say("Your takes could not be loaded. " + e.message);
      return;
    }
    draw();
    say(state.takes.length ? "Replay one, keep it, or let it go." : "Nothing recorded yet.");
    $("f-kept").addEventListener("change", draw);
    $("replay-stop").addEventListener("click", () => {
      stopReplay();
      $("replay-status").textContent = "Stopped.";
    });
  }

  if (!T || !P || !Sched || !Synth || !View || !M || !S || !Timing) say("The page's scripts did not load.");
  else init();
})();
