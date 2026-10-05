// improv: naming what the player is holding down. Pure: no browser, runs under Node.
//
// The notes held, in, the best name for them, out. Every chord quality in the theory table is
// tried over every root and scored by how much of it is there and how much is left over, so
// the table stays the only place that says what a chord is. Three rules from spec chapter 4
// decide between readings: the bass is preferred as the root, a root that is not the bass makes
// a slash chord rather than a different chord, and fewer than three notes are not forced into a
// chord name at all. A reading that leaves a note of the chord out is offered as a best guess
// with the other readings of the same notes beside it, because those notes really are ambiguous.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./chart.js"));
  } else {
    root.ImprovRecognize = factory(root.ImprovChart);
  }
})(typeof self !== "undefined" ? self : this, function (Chart) {
  const INTERVAL_NAMES = [
    "the same note",
    "a minor second",
    "a major second",
    "a minor third",
    "a major third",
    "a fourth",
    "a tritone",
    "a fifth",
    "a minor sixth",
    "a major sixth",
    "a minor seventh",
    "a major seventh",
  ];
  const SHELL_ROLES = new Set(["third", "seventh"]);
  const MIN_PCS_FOR_A_SCALE = 5;
  const MOST_FITS_SHOWN = 3;

  const pcOf = (note) => ((note % 12) + 12) % 12;

  function spell(note, spelling) {
    const names = spelling === "flats" ? Chart.FLAT_NAMES : Chart.SHARP_NAMES;
    return names[pcOf(note)];
  }

  // Middle C (60) is C4.
  function noteLabel(note, spelling) {
    return spell(note, spelling) + (Math.floor(note / 12) - 1);
  }

  function intervalName(low, high) {
    const gap = high - low;
    if (gap === 12) return "an octave";
    return INTERVAL_NAMES[gap % 12];
  }

  // ------------------------------------------------------------------- scoring

  // Every quality over every root. A reading is better when more of the chord is actually
  // being held (present), worse for each note of the chord that is missing, and worse still
  // for a held note the chord cannot explain (extra), because that is the sign of a wrong name.
  //
  // Three rules earn their keep here. A missing note costs more than the bass bonus, so a
  // chord that is all there beats an incomplete one with the bass as its root: C, E and A is
  // Am/C, not a C6 with no fifth. The bass note is never "extra", because a bass note outside
  // the chord is exactly what the slash in C/F# is for. But a reading in which the bass does
  // belong to the chord is better evidence than one that has to treat it as a foreign note,
  // so C E A B is an Am9 without its fifth rather than an Asus2 with a C underneath.
  function readings(pcs, bass, qualities) {
    const held = new Set(pcs);
    const found = [];
    for (let root = 0; root < 12; root++) {
      for (const quality of qualities || []) {
        const intervals = quality.intervals || [];
        if (!intervals.length) continue;
        const required = intervals.map((i) => pcOf(root + i));
        const unique = new Set(required);
        let present = 0;
        for (const pc of unique) if (held.has(pc)) present += 1;
        const missing = unique.size - present;
        let extra = 0;
        for (const pc of held) if (!unique.has(pc) && pc !== bass) extra += 1;
        if (present < 2) continue;
        const rootHeld = held.has(root);
        const rootIsBass = root === bass;
        found.push({
          root,
          quality,
          present,
          missing,
          extra,
          rootHeld,
          rootIsBass,
          bassIsChordTone: unique.has(bass),
          size: unique.size,
          score:
            present * 4 -
            missing * 4 -
            extra * 5 +
            (rootHeld ? 2 : 0) +
            (rootIsBass ? 3 : 0) +
            (unique.has(bass) ? 2 : 0),
        });
      }
    }
    found.sort(
      (a, b) =>
        b.score - a.score ||
        Number(b.rootIsBass) - Number(a.rootIsBass) ||
        Number(b.rootHeld) - Number(a.rootHeld) ||
        a.size - b.size ||
        (a.quality.sort_order || 0) - (b.quality.sort_order || 0) ||
        a.root - b.root
    );
    return found;
  }

  function nameOf(reading, bass, spelling) {
    const rootName = spell(reading.root, spelling);
    const bassName = reading.root === bass ? "" : spell(bass, spelling);
    return Chart.chordName(rootName, reading.quality.symbol, bassName);
  }

  // The same notes read as other chords. Every held note has to be a note of the chord, the
  // bass included: a name that ignores a note the player is holding is not an alternative, it
  // is wrong, and a reading that needs the lowest note to be a foreign bass is a different
  // chord, not another reading of this one. And another reading has to explain the notes at
  // least as well as the one on offer: a guessier guess is not an alternative worth the room.
  function alternativesFor(found, winner, bass, spelling) {
    const names = [];
    const winnerName = nameOf(winner, bass, spelling);
    const others = found
      .filter((r) => r !== winner && r.extra === 0 && r.bassIsChordTone && r.missing <= winner.missing)
      .sort((a, b) => a.missing - b.missing || b.score - a.score);
    for (const reading of others) {
      const name = nameOf(reading, bass, spelling);
      if (name !== winnerName && !names.includes(name)) names.push(name);
      if (names.length === 3) break;
    }
    return names;
  }

  // The left-hand shell: the third and the seventh of a dominant seventh, held without the
  // root. Those two notes are always a tritone apart, and a tritone is the third and seventh
  // of exactly two dominant sevenths, so the page can name both instead of choosing. Any other
  // pair of notes is the third and seventh of too many chords to mean anything, so it is left
  // as two notes and an interval.
  function shellGuesses(pcs, qualities, spelling) {
    const guesses = [];
    if (pcs.length !== 2) return guesses;
    for (let root = 0; root < 12; root++) {
      for (const quality of qualities || []) {
        if (quality.family !== "dominant" || (quality.intervals || []).length !== 4) continue;
        const roles = quality.roles || {};
        const shell = Object.keys(roles)
          .filter((step) => SHELL_ROLES.has(roles[step]))
          .map((step) => pcOf(root + Number(step)));
        if (shell.length !== 2 || !pcs.every((pc) => shell.includes(pc))) continue;
        const name = Chart.chordName(spell(root, spelling), quality.symbol, "");
        if (!guesses.includes(name)) guesses.push(name);
      }
    }
    return guesses;
  }

  // ------------------------------------------------------------------- the answer

  function recognize(notes, qualities, options) {
    const spelling = (options || {}).spelling === "flats" ? "flats" : "sharps";
    const sorted = [...new Set(notes || [])].sort((a, b) => a - b);
    const labels = sorted.map((note) => noteLabel(note, spelling));
    const pcs = [...new Set(sorted.map(pcOf))];

    if (!sorted.length) return { kind: "none", notes: [], text: "" };

    if (pcs.length < 3) {
      const guesses = pcs.length === 2 ? shellGuesses(pcs, qualities, spelling) : [];
      const interval = sorted.length > 1 ? intervalName(sorted[0], sorted[sorted.length - 1]) : "";
      return {
        kind: "notes",
        notes: labels,
        interval,
        guesses,
        text: interval ? `${labels.join(" ")}, ${interval}` : labels.join(" "),
      };
    }

    const bass = pcOf(sorted[0]);
    const found = readings(pcs, bass, qualities);
    if (!found.length) return { kind: "notes", notes: labels, interval: "", guesses: [], text: labels.join(" ") };

    const winner = found[0];
    // Exact means every note held is a note of the chord and none of the chord is missing. A
    // foreign bass is not exact, however well the notes above it fit, so it is offered as a guess.
    const exact = winner.missing === 0 && winner.extra === 0 && winner.bassIsChordTone;
    return {
      kind: "chord",
      name: nameOf(winner, bass, spelling),
      root: spell(winner.root, spelling),
      quality: winner.quality.symbol,
      bass: spell(bass, spelling),
      slash: winner.root !== bass,
      exact,
      notes: labels,
      alternatives: exact ? [] : alternativesFor(found, winner, bass, spelling),
    };
  }

  // ------------------------------------------------------------------ scale hints

  // The notes played inside the last few seconds, oldest first. A run moves on, so what the
  // player is in the middle of is a window, not everything they have ever pressed.
  function recentNotes(events, now, seconds) {
    return (events || []).filter((e) => e && e.at > now - seconds && e.at <= now).map((e) => e.note);
  }

  // Which scales contain every note played. Three notes fit a dozen scales, so naming one
  // before five different notes have been heard would be a guess dressed as an answer; until
  // then the answer is how many more notes it wants. The closest fit comes first: the scale
  // with the fewest notes of its own left unplayed, then one whose root has actually been
  // played. Two scales can be the same five notes (a minor pentatonic is its relative major
  // pentatonic), so the one rooted on the note the run started from comes first; after that,
  // the order the theory table itself puts them in.
  function scaleFits(notes, scales, options) {
    const spelling = (options || {}).spelling === "flats" ? "flats" : "sharps";
    const needed = (options || {}).minimum === undefined ? MIN_PCS_FOR_A_SCALE : options.minimum;
    const played = [...new Set((notes || []).map(pcOf))];
    if (played.length < needed) return { ready: false, needed: needed - played.length, fits: [] };

    const found = [];
    for (let root = 0; root < 12; root++) {
      for (const scale of scales || []) {
        const intervals = scale.intervals || [];
        if (!intervals.length) continue;
        const inScale = intervals.map((i) => pcOf(root + i));
        if (!played.every((pc) => inScale.includes(pc))) continue;
        found.push({
          slug: scale.slug,
          rootPc: root,
          root: spell(root, spelling),
          name: `${spell(root, spelling)} ${scale.name}`,
          unused: inScale.filter((pc) => !played.includes(pc)).map((pc) => spell(pc, spelling)),
          rootPlayed: played.includes(root),
          rootIsFirst: root === played[0],
          order: scale.order || 0,
        });
      }
    }
    found.sort(
      (a, b) =>
        a.unused.length - b.unused.length ||
        Number(b.rootIsFirst) - Number(a.rootIsFirst) ||
        Number(b.rootPlayed) - Number(a.rootPlayed) ||
        a.order - b.order ||
        a.rootPc - b.rootPc
    );
    return { ready: true, needed: 0, fits: found.slice(0, MOST_FITS_SHOWN) };
  }

  return { recognize, scaleFits, recentNotes, noteLabel, intervalName, INTERVAL_NAMES, MIN_PCS_FOR_A_SCALE };
});
