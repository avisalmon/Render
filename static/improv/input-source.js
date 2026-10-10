// improv: where the notes come from. The piano over MIDI is the default and stays the real thing; this file
// adds two others a page can be switched to: touch keys on the screen (so a phone is enough to jam), and the
// microphone (the piano heard through the air, read by pitch.js). Each one hands the page the same thing a MIDI
// port does, an event with .data bytes and .timeStamp, so the page's own onMidi never knows the difference.
//
// The choice is kept on the device (localStorage), not in the account: a phone and a piano laptop differ.
(function () {
  "use strict";
  const Midi = window.ImprovMidi;
  const Pitch = window.ImprovPitch;
  const Synth = window.ImprovSynth;
  const Keys = window.ImprovKeyboardView;

  const STORE = "improv.input.mode";
  const MODES = [
    ["midi", "Piano (MIDI)"],
    ["touch", "Touch keys"],
    ["mic", "Microphone"],
  ];
  // What the air and the browser add between a key being struck and the samples reaching the page.
  const MIC_LAG_MS = 30;
  const TOP_NOTE = 105; // the three control keys start at 106 and must never be played from here
  const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const nameOf = (note) => NAMES[note % 12] + (Math.floor(note / 12) - 1);

  function saved() {
    try {
      const value = window.localStorage.getItem(STORE);
      return MODES.some((m) => m[0] === value) ? value : "midi";
    } catch (e) {
      return "midi";
    }
  }

  function remember(mode) {
    try {
      window.localStorage.setItem(STORE, mode);
    } catch (e) {
      /* private window: the choice lasts until the page closes */
    }
  }

  // options: { status, deliver(event), midiStart(), midiStop() }
  function attach(options) {
    const status = options.status;
    let mode = "midi";
    let generation = 0;
    let stopCurrent = () => {};

    const say = (text) => {
      status.textContent = text;
    };
    const deliver = (bytes, at) => options.deliver({ data: bytes, timeStamp: at === undefined ? performance.now() : at });

    // ------------------------------------------------------------------ the choice

    const select = document.createElement("select");
    select.id = "im-input-mode";
    select.className = "im-select im-input-mode";
    select.setAttribute("aria-label", "Where the notes come from");
    for (const [value, text] of MODES) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    }
    status.parentNode.insertBefore(select, status);
    select.addEventListener("change", () => {
      remember(select.value);
      setMode(select.value);
    });

    function setMode(next) {
      generation += 1;
      stopCurrent();
      stopCurrent = () => {};
      mode = next;
      select.value = next;
      document.documentElement.dataset.input = next;
      if (next === "midi") {
        options.midiStart();
        return;
      }
      options.midiStop();
      stopCurrent = next === "touch" ? startTouch() : startMic(generation);
    }

    // ------------------------------------------------------------------ touch keys

    let dock = null;
    let audio = null; // { ctx, synth }

    function ensureAudio() {
      if (!audio) {
        const Context = window.AudioContext || window.webkitAudioContext;
        if (!Context || !Synth) return null;
        const ctx = new Context();
        audio = { ctx, synth: Synth.createSynth(ctx) };
      }
      if (audio.ctx.state === "suspended") audio.ctx.resume().catch(() => {});
      return audio;
    }

    function octavesFor(width) {
      return width < 600 ? 2 : width < 1000 ? 3 : 4;
    }

    function buildDock() {
      const box = document.createElement("div");
      box.id = "im-dock";
      box.className = "im-dock";
      box.setAttribute("role", "group");
      box.setAttribute("aria-label", "Touch keyboard");
      const bar = document.createElement("div");
      bar.className = "im-dock-bar";
      const lower = document.createElement("button");
      lower.type = "button";
      lower.id = "im-dock-lower";
      lower.className = "im-btn im-btn-quiet";
      lower.textContent = "Lower";
      const higher = document.createElement("button");
      higher.type = "button";
      higher.id = "im-dock-higher";
      higher.className = "im-btn im-btn-quiet";
      higher.textContent = "Higher";
      const range = document.createElement("span");
      range.id = "im-dock-range";
      range.className = "im-note";
      bar.append(lower, range, higher);
      const keys = document.createElement("div");
      keys.id = "im-dock-keys";
      keys.className = "im-keyboard im-dock-keys";
      keys.setAttribute("aria-label", "Touch keys");
      box.append(bar, keys);
      document.body.appendChild(box);
      return { box, lower, higher, range, keys };
    }

    function startTouch() {
      if (!dock) dock = buildDock();
      const parts = dock;
      parts.box.hidden = false;
      let octaves = octavesFor(window.innerWidth);
      let base = 48;
      let drawn = new Map();
      const sounding = new Map(); // pointerId -> { note, release }
      const pressed = new Set();

      const baseMax = () => Math.max(24, Math.floor((TOP_NOTE - 12 * octaves) / 12) * 12);

      function stopPointer(id) {
        const held = sounding.get(id);
        if (!held) return;
        sounding.delete(id);
        deliver(Midi.noteOffBytes(held.note));
        if (held.release) held.release();
        const key = drawn.get(held.note);
        if (key && ![...sounding.values()].some((s) => s.note === held.note)) key.classList.remove("im-key-on");
      }

      function releaseAll() {
        for (const id of [...sounding.keys()]) stopPointer(id);
        pressed.clear();
      }

      function draw() {
        releaseAll();
        octaves = octavesFor(window.innerWidth);
        base = clamp(base, 24, baseMax());
        drawn = Keys.draw(parts.keys, base, base + 12 * octaves);
        parts.range.textContent = `${nameOf(base)} to ${nameOf(base + 12 * octaves)}`;
        parts.lower.disabled = base <= 24;
        parts.higher.disabled = base >= baseMax();
      }

      function hit(x, y) {
        const el = document.elementFromPoint(x, y);
        const key = el && el.closest ? el.closest("#im-dock-keys .im-key") : null;
        return key ? { note: Number(key.dataset.note), key } : null;
      }

      // Struck low on a key is loud, high on it is soft, the way a finger meets a real key.
      const velocityAt = (key, y) => {
        const rect = key.getBoundingClientRect();
        return Math.round(35 + 85 * clamp((y - rect.top) / Math.max(rect.height, 1), 0, 1));
      };

      function begin(id, found, y) {
        const velocity = velocityAt(found.key, y);
        const sound = ensureAudio();
        const release = sound ? sound.synth.hold(found.note, velocity / 127) : null;
        sounding.set(id, { note: found.note, release });
        found.key.classList.add("im-key-on");
        deliver(Midi.noteOnBytes(found.note, velocity));
      }

      const onDown = (e) => {
        const found = hit(e.clientX, e.clientY);
        if (!found) return;
        e.preventDefault();
        pressed.add(e.pointerId);
        if (parts.keys.setPointerCapture) {
          try {
            parts.keys.setPointerCapture(e.pointerId);
          } catch (err) {
            /* a synthetic pointer cannot be captured */
          }
        }
        begin(e.pointerId, found, e.clientY);
      };
      const onMove = (e) => {
        if (!pressed.has(e.pointerId)) return;
        const found = hit(e.clientX, e.clientY);
        const now = sounding.get(e.pointerId);
        if (now && found && found.note === now.note) return;
        stopPointer(e.pointerId);
        if (found) begin(e.pointerId, found, e.clientY);
      };
      const onUp = (e) => {
        pressed.delete(e.pointerId);
        stopPointer(e.pointerId);
      };
      const onShift = (by) => () => {
        base = clamp(base + by * 12, 24, baseMax());
        draw();
      };
      const onLower = onShift(-1);
      const onHigher = onShift(1);
      const onResize = () => {
        if (octavesFor(window.innerWidth) !== octaves) draw();
      };

      parts.keys.addEventListener("pointerdown", onDown);
      parts.keys.addEventListener("pointermove", onMove);
      parts.keys.addEventListener("pointerup", onUp);
      parts.keys.addEventListener("pointercancel", onUp);
      parts.lower.addEventListener("click", onLower);
      parts.higher.addEventListener("click", onHigher);
      window.addEventListener("resize", onResize);
      draw();
      say("Touch keys. Play on the keyboard at the bottom; Lower and Higher move it up and down the piano.");

      return () => {
        releaseAll();
        parts.keys.removeEventListener("pointerdown", onDown);
        parts.keys.removeEventListener("pointermove", onMove);
        parts.keys.removeEventListener("pointerup", onUp);
        parts.keys.removeEventListener("pointercancel", onUp);
        parts.lower.removeEventListener("click", onLower);
        parts.higher.removeEventListener("click", onHigher);
        window.removeEventListener("resize", onResize);
        parts.box.hidden = true;
      };
    }

    // ------------------------------------------------------------------ microphone

    function startMic(mine) {
      let cleanup = () => {};
      const alive = () => generation === mine;
      const media = navigator.mediaDevices;
      if (!media || !media.getUserMedia || !Pitch) {
        say("This browser cannot use the microphone. Use Chrome, Edge or Safari over https.");
        return cleanup;
      }
      say("Asking for the microphone.");
      media
        .getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } })
        .then((stream) => {
          if (!alive()) {
            stream.getTracks().forEach((t) => t.stop());
            return;
          }
          const Context = window.AudioContext || window.webkitAudioContext;
          const ctx = new Context();
          ctx.resume().catch(() => {});
          const source = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = Pitch.SIZE;
          analyser.smoothingTimeConstant = 0;
          source.connect(analyser); // listened to, never played back
          const tracker = Pitch.createTracker(ctx.sampleRate);
          const buffer = new Float32Array(analyser.fftSize);
          const hopS = tracker.hopMs / 1000;
          let lastAt = -1;

          const poll = setInterval(() => {
            if (ctx.currentTime - lastAt < hopS * 0.9) return;
            lastAt = ctx.currentTime;
            analyser.getFloatTimeDomainData(buffer);
            const endMs = performance.now() - MIC_LAG_MS - (ctx.baseLatency || 0) * 1000;
            for (const e of tracker.push(buffer, endMs)) {
              deliver(e.type === "on" ? Midi.noteOnBytes(e.note, e.velocity) : Midi.noteOffBytes(e.note), e.t);
            }
          }, 10);

          const resume = () => ctx.resume().catch(() => {});
          document.addEventListener("pointerdown", resume, { once: true });
          const words = setInterval(() => {
            if (ctx.state === "suspended") {
              say("Tap the page once to start listening.");
              return;
            }
            const heard = tracker.held().sort((a, b) => a - b).map(nameOf);
            say(heard.length ? `Listening. Heard ${heard.join(" ")}.` : "Listening to the microphone. Nothing heard yet. Use headphones if the band is playing.");
          }, 250);

          cleanup = () => {
            clearInterval(poll);
            clearInterval(words);
            document.removeEventListener("pointerdown", resume);
            for (const note of tracker.held()) deliver(Midi.noteOffBytes(note));
            stream.getTracks().forEach((t) => t.stop());
            ctx.close().catch(() => {});
          };
          if (!alive()) cleanup();
        })
        .catch(() => {
          if (alive()) say("The microphone was refused. Allow it in the address bar, or pick another input.");
        });
      return () => cleanup();
    }

    // ------------------------------------------------------------------ the page's way in

    return {
      start: () => setMode(saved()),
      mode: () => mode,
    };
  }

  window.ImprovInput = { attach, MODES, nameOf };
})();
