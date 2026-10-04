// improv: the timing spike page (SPR-I.1.2). Browser glue only. The maths lives in
// timing.js and midi.js, which are tested under Node.
(function () {
  "use strict";
  const M = window.ImprovMidi;
  const T = window.ImprovTiming;
  const $ = (id) => document.getElementById(id);

  const LOOKAHEAD_S = 0.12;
  const TICK_MS = 25;
  const KEEP_CLICKS = 64;
  const MAX_ROWS = 30;
  const LAST_N = 16;
  const FIRST_KEY = 36; // C2
  const LAST_KEY = 96; // C7
  const BLACK = new Set([1, 3, 6, 8, 10]);

  const state = {
    ctx: null,
    anchor: null,
    clicks: [], // audio-clock times of clicks already scheduled
    nextBeat: 0,
    gap: 0.5,
    beat: 0,
    timer: null,
    midi: null,
    input: null,
    inputCount: 0,
    rows: [], // { n, source, note, velocity, offset }
    counter: 0,
    keys: new Map(),
  };

  // ------------------------------------------------------------- the keyboard

  function buildKeyboard() {
    const host = $("keyboard");
    const whites = [];
    for (let n = FIRST_KEY; n <= LAST_KEY; n++) if (!BLACK.has(n % 12)) whites.push(n);
    const width = 100 / whites.length;
    let index = 0;
    for (let n = FIRST_KEY; n <= LAST_KEY; n++) {
      const key = document.createElement("div");
      key.dataset.note = String(n);
      key.title = M.noteName(n);
      if (BLACK.has(n % 12)) {
        key.className = "im-key im-key-black";
        key.style.left = index * width - width * 0.3 + "%";
        key.style.width = width * 0.6 + "%";
      } else {
        key.className = "im-key im-key-white";
        key.style.left = index * width + "%";
        key.style.width = width + "%";
        index++;
      }
      host.appendChild(key);
      state.keys.set(n, key);
    }
    host.addEventListener("pointerdown", (e) => {
      const key = e.target.closest("[data-note]");
      if (!key) return;
      key.setPointerCapture(e.pointerId);
      const note = Number(key.dataset.note);
      handle({ type: "on", note, velocity: 90 }, "screen", e.timeStamp);
      blip(note);
    });
    const release = (e) => {
      const key = e.target.closest("[data-note]");
      if (key) handle({ type: "off", note: Number(key.dataset.note) }, "screen", e.timeStamp);
    };
    host.addEventListener("pointerup", release);
    host.addEventListener("pointercancel", release);
  }

  function light(note, on) {
    const key = state.keys.get(note);
    if (key) key.classList.toggle("im-key-on", on);
  }

  // -------------------------------------------------------------------- audio

  function blip(note) {
    if (!state.ctx) return;
    const t = state.ctx.currentTime;
    const osc = state.ctx.createOscillator();
    const gain = state.ctx.createGain();
    osc.type = "triangle";
    osc.frequency.value = 440 * Math.pow(2, (note - 69) / 12);
    gain.gain.setValueAtTime(0.2, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.4);
    osc.connect(gain).connect(state.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.45);
  }

  function clickAt(time, accent) {
    const osc = state.ctx.createOscillator();
    const gain = state.ctx.createGain();
    osc.frequency.value = accent ? 1500 : 1000;
    gain.gain.setValueAtTime(0.0001, time);
    gain.gain.exponentialRampToValueAtTime(0.6, time + 0.002);
    gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.04);
    osc.connect(gain).connect(state.ctx.destination);
    osc.start(time);
    osc.stop(time + 0.05);
  }

  function refreshAnchor() {
    try {
      state.anchor = T.makeAnchor(state.ctx.getOutputTimestamp());
    } catch (e) {
      /* not ready yet; keep the last good anchor */
    }
  }

  function tick() {
    refreshAnchor();
    const bpm = Number($("bpm").value);
    let gap;
    try {
      gap = 60 / bpm;
      state.gap = gap;
      T.beatTimes(0, bpm, 1);
    } catch (e) {
      return;
    }
    while (state.nextBeat < state.ctx.currentTime + LOOKAHEAD_S) {
      clickAt(state.nextBeat, state.beat % 4 === 0);
      state.clicks.push(state.nextBeat);
      if (state.clicks.length > KEEP_CLICKS) state.clicks.shift();
      state.nextBeat += gap;
      state.beat++;
    }
  }

  function toggleClick() {
    const button = $("click-toggle");
    if (state.timer) {
      clearInterval(state.timer);
      state.timer = null;
      button.textContent = "Start click";
      return;
    }
    state.beat = 0;
    state.nextBeat = state.ctx.currentTime + 0.2;
    state.timer = setInterval(tick, TICK_MS);
    button.textContent = "Stop click";
    setTimeout(environment, 600);
  }

  async function startAudio() {
    if (!state.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) {
        $("midi-status").textContent = "This browser has no Web Audio. Use Chrome or Edge.";
        return;
      }
      state.ctx = new Ctx({ latencyHint: "interactive" });
    }
    await state.ctx.resume();
    $("click-toggle").disabled = false;
    refreshAnchor();
    await startMidi();
    environment();
  }

  // --------------------------------------------------------------------- MIDI

  async function startMidi() {
    const status = $("midi-status");
    if (!navigator.requestMIDIAccess) {
      status.textContent = "This browser has no Web MIDI. Use Chrome or Edge. The on-screen keyboard still works.";
      return;
    }
    try {
      state.midi = await navigator.requestMIDIAccess({ sysex: false });
    } catch (e) {
      status.textContent = "MIDI was refused: " + e.name + ". Allow it in the address bar and press Start again.";
      return;
    }
    state.midi.onstatechange = listInputs;
    listInputs();
  }

  function listInputs() {
    const select = $("midi-input");
    const previous = select.value || localStorage.getItem("improv.spike.input") || "";
    const inputs = Array.from(state.midi.inputs.values());
    state.inputCount = inputs.length;
    select.innerHTML = "";
    if (!inputs.length) {
      select.innerHTML = '<option value="">(no MIDI input found)</option>';
      $("midi-status").textContent = "MIDI is allowed, but no input device is connected. Plug the piano in by USB.";
      attach(null);
      environment();
      return;
    }
    for (const input of inputs) {
      const option = document.createElement("option");
      option.value = input.id;
      option.textContent = input.name + (input.state === "connected" ? "" : " (" + input.state + ")");
      select.appendChild(option);
    }
    const stillThere = inputs.find((i) => i.id === previous);
    select.value = stillThere ? stillThere.id : inputs[0].id;
    attach(state.midi.inputs.get(select.value));
    environment();
  }

  function attach(input) {
    if (state.input) state.input.onmidimessage = null;
    state.input = input;
    if (!input) return;
    input.onmidimessage = (e) => {
      const message = M.parse(e.data);
      if (message) handle(message, "midi", e.timeStamp);
    };
    localStorage.setItem("improv.spike.input", input.id);
    $("midi-status").textContent = "Listening to " + input.name + ".";
  }

  // ------------------------------------------------------------- note handling

  function handle(message, source, timestampMs) {
    if (message.type === "pedal") {
      $("pedal").textContent = message.down ? "down" : "up";
      return;
    }
    light(message.note, message.type === "on");
    if (message.type !== "on") return;
    let offset = null;
    if (state.anchor && state.clicks.length && state.timer) {
      const audioClicks = state.clicks.concat(T.upcoming(state.nextBeat, state.gap, 2));
      const heard = audioClicks.map((t) => T.heardAt(state.anchor, t));
      const hit = T.nearestClick(timestampMs, heard);
      offset = hit ? hit.offsetMs : null;
    }
    state.rows.unshift({ n: ++state.counter, source, note: message.note, velocity: message.velocity, offset, at: timestampMs });
    if (state.rows.length > 200) state.rows.pop();
    renderRows();
    renderSummary();
  }

  function renderRows() {
    const body = $("readout");
    body.innerHTML = "";
    for (const row of state.rows.slice(0, MAX_ROWS)) {
      const tr = document.createElement("tr");
      const cells = [
        row.n,
        row.source,
        M.noteName(row.note),
        row.velocity,
        row.offset === null ? "no click running" : (row.offset > 0 ? "+" : "") + row.offset.toFixed(1) + " ms",
      ];
      for (const value of cells) {
        const td = document.createElement("td");
        td.textContent = String(value);
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
  }

  function summaryFor(source) {
    const offsets = state.rows
      .filter((r) => r.source === source && r.offset !== null)
      .slice(0, LAST_N)
      .map((r) => r.offset);
    const s = T.stats(offsets);
    return { s, v: s.n ? T.verdict(s) : null };
  }

  function steadiness(source) {
    const times = state.rows.filter((r) => r.source === source).slice(0, LAST_N).map((r) => r.at).reverse();
    const s = T.stats(T.intervals(times));
    if (!s.n) return "";
    return " Gaps between notes: mean " + s.mean.toFixed(0) + " ms, spread " + (s.sd === null ? "n/a" : s.sd.toFixed(0) + " ms") + ".";
  }

  function describe(label, { s, v }) {
    if (!s.n) return label + ": no notes against the click yet.";
    const sd = s.sd === null ? "n/a" : s.sd.toFixed(1) + " ms";
    return (
      label + ": last " + s.n + " notes, mean " + (s.mean > 0 ? "+" : "") + s.mean.toFixed(1) + " ms, spread " + sd +
      ", range " + s.min.toFixed(0) + " to " + s.max.toFixed(0) + " ms. " + (v.usable ? "Usable. " : "Not usable yet: ") + v.reason + "."
    );
  }

  function renderSummary() {
    $("summary").textContent = describe("Piano", summaryFor("midi")) + steadiness("midi") + "\n" + describe("Screen keyboard", summaryFor("screen"));
    report();
  }

  // -------------------------------------------------------------- environment

  function environment() {
    const c = state.ctx;
    const lines = [
      "Browser: " + navigator.userAgent,
      "Audio: " + (c ? c.state + ", " + c.sampleRate + " Hz, baseLatency " + fixed(c.baseLatency) + " s, outputLatency " + fixed(c.outputLatency) + " s" : "not started"),
      "Output timestamp: " + (state.anchor ? "available" : "not available yet"),
      "Web MIDI: " + (navigator.requestMIDIAccess ? (state.midi ? "allowed, " + state.inputCount + " input(s)" : "supported, not started") : "not supported"),
    ];
    if (state.midi) {
      for (const input of state.midi.inputs.values()) lines.push("  input: " + input.name + " (" + input.manufacturer + ", " + input.state + ")");
    }
    $("environment").textContent = lines.join("\n");
    report();
  }

  function fixed(value) {
    return typeof value === "number" ? value.toFixed(4) : "unknown";
  }

  function report() {
    const piano = state.rows.filter((r) => r.source === "midi" && r.offset !== null).slice(0, LAST_N).map((r) => r.offset.toFixed(1));
    $("report").value =
      "improv timing spike\n" + $("environment").textContent + "\nTempo: " + $("bpm").value + " bpm\n" +
      $("summary").textContent + "\nLast piano offsets (ms, newest first): " + (piano.join(", ") || "none") + "\n";
  }

  async function copyReport() {
    report();
    const text = $("report").value;
    try {
      await navigator.clipboard.writeText(text);
      $("copied").textContent = "Copied.";
    } catch (e) {
      $("report").select();
      $("copied").textContent = "Select and copy the text above.";
    }
  }

  // --------------------------------------------------------------------- init

  buildKeyboard();
  $("start-audio").addEventListener("click", startAudio);
  $("click-toggle").addEventListener("click", toggleClick);
  $("midi-input").addEventListener("change", () => state.midi && attach(state.midi.inputs.get($("midi-input").value)));
  $("copy-result").addEventListener("click", copyReport);
  $("bpm").addEventListener("change", report);
  report();
})();
