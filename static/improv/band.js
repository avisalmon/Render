// improv: the band's score. Pure: no browser, no audio, runs under Node in the tests.
//
// planBand(parsed, style, qualities, options) turns a parsed chart (chart.js) and a
// Style row (the API's shape) into what to play, bar by bar:
//   { ok: true, beatsPerBar, swingRatio, bars: [{ index, source, beats, events }] }  or
//   { ok: false, error: "plain message" }
// Each event is { voice: "drums"|"bass"|"comp", inst?, beat, beats, midi?, velocity },
// `beat` counted in quarter notes from the start of its bar, swing already applied.
//
// Timing is exact. Swing is the only displacement, and it lives in one function
// (swingBeat) that the judging in chapter 5 uses as well, so the band and the score
// agree on where the beat is. Variation comes from velocity, never from random timing.
// Everything is a function of its input: the same chart and style give the same notes.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovBand = factory();
})(typeof self !== "undefined" ? self : this, function () {
  // These three lists are the vocabulary of improv/grooves.py. A test compares them.
  const DRUM_INSTRUMENTS = ["kick", "snare", "rim", "hat", "openhat", "ride", "shaker", "clave"];
  const BASS_RULES = ["walking", "two_feel", "root_fifth", "eighths", "bossa", "boogie"];
  const VOICINGS = ["shell", "triad", "seventh"];
  const STEPS_PER_BEAT = 4;
  const EPS = 1e-9;
  const VOICE_ORDER = { drums: 0, bass: 1, comp: 2 };

  // ---------------------------------------------------------------------- swing

  // Beat positions are in quarter notes. The first half of each beat is stretched or
  // squeezed so the off-beat eighth lands `ratio` of the way through the beat
  // (0.5 is straight, 0.67 is a triplet feel). Sixteenths move in proportion.
  function swingBeat(beat, ratio) {
    const whole = Math.floor(beat + EPS);
    const frac = Math.max(0, beat - whole);
    const warped = frac <= 0.5 ? frac * 2 * ratio : ratio + (frac - 0.5) * 2 * (1 - ratio);
    return whole + warped;
  }

  // ------------------------------------------------------------------ the chord

  function inferRole(interval) {
    if (interval === 3 || interval === 4) return "third";
    if (interval === 7) return "fifth";
    if (interval === 10 || interval === 11) return "seventh";
    return null;
  }

  // role name -> semitones above the root, for one quality of the API
  function rolesOf(quality) {
    const found = {};
    const roles = quality.roles || {};
    const keys = Object.keys(roles);
    if (keys.length) {
      keys.forEach((k) => {
        if (!(roles[k] in found)) found[roles[k]] = Number(k);
      });
    } else {
      quality.intervals.forEach((i) => {
        const role = inferRole(i);
        if (role && !(role in found)) found[role] = i;
      });
    }
    return found;
  }

  function firstOf(roles, names) {
    for (const n of names) if (n in roles) return roles[n];
    return undefined;
  }

  function thirdSlot(roles) {
    return firstOf(roles, ["third", "second", "fourth"]);
  }
  function fifthSlot(roles) {
    return firstOf(roles, ["fifth", "flat_fifth", "sharp_fifth"]);
  }
  function seventhSlot(roles) {
    return firstOf(roles, ["seventh", "diminished_seventh", "sixth"]);
  }

  const ALTERED = ["flat_ninth", "sharp_ninth", "flat_fifth", "sharp_fifth", "flat_thirteenth", "sharp_eleventh", "second", "fourth"];

  // The pitch classes (as semitones above the root) a voicing keeps, lowest first.
  function voicingIntervals(quality, voicing) {
    const roles = rolesOf(quality);
    const all = [...quality.intervals].sort((a, b) => a - b);
    let picked;
    if (voicing === "shell") {
      const third = thirdSlot(roles);
      const upper = seventhSlot(roles);
      picked = [third, upper !== undefined ? upper : fifthSlot(roles)];
      if ("ninth" in roles) picked.push(roles.ninth);
      else if ("seventh" in roles && !ALTERED.some((r) => r in roles)) picked.push(2);
    } else if (voicing === "triad") {
      picked = [0, thirdSlot(roles), fifthSlot(roles)];
    } else {
      picked = all.slice();
      if (picked.length > 4 && fifthSlot(roles) !== undefined) picked = picked.filter((i) => i !== fifthSlot(roles));
      if (picked.length > 4) picked = picked.filter((i) => i !== 0);
    }
    const kept = [...new Set(picked.filter((i) => i !== undefined))].sort((a, b) => a - b);
    return kept.length ? kept : [0];
  }

  // ---------------------------------------------------------------- pitch finding

  // The note with this pitch class inside [low, high] that is closest to target. A range
  // the style validator accepts is always wide enough to hold every pitch class.
  function nearest(pc, target, low, high) {
    let best = null;
    let bestDistance = Infinity;
    for (let m = low; m <= high; m++) {
      if (m % 12 !== pc) continue;
      const d = Math.abs(m - target);
      if (d < bestDistance) {
        best = m;
        bestDistance = d;
      }
    }
    return best === null ? low + ((pc - (low % 12) + 12) % 12) : best;
  }

  // The first note above `prev` with this pitch class inside the range, else the lowest.
  function above(pc, prev, low, high) {
    for (let m = Math.max(low, prev + 1); m <= high; m++) if (m % 12 === pc) return m;
    return nearest(pc, low, low, high);
  }

  // ------------------------------------------------------------------- the bass

  const note = (beat, beats, midi, velocity) => ({ voice: "bass", beat, beats, midi, velocity });

  function approachNote(nextRootPc, prev, low, high) {
    const below = nearest((nextRootPc + 11) % 12, prev, low, high);
    const upper = nearest((nextRootPc + 1) % 12, prev, low, high);
    return Math.abs(below - prev) <= Math.abs(upper - prev) ? below : upper;
  }

  // One chord's stretch of the bar: `seg.start` and `seg.length` in beats. Each rule
  // returns its notes and leaves the last note's pitch in state.last, so the next chord
  // is reached from where this one ended.
  const BASS = {
    walking(seg, ctx) {
      const { low, high, state } = ctx;
      const count = Math.max(1, Math.floor(seg.length + EPS));
      const out = [];
      let prev = nearest(seg.bassPc, state.last === null ? Math.round((low + high) / 2) : state.last, low, high);
      out.push(note(seg.start, count === 1 ? seg.length : 1, prev, 0.85));
      for (let i = 1; i < count; i++) {
        const last = i === count - 1;
        const m = last ? approachNote(seg.nextRootPc, prev, low, high) : above((seg.rootPc + ctx.core[(i - 1) % ctx.core.length]) % 12, prev, low, high);
        out.push(note(seg.start + i, last ? seg.length - i : 1, m, last ? 0.72 : 0.7));
        prev = m;
      }
      state.last = prev;
      return out;
    },

    two_feel(seg, ctx) {
      return halves(seg, ctx, 0.8);
    },

    root_fifth(seg, ctx) {
      return halves(seg, ctx, 1);
    },

    eighths(seg, ctx) {
      const { low, high, state } = ctx;
      const m = nearest(seg.bassPc, state.last === null ? Math.round((low + high) / 2) : state.last, low, high);
      const out = [];
      for (let t = 0; t < seg.length - EPS; t += 0.5) {
        out.push(note(seg.start + t, Math.min(0.5, seg.length - t) * 0.9, m, Number.isInteger(t) ? 0.85 : 0.68));
      }
      state.last = m;
      return out;
    },

    bossa(seg, ctx) {
      const { low, high, state } = ctx;
      const r = nearest(seg.bassPc, state.last === null ? Math.round((low + high) / 2) : state.last, low, high);
      const lowerFifth = nearest(seg.fifthPc, r - 5, low, high);
      const fifth = lowerFifth < r ? lowerFifth : nearest(seg.fifthPc, r + 7, low, high);
      const out = [];
      for (let cell = 0; cell < seg.length - EPS; cell += 2) {
        const room = seg.length - cell;
        out.push(note(seg.start + cell, Math.min(1.5, room), r, 0.85));
        if (room > 1.5 + EPS) out.push(note(seg.start + cell + 1.5, Math.min(0.5, room - 1.5), fifth, 0.7));
      }
      state.last = r;
      return out;
    },

    boogie(seg, ctx) {
      const { low, high, state } = ctx;
      const r = nearest(seg.bassPc, low + 5, low, high);
      const third = ctx.third;
      const pattern = [0, third, 7, 9, 10, 9, 7, third];
      const out = [];
      let n = 0;
      for (let t = 0; t < seg.length - EPS; t += 0.5, n++) {
        let m = r + pattern[n % pattern.length];
        while (m > high) m -= 12;
        out.push(note(seg.start + t, Math.min(0.5, seg.length - t) * 0.95, m, Number.isInteger(t) ? 0.85 : 0.65));
      }
      state.last = r;
      return out;
    },
  };

  // Root on the first beat, the fifth two beats on. `hold` is how much of its slot a note
  // takes: short for the two-feel, the whole slot for the ringing pop and gospel sound.
  function halves(seg, ctx, hold) {
    const { low, high, state } = ctx;
    const r = nearest(seg.bassPc, state.last === null ? Math.round((low + high) / 2) : state.last, low, high);
    const out = [note(seg.start, Math.min(2, seg.length) * hold, r, 0.85)];
    let last = r;
    if (seg.length > 2 + EPS) {
      last = nearest(seg.fifthPc, r + 7, low, high);
      out.push(note(seg.start + 2, Math.min(2, seg.length - 2) * hold, last, 0.7));
    }
    state.last = last;
    return out;
  }

  // ------------------------------------------------------------------- the comping

  // Where to put a set of pitch classes inside the register: every inversion in every
  // octave that fits, and the one that moves least from the last voicing wins.
  function placeVoicing(pcs, previous, low, high) {
    const centre = (low + high) / 2;
    let best = null;
    let bestCost = Infinity;
    for (let rot = 0; rot < pcs.length; rot++) {
      const order = pcs.slice(rot).concat(pcs.slice(0, rot));
      for (let b = low; b <= high; b++) {
        if (b % 12 !== order[0]) continue;
        const notes = [b];
        for (let j = 1; j < order.length; j++) {
          let m = notes[j - 1] + 1;
          while (m % 12 !== order[j]) m++;
          notes.push(m);
        }
        if (notes[notes.length - 1] > high) continue;
        const mean = notes.reduce((a, c) => a + c, 0) / notes.length;
        let cost = Math.abs(mean - centre) * 0.1;
        if (previous && previous.length === notes.length) {
          cost += notes.reduce((a, c, i) => a + Math.abs(c - previous[i]), 0);
        } else if (previous) {
          const pm = previous.reduce((a, c) => a + c, 0) / previous.length;
          cost += Math.abs(mean - pm) * notes.length;
        }
        if (cost < bestCost - EPS) {
          best = notes;
          bestCost = cost;
        }
      }
    }
    if (best) return best;
    const order = pcs.slice();
    const out = [nearest(order[0], low, low, high)];
    for (let j = 1; j < order.length; j++) {
      let m = out[j - 1] + 1;
      while (m % 12 !== order[j]) m++;
      out.push(m);
    }
    return out;
  }

  // ----------------------------------------------------------------------- the plan

  const fail = (error) => ({ ok: false, error });

  function chordKey(c) {
    return `${c.root}|${c.quality}|${c.bass === null ? "" : c.bass}`;
  }

  function planBand(parsed, style, qualities, options) {
    const opts = options || {};
    if (!parsed || parsed.ok !== true || !Array.isArray(parsed.bars) || !parsed.bars.length) return fail("There is no chart to play.");
    if (!style || !style.drums || !style.bass || !style.comp) return fail("There is no style to play.");
    const signature = /^(\d+)\/4$/.exec(style.time_signature || "");
    if (!signature) return fail(`The band cannot play a ${style.time_signature} groove.`);
    const beatsPerBar = parsed.beatsPerBar;
    if (Number(signature[1]) !== beatsPerBar) {
      return fail(`${style.name || "This style"} is a ${style.time_signature} groove and the chart has ${beatsPerBar} beats to a bar.`);
    }
    const swingRatio = opts.swingRatio === undefined || opts.swingRatio === null ? Number(style.swing_ratio) : Number(opts.swingRatio);
    if (!(swingRatio >= 0.5 && swingRatio <= 0.75)) return fail("Swing has to be between 0.50 (straight) and 0.75.");
    const rule = style.bass.rule;
    if (!(rule in BASS)) return fail(`The band has no bass rule called "${rule}".`);
    if (!VOICINGS.includes(style.comp.voicing)) return fail(`The band has no voicing called "${style.comp.voicing}".`);

    const library = new Map((qualities || []).map((q) => [q.symbol, q]));
    const from = opts.from === undefined ? 0 : opts.from;
    const to = opts.to === undefined ? parsed.bars.length : opts.to;
    const slice = parsed.bars.slice(from, to);
    if (!slice.length) return fail("There are no bars in that range.");
    const loop = opts.loop !== false;

    const [bassLow, bassHigh] = style.bass.range;
    const [compLow, compHigh] = style.comp.register;
    const bassState = { last: null };
    const compState = { key: null, notes: null };
    const steps = beatsPerBar * STEPS_PER_BEAT;
    const bars = [];

    for (let i = 0; i < slice.length; i++) {
      const bar = slice[i];
      const nextBar = i + 1 < slice.length ? slice[i + 1] : loop ? slice[0] : null;
      const raw = [];

      for (const name of Object.keys(style.drums)) {
        const grid = style.drums[name];
        for (let s = 0; s < steps; s++) {
          if (grid[s] > 0) raw.push({ voice: "drums", inst: name, beat: s / STEPS_PER_BEAT, beats: 1 / STEPS_PER_BEAT, velocity: grid[s] });
        }
      }

      const segments = bar.chords.map((c, k) => {
        const q = library.get(c.quality);
        const next = k + 1 < bar.chords.length ? bar.chords[k + 1] : nextBar ? nextBar.chords[0] : c;
        return { chord: c, quality: q, start: c.beat, length: c.beats, end: c.beat + c.beats, next };
      });
      const missing = segments.find((s) => !s.quality);
      if (missing) return fail(`The band does not know the chord quality "${missing.chord.quality}" (chord ${missing.chord.typed}).`);

      for (const seg of segments) {
        const roles = rolesOf(seg.quality);
        const fifth = fifthSlot(roles);
        const core = [thirdSlot(roles), fifth, seventhSlot(roles)].filter((v) => v !== undefined);
        const detail = {
          start: seg.start,
          length: seg.length,
          rootPc: seg.chord.root,
          bassPc: seg.chord.bass === null ? seg.chord.root : seg.chord.bass,
          fifthPc: (seg.chord.root + (fifth === undefined ? 7 : fifth)) % 12,
          nextRootPc: seg.next.bass === null ? seg.next.root : seg.next.bass,
        };
        const ctx = { low: bassLow, high: bassHigh, state: bassState, core: core.length ? core : [7], third: thirdSlot(roles) === 3 ? 3 : 4 };
        raw.push(...BASS[rule](detail, ctx));
      }

      const voicings = new Map();
      const voiceChord = (seg) => {
        const key = chordKey(seg.chord);
        if (voicings.has(seg)) return voicings.get(seg);
        let notes;
        if (compState.key === key) notes = compState.notes;
        else {
          const pcs = voicingIntervals(seg.quality, style.comp.voicing).map((iv) => (seg.chord.root + iv) % 12);
          notes = placeVoicing(pcs, compState.notes, compLow, compHigh);
          compState.key = key;
          compState.notes = notes;
        }
        voicings.set(seg, notes);
        return notes;
      };
      style.comp.rhythm.forEach(([startStep, lengthSteps], h) => {
        const hitStart = startStep / STEPS_PER_BEAT;
        const hitEnd = (startStep + lengthSteps) / STEPS_PER_BEAT;
        for (const seg of segments) {
          const from2 = Math.max(hitStart, seg.start);
          const to2 = Math.min(hitEnd, seg.end);
          if (to2 - from2 <= EPS) continue;
          for (const m of voiceChord(seg)) raw.push({ voice: "comp", beat: from2, beats: (to2 - from2) * 0.92, midi: m, velocity: h === 0 ? 0.62 : 0.5 });
        }
      });

      const events = raw
        .map((e) => {
          const start = swingBeat(e.beat, swingRatio);
          return { ...e, beat: start, beats: swingBeat(e.beat + e.beats, swingRatio) - start };
        })
        .sort((a, b) => a.beat - b.beat || VOICE_ORDER[a.voice] - VOICE_ORDER[b.voice]);
      bars.push({ index: i, source: bar.n, beats: beatsPerBar, events });
    }

    return { ok: true, beatsPerBar, swingRatio, bars };
  }

  return { planBand, swingBeat, voicingIntervals, placeVoicing, nearest, rolesOf, DRUM_INSTRUMENTS, BASS_RULES, VOICINGS, STEPS_PER_BEAT };
});
