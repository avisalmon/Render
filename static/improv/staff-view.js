// improv: draws a grand staff for the reading trainer. Browser only, SVG, and only text goes in, never
// markup. The layout rules (which step is which line, where the key signature sits) come from reading.js;
// this file only places shapes. It gives back the note groups so the page can colour them, and a cursor and
// a curtain it can move.
(function () {
  "use strict";
  const R = window.ImprovReading;
  const NS = "http://www.w3.org/2000/svg";
  const W = 960;
  const H = 250;
  const LEFT = 64;
  const RIGHT = 16;
  const SP = 5; // half a staff space
  const TREBLE_Y = 100; // the bottom line of the treble staff
  const BASS_Y = 215;
  const CLEF_W = 46;
  const LETTERS = ["C", "D", "E", "F", "G", "A", "B"];

  function el(tag, attrs, parent) {
    const node = document.createElementNS(NS, tag);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function text(parent, x, y, content, cls, size) {
    const t = el("text", { x, y, class: cls, "font-size": size }, parent);
    t.textContent = content;
    return t;
  }

  function yOf(hand, step) {
    const staff = hand === "R" ? R.TREBLE : R.BASS;
    const base = hand === "R" ? TREBLE_Y : BASS_Y;
    return base - (step - staff.bottom) * SP;
  }

  const ACC_GLYPH = { "#": "♯", b: "♭", n: "♮" };

  // Draws the staves, clefs, signature and notes of `exercise`. Returns the layout the page needs.
  function draw(host, exercise, words) {
    host.textContent = "";
    host.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const sig = R.signaturePositions(exercise.key);
    const sigW = sig.treble.length * 9 + (sig.treble.length ? 6 : 0);
    const bar0 = LEFT + CLEF_W + sigW + 30;
    const barW = (W - bar0 - RIGHT) / exercise.bars;
    const noteX = (beat) => {
      const bar = Math.floor(beat / exercise.beats);
      const inBar = beat - bar * exercise.beats;
      return bar0 + bar * barW + 20 + inBar * ((barW - 30) / exercise.beats);
    };

    for (const base of [TREBLE_Y, BASS_Y]) for (let i = 0; i < 5; i++) el("line", { x1: LEFT, x2: W - RIGHT, y1: base - i * 10, y2: base - i * 10, class: "im-st-line" }, host);
    el("line", { x1: LEFT, x2: LEFT, y1: TREBLE_Y - 40, y2: BASS_Y, class: "im-st-bar" }, host);
    for (let b = 1; b <= exercise.bars; b++) {
      const x = bar0 + b * barW;
      el("line", { x1: x, x2: x, y1: TREBLE_Y - 40, y2: TREBLE_Y, class: "im-st-bar" }, host);
      el("line", { x1: x, x2: x, y1: BASS_Y - 40, y2: BASS_Y, class: "im-st-bar" }, host);
      text(host, bar0 + (b - 1) * barW + 3, TREBLE_Y - 47, String(b), "im-st-barno", 10);
    }
    text(host, LEFT + 3, TREBLE_Y + 1, "\u{1D11E}", "im-st-clef", 50);
    text(host, LEFT + 3, BASS_Y - 9, "\u{1D122}", "im-st-clef", 42);
    sig.treble.forEach((step, i) => text(host, LEFT + CLEF_W + i * 9, yOf("R", step) + 5, ACC_GLYPH[sig.kind], "im-st-acc", 17));
    sig.bass.forEach((step, i) => text(host, LEFT + CLEF_W + i * 9, yOf("L", step) + 5, ACC_GLYPH[sig.kind], "im-st-acc", 17));
    for (const base of [TREBLE_Y, BASS_Y]) {
      text(host, LEFT + CLEF_W + sigW + 4, base - 22, String(exercise.beats), "im-st-time", 20);
      text(host, LEFT + CLEF_W + sigW + 4, base - 2, "4", "im-st-time", 20);
    }
    // Which hand each staff is, and the key, next to it: the player should never have to work out the key.
    text(host, 4, TREBLE_Y - 44, words.right, "im-st-hand", 11);
    text(host, 4, BASS_Y - 44, words.left, "im-st-hand", 11);
    text(host, 4, TREBLE_Y + 14, words.key, "im-st-key", 11);
    text(host, 4, BASS_Y + 14, words.signature, "im-st-key", 11);

    const silent = exercise.hands === "R" ? "L" : exercise.hands === "L" ? "R" : null;
    if (silent) {
      for (let b = 0; b < exercise.bars; b++) {
        const base = silent === "R" ? TREBLE_Y : BASS_Y;
        el("rect", { x: bar0 + b * barW + barW / 2 - 7, y: base - 30, width: 14, height: 5, class: "im-st-rest" }, host);
      }
    }

    const layer = el("g", { class: "im-st-notes" }, host);
    const groups = [];
    const beamed = new Set();
    exercise.notes.forEach((n, i) => {
      const x = noteX(n.beat);
      const y = yOf(n.hand, n.step);
      const g = el("g", { class: "im-st-note", "data-index": i, tabindex: "-1" }, layer);
      const staff = n.hand === "R" ? R.TREBLE : R.BASS;
      const diff = n.step - staff.bottom;
      if (diff < 0) for (let d = -2; d >= diff; d -= 2) el("line", { x1: x - 10, x2: x + 10, y1: yOf(n.hand, staff.bottom + d), y2: yOf(n.hand, staff.bottom + d), class: "im-st-ledger" }, g);
      if (diff > 8) for (let d = 10; d <= diff; d += 2) el("line", { x1: x - 10, x2: x + 10, y1: yOf(n.hand, staff.bottom + d), y2: yOf(n.hand, staff.bottom + d), class: "im-st-ledger" }, g);
      const hollow = n.dur >= 2;
      el("ellipse", { cx: x, cy: y, rx: 6.2, ry: 4.3, transform: `rotate(-18 ${x} ${y})`, class: "im-st-head" + (hollow ? " im-st-hollow" : "") }, g);
      if (n.dur === 3) el("circle", { cx: x + 10, cy: y - (n.step % 2 === 0 ? 5 : 0) + (n.step % 2 === 0 ? 0 : 0), r: 1.6, class: "im-st-dot" }, g);
      const mid = n.hand === "R" ? staff.bottom + 4 : staff.bottom + 4;
      if (n.dur < 4) {
        // An eighth pair shares a beam and a direction; a single stem points away from the middle line.
        const mate = n.dur === 0.5 ? exercise.notes.find((m) => m.hand === n.hand && m.dur === 0.5 && Math.abs(m.beat - (n.beat + (n.beat % 1 === 0 ? 0.5 : -0.5))) < 0.001) : null;
        const lead = mate ? (n.beat < mate.beat ? n : mate) : n;
        const up = mate ? Math.max(n.step, mate.step) < mid : n.step < mid;
        const sx = up ? x + 5.6 : x - 5.6;
        const top = up ? y - 33 : y + 33;
        el("line", { x1: sx, x2: sx, y1: y, y2: top, class: "im-st-stem" }, g);
        if (mate && lead === n && !beamed.has(mate.index)) {
          beamed.add(n.index);
          const mx = noteX(mate.beat);
          const msx = up ? mx + 5.6 : mx - 5.6;
          const mtop = up ? yOf(mate.hand, mate.step) - 33 : yOf(mate.hand, mate.step) + 33;
          el("line", { x1: sx, y1: top, x2: msx, y2: mtop, class: "im-st-beam" }, g);
        } else if (n.dur === 0.5 && !mate) {
          el("path", { d: `M${sx} ${top} q 8 6 6 18`, class: "im-st-flag" }, g);
        }
      }
      if (n.shown) text(g, x - 20, y + 6, ACC_GLYPH[n.shown], "im-st-acc", 17);
      groups.push(g);
    });

    const ghosts = el("g", { class: "im-st-ghosts" }, host);
    const curtain = el("rect", { class: "im-st-curtain", x: bar0, y: 0, width: 0, height: H, visibility: "hidden" }, host);
    const cursor = el("line", { class: "im-st-cursor", x1: 0, x2: 0, y1: 44, y2: 232, visibility: "hidden" }, host);

    return {
      groups,
      noteX,
      bar0,
      barW,
      // Puts the cursor at a beat; with the curtain on, everything behind it is covered.
      place(beat, curtainOn, fromBar) {
        const x = noteX(beat);
        cursor.setAttribute("x1", x);
        cursor.setAttribute("x2", x);
        cursor.setAttribute("visibility", "visible");
        if (curtainOn) {
          const from = bar0 + (fromBar || 0) * barW;
          curtain.setAttribute("x", from);
          curtain.setAttribute("width", Math.max(0, x - 14 - from));
          curtain.setAttribute("visibility", "visible");
        } else curtain.setAttribute("visibility", "hidden");
      },
      hide() {
        cursor.setAttribute("visibility", "hidden");
        curtain.setAttribute("visibility", "hidden");
      },
      // A dotted head where the wrong note was played, so what was read and what was played sit together.
      ghost(index, midi) {
        const n = exercise.notes[index];
        const spelled = R.spell(midi, exercise.key);
        const x = noteX(n.beat) + 1;
        const y = yOf(n.hand, spelled.step);
        el("ellipse", { cx: x, cy: y, rx: 6.2, ry: 4.3, transform: `rotate(-18 ${x} ${y})`, class: "im-st-ghost", "data-ghost": index }, ghosts);
      },
      clearGhosts() {
        ghosts.textContent = "";
      },
    };
  }

  // The colour of each note from a judgement: right, off (early or late), wrong, missed, out, or none.
  const STATES = ["im-st-right", "im-st-off", "im-st-wrong", "im-st-missed", "im-st-out", "im-st-now", "im-st-due"];

  function paint(layout, result, dueIndexes) {
    const due = new Set(dueIndexes || []);
    layout.groups.forEach((g, i) => {
      g.classList.remove(...STATES);
      const r = result ? result.results[i] : null;
      if (r) {
        if (r.state === "right") g.classList.add(r.timing === "ontime" || r.timing === "quick" ? "im-st-right" : "im-st-off");
        else if (r.state === "wrong") g.classList.add("im-st-wrong");
        else if (r.state === "missed") g.classList.add("im-st-missed");
        else if (r.state === "out") g.classList.add("im-st-out");
      }
      if (due.has(i)) g.classList.add("im-st-due");
    });
  }

  function light(layout, indexes) {
    const on = new Set(indexes || []);
    layout.groups.forEach((g, i) => g.classList.toggle("im-st-now", on.has(i)));
  }

  window.ImprovStaffView = { draw, paint, light, LETTERS };
})();
