// improv: the band's voices, synthesized with Web Audio. No samples, no network, no
// audio files. The AudioContext is handed in (the page makes it), so this file never
// touches the browser itself and a test can hand it a recording stand-in.
//
// The click is the metronome and the count-in: a short high tick, higher on the beat.
//
// It does not have to sound like a record. It has to be clear, steady and not tiring
// over twenty minutes: soft drums, a rounded bass, an electric-piano-like comp.
//
//   const synth = ImprovSynth.createSynth(ctx);        // connects to ctx.destination
//   synth.play(event, when, seconds);                  // an event from ImprovBand
//   synth.setLevel("comp", 0.5); synth.setMuted("bass", true);
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovSynth = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const GROUPS = ["drums", "bass", "comp", "click", "demo"];
  const DEFAULT_LEVELS = { drums: 0.8, bass: 0.9, comp: 0.7, click: 0.8, demo: 0.9 };

  function midiToHz(midi) {
    return 440 * Math.pow(2, (midi - 69) / 12);
  }

  function createSynth(ctx, destination) {
    const master = ctx.createGain();
    master.gain.value = 0.8;
    // A gentle limiter: a full chord, the bass and the ride on the same beat must not clip.
    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -10;
    limiter.knee.value = 12;
    limiter.ratio.value = 6;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.2;
    master.connect(limiter);
    limiter.connect(destination || ctx.destination);

    const groups = {};
    const muted = {};
    const levels = {};
    for (const name of GROUPS) {
      groups[name] = ctx.createGain();
      levels[name] = DEFAULT_LEVELS[name];
      muted[name] = false;
      groups[name].gain.value = levels[name];
      groups[name].connect(master);
    }

    // One second of white noise, made once and looped by every noisy drum.
    const noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const samples = noise.getChannelData(0);
    let seed = 22222;
    for (let i = 0; i < samples.length; i++) {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      samples[i] = (seed / 4294967296) * 2 - 1;
    }

    const envelope = (param, when, peak, attack, decay) => {
      param.setValueAtTime(0.0001, when);
      param.linearRampToValueAtTime(peak, when + attack);
      param.exponentialRampToValueAtTime(0.0001, when + attack + decay);
    };

    function burst(out, when, { type, freq, q, peak, attack = 0.002, decay }) {
      const source = ctx.createBufferSource();
      source.buffer = noise;
      source.loop = true;
      const filter = ctx.createBiquadFilter();
      filter.type = type;
      filter.frequency.value = freq;
      if (q) filter.Q.value = q;
      const gain = ctx.createGain();
      envelope(gain.gain, when, peak, attack, decay);
      source.connect(filter);
      filter.connect(gain);
      gain.connect(out);
      source.start(when);
      source.stop(when + attack + decay + 0.05);
    }

    function tone(out, when, { type = "sine", from, to, peak, attack = 0.002, decay }) {
      const osc = ctx.createOscillator();
      osc.type = type;
      osc.frequency.setValueAtTime(from, when);
      if (to !== undefined) osc.frequency.exponentialRampToValueAtTime(to, when + decay * 0.6);
      const gain = ctx.createGain();
      envelope(gain.gain, when, peak, attack, decay);
      osc.connect(gain);
      gain.connect(out);
      osc.start(when);
      osc.stop(when + attack + decay + 0.05);
    }

    const DRUMS = {
      kick: (out, when, v) => tone(out, when, { from: 130, to: 45, peak: 0.95 * v, decay: 0.28 }),
      snare: (out, when, v) => {
        burst(out, when, { type: "bandpass", freq: 2200, q: 0.8, peak: 0.55 * v, decay: 0.16 });
        tone(out, when, { type: "triangle", from: 190, to: 150, peak: 0.35 * v, decay: 0.1 });
      },
      rim: (out, when, v) => {
        tone(out, when, { type: "square", from: 1750, peak: 0.12 * v, decay: 0.03 });
        burst(out, when, { type: "highpass", freq: 3000, peak: 0.2 * v, decay: 0.03 });
      },
      hat: (out, when, v) => burst(out, when, { type: "highpass", freq: 7500, peak: 0.28 * v, decay: 0.05 }),
      openhat: (out, when, v) => burst(out, when, { type: "highpass", freq: 7000, peak: 0.26 * v, attack: 0.004, decay: 0.28 }),
      ride: (out, when, v) => {
        burst(out, when, { type: "bandpass", freq: 8200, q: 1.2, peak: 0.3 * v, decay: 0.45 });
        tone(out, when, { type: "triangle", from: 3400, peak: 0.07 * v, decay: 0.3 });
      },
      shaker: (out, when, v) => burst(out, when, { type: "bandpass", freq: 5200, q: 0.9, peak: 0.22 * v, attack: 0.012, decay: 0.06 }),
      clave: (out, when, v) => tone(out, when, { from: 2500, peak: 0.4 * v, decay: 0.045 }),
    };

    function bass(out, when, midi, length, v) {
      const hold = Math.max(0.08, length);
      const osc = ctx.createOscillator();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(midiToHz(midi), when);
      const sub = ctx.createOscillator();
      sub.type = "sine";
      sub.frequency.setValueAtTime(midiToHz(midi), when);
      const filter = ctx.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(900, when);
      filter.frequency.exponentialRampToValueAtTime(260, when + 0.25);
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.linearRampToValueAtTime(0.5 * v, when + 0.01);
      gain.gain.setValueAtTime(0.5 * v, when + hold * 0.7);
      gain.gain.exponentialRampToValueAtTime(0.0001, when + hold + 0.06);
      osc.connect(filter);
      sub.connect(filter);
      filter.connect(gain);
      gain.connect(out);
      osc.start(when);
      sub.start(when);
      osc.stop(when + hold + 0.1);
      sub.stop(when + hold + 0.1);
    }

    function comp(out, when, midi, length, v) {
      const hold = Math.max(0.1, length);
      const hz = midiToHz(midi);
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.linearRampToValueAtTime(0.16 * v, when + 0.006);
      gain.gain.exponentialRampToValueAtTime(0.09 * v, when + Math.min(0.4, hold * 0.6));
      gain.gain.setValueAtTime(0.09 * v, when + hold);
      gain.gain.exponentialRampToValueAtTime(0.0001, when + hold + 0.12);
      const body = ctx.createOscillator();
      body.type = "sine";
      body.frequency.setValueAtTime(hz, when);
      const tineGain = ctx.createGain();
      tineGain.gain.setValueAtTime(0.0001, when);
      tineGain.gain.linearRampToValueAtTime(0.35, when + 0.004);
      tineGain.gain.exponentialRampToValueAtTime(0.0001, when + 0.25);
      const tine = ctx.createOscillator();
      tine.type = "sine";
      tine.frequency.setValueAtTime(hz * 4, when);
      const filter = ctx.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(3200, when);
      body.connect(filter);
      tine.connect(tineGain);
      tineGain.connect(filter);
      filter.connect(gain);
      gain.connect(out);
      body.start(when);
      tine.start(when);
      body.stop(when + hold + 0.2);
      tine.stop(when + hold + 0.2);
    }

    // The demo voice: a plain tone for a replayed take or a lesson phrase when the piano's
    // own MIDI out is not there. Deliberately simple, so it is never mistaken for the band.
    function demo(out, when, midi, length, v) {
      const osc = ctx.createOscillator();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(midiToHz(midi), when);
      const gain = ctx.createGain();
      const hold = Math.max(0.05, length);
      gain.gain.setValueAtTime(0, when);
      gain.gain.linearRampToValueAtTime(0.5 * v, when + 0.01);
      gain.gain.setTargetAtTime(0.3 * v, when + 0.01, 0.15);
      gain.gain.setTargetAtTime(0, when + hold, 0.05);
      osc.connect(gain);
      gain.connect(out);
      osc.start(when);
      osc.stop(when + hold + 0.3);
    }

    function applyGain(name) {
      groups[name].gain.value = muted[name] ? 0 : levels[name];
    }

    return {
      // `seconds` is the length of the note on the audio clock. A start time in the past
      // is moved to now, so a late bar is heard late rather than not at all.
      play(event, when, seconds) {
        const at = Math.max(when, ctx.currentTime);
        const out = groups[event.voice];
        if (!out) return;
        const v = Math.min(1, Math.max(0.01, Number(event.velocity) || 0.01));
        if (event.voice === "drums") {
          const voice = DRUMS[event.inst];
          if (voice) voice(out, at, v);
        } else if (event.voice === "click") {
          tone(out, at, { from: event.accent ? 1568 : 1046, peak: 0.5 * v, decay: 0.045 });
        } else if (event.voice === "bass") bass(out, at, event.midi, seconds, v);
        else if (event.voice === "comp") comp(out, at, event.midi, seconds, v);
        else if (event.voice === "demo") demo(out, at, event.midi, seconds, v);
      },

      setLevel(name, level) {
        if (!(name in groups)) return;
        levels[name] = Math.min(1, Math.max(0, Number(level)));
        applyGain(name);
      },

      setMuted(name, value) {
        if (!(name in groups)) return;
        muted[name] = Boolean(value);
        applyGain(name);
      },

      get groups() {
        return GROUPS.slice();
      },
    };
  }

  return { createSynth, midiToHz, GROUPS };
});
