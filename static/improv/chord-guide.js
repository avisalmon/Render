// improv: what the Play screen's chord guide shows for one chord. Pure, no page. A chord goes in
// (as the parsed chart names it), the library's chord qualities with their ranked scales, and the
// spelling; out come the chord's notes by name, the scale it sits in, and the chord in its first
// positions laid left to right on a five-octave keyboard, so a player who does not know "Dm7" sees
// the keys, the scale around them, and the same chord a position higher each time.
//
//   const g = ImprovChordGuide.guideFor(chord, qualities, "flats");
//   g.keys    Map of MIDI note -> { role: "scale" | "p1" | "p2" | "p3", label }
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovChordGuide = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const FIRST = 48; // C3
  const LAST = 107; // B7
  const MAX_POSITIONS = 3;
  const SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];
  const POSITION_WORDS = ["Root position", "First inversion", "Second inversion"];

  const pcOf = (n) => ((n % 12) + 12) % 12;

  function nameOf(pc, spelling) {
    return (spelling === "flats" ? FLAT_NAMES : SHARP_NAMES)[pcOf(pc)];
  }

  // The chord's tones as semitones above the root, folded into one octave, sorted, no repeats.
  function tonesOf(quality) {
    const folded = (quality.intervals || []).map((i) => pcOf(i));
    return [...new Set(folded)].sort((a, b) => a - b);
  }

  // Position k keeps the tone k at the bottom and carries the lower tones up an octave. Each
  // position gets its own octave of the keyboard, starting on the chord's root, so they sit side
  // by side and none hides another.
  function voicing(rootMidi, tones, k) {
    return tones.map((t, i) => rootMidi + 12 * k + t + (i < k ? 12 : 0)).sort((a, b) => a - b);
  }

  function guideFor(chord, qualities, spelling) {
    if (!chord) return null;
    const quality = (qualities || []).find((q) => q.symbol === chord.quality);
    if (!quality) return null;
    const tones = tonesOf(quality);
    if (!tones.length) return null;
    const rootMidi = FIRST + pcOf(chord.root);

    const first = (quality.scales || [])[0] || null;
    const scalePcs = new Set(first ? (first.intervals || []).map((i) => pcOf(chord.root + i)) : []);

    const positions = [];
    for (let k = 0; k < Math.min(MAX_POSITIONS, tones.length); k++) {
      const notes = voicing(rootMidi, tones, k);
      if (notes[notes.length - 1] > LAST) break;
      positions.push({ index: k + 1, word: POSITION_WORDS[k], notes, names: notes.map((n) => nameOf(n, spelling)) });
    }

    const keys = new Map();
    for (let note = FIRST; note <= LAST; note++) if (scalePcs.has(pcOf(note))) keys.set(note, { role: "scale", label: "" });
    for (const p of positions) for (const note of p.notes) keys.set(note, { role: "p" + p.index, label: nameOf(note, spelling) });

    return {
      name: chord.name,
      from: FIRST,
      to: LAST,
      tones: tones.map((t) => nameOf(chord.root + t, spelling)),
      scaleName: first ? `${nameOf(chord.root, spelling)} ${first.name || first.slug}` : "",
      scaleNotes: first ? [...first.intervals].map((i) => nameOf(chord.root + i, spelling)) : [],
      positions,
      keys,
    };
  }

  // The chord sounding at a beat of a bar: the last one that has started.
  function chordInBar(bar, beat) {
    if (!bar || !bar.chords || !bar.chords.length) return null;
    let chord = bar.chords[0];
    for (const c of bar.chords) if (beat + 1e-9 >= c.beat) chord = c;
    return chord;
  }

  return { guideFor, chordInBar, FIRST, LAST, MAX_POSITIONS };
});
