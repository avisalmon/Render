// improv: draws a grand staff for the reading trainer and the repertoire. Browser only, SVG, and only text goes
// in, never markup. The layout rules (which step is which line, where the key signature sits) come from
// reading.js; this file only places shapes. It gives back the note groups so the page can colour them, and a
// cursor and a curtain it can move.
//
// A note is {hand, step, acc, beat, dur, shown?, voice?, ties?, hold?}. Durations are quarter notes: 0.25 to 4,
// dotted at 0.75, 1.5 and 3. Notes at one beat in one hand and voice are a chord and share a stem; with two
// voices in a hand's bar the first points up and the second down. A long exercise is drawn in pages of
// `exercise.perPage` bars side by side in one wide picture; the view slides to the page the cursor is on, so a
// beat is the same width everywhere and the player never has to read small.
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
  const STEM = 30;
  const EPS = 1e-6;
  const LETTERS = ["C", "D", "E", "F", "G", "A", "B"];
  const DOTTED = [0.75, 1.5, 3];

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
  const voiceOf = (n) => n.voice || 1;

  // Rests that fill a gap that starts at beat `t`: never across a beat line when smaller than a beat.
  function restValues(t, gap) {
    const out = [];
    const sizes = [4, 2, 1, 0.5, 0.25];
    while (gap > EPS) {
      const toBeat = Math.abs(t - Math.round(t)) < EPS ? Infinity : Math.ceil(t) - t;
      const room = Math.min(gap, toBeat);
      const v = sizes.find((s) => s <= room + EPS);
      if (!v) break;
      out.push([t, v]);
      t += v;
      gap -= v;
    }
    return out;
  }

  // The silent shapes, centred on (x, y), y being the middle line of the staff.
  function drawRest(parent, kind, x, y, cls) {
    const g = el("g", { class: cls }, parent);
    if (kind === 4) el("rect", { x: x - 5.5, y: y - 10, width: 11, height: 4.5, class: "im-st-rest-fill" }, g);
    else if (kind === 2) el("rect", { x: x - 5.5, y: y - 4.5, width: 11, height: 4.5, class: "im-st-rest-fill" }, g);
    else if (kind === 1) el("path", { d: `M${x - 2} ${y - 10} L${x + 3} ${y - 4} L${x - 2} ${y + 1} Q${x + 4} ${y + 2} ${x} ${y + 9}`, class: "im-st-rest-line" }, g);
    else {
      const dots = kind === 0.5 ? 1 : 2;
      el("path", { d: `M${x + 3} ${y - 7} L${x - 2} ${y + 7 + (dots - 1) * 3}`, class: "im-st-rest-line" }, g);
      for (let d = 0; d < dots; d++) {
        const cx = x - 2.6 - d * 1.6;
        const cy = y - 4 + d * 5;
        el("circle", { cx, cy, r: 2, class: "im-st-rest-fill" }, g);
        el("path", { d: `M${cx} ${cy - 1.6} q 3 -1.4 5.6 -1.2`, class: "im-st-rest-line" }, g);
      }
    }
  }

  // Draws the staves, clefs, signature and notes of `exercise`. Returns the layout the page needs.
  function draw(svg, exercise, words) {
    svg.textContent = "";
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    // The drawing is every page side by side; a clip keeps the next page from showing in the margins of a wide box.
    const clipId = `${svg.id || "staff"}-clip`;
    const clipRect = el("rect", { x: 0, y: -60, width: W, height: H + 120 }, el("clipPath", { id: clipId }, el("defs", {}, svg)));
    const host = el("g", { "clip-path": `url(#${clipId})` }, svg);
    const bars = exercise.bars;
    const beats = exercise.beats;
    const per = exercise.perPage || bars;
    const pages = Math.max(1, Math.ceil(bars / per));
    const firstBar = exercise.firstBar || 1;
    const sig = R.signaturePositions(exercise.key);
    const sigW = sig.treble.length * 9 + (sig.treble.length ? 6 : 0);
    const bar0 = LEFT + CLEF_W + sigW + 30;
    const barW = (W - bar0 - RIGHT) / per;
    const bw = barW / beats;
    const pageOfBar = (bar) => Math.floor(bar / per);
    const barX = (bar) => pageOfBar(bar) * W + bar0 + (bar - pageOfBar(bar) * per) * barW;
    // One beat is the same width everywhere, bar lines included, so the cursor moves at one speed and
    // crosses a bar line at the same rate it crosses a beat.
    const barOfBeat = (beat) => Math.max(0, Math.min(bars - 1, Math.floor(beat / beats + EPS)));
    const noteX = (beat) => {
      const bar = barOfBeat(beat);
      return barX(bar) + 20 + (beat - bar * beats) * bw;
    };

    for (let p = 0; p < pages; p++) {
      const ox = p * W;
      for (const base of [TREBLE_Y, BASS_Y]) for (let i = 0; i < 5; i++) el("line", { x1: ox + LEFT, x2: ox + W - RIGHT, y1: base - i * 10, y2: base - i * 10, class: "im-st-line" }, host);
      el("line", { x1: ox + LEFT, x2: ox + LEFT, y1: TREBLE_Y - 40, y2: BASS_Y, class: "im-st-bar" }, host);
      text(host, ox + LEFT + 3, TREBLE_Y + 1, "\u{1D11E}", "im-st-clef", 50);
      text(host, ox + LEFT + 3, BASS_Y - 9, "\u{1D122}", "im-st-clef", 42);
      sig.treble.forEach((step, i) => text(host, ox + LEFT + CLEF_W + i * 9, yOf("R", step) + 5, ACC_GLYPH[sig.kind], "im-st-acc", 17));
      sig.bass.forEach((step, i) => text(host, ox + LEFT + CLEF_W + i * 9, yOf("L", step) + 5, ACC_GLYPH[sig.kind], "im-st-acc", 17));
      for (const base of [TREBLE_Y, BASS_Y]) {
        text(host, ox + LEFT + CLEF_W + sigW + 4, base - 22, String(beats), "im-st-time", 20);
        text(host, ox + LEFT + CLEF_W + sigW + 4, base - 2, "4", "im-st-time", 20);
      }
      // Which hand each staff is, and the key, next to it: the player should never have to work out the key.
      text(host, ox + 4, TREBLE_Y - 44, words.right, "im-st-hand", 11);
      text(host, ox + 4, BASS_Y - 44, words.left, "im-st-hand", 11);
      text(host, ox + 4, TREBLE_Y + 14, words.key, "im-st-key", 11);
      text(host, ox + 4, BASS_Y + 14, words.signature, "im-st-key", 11);
    }
    for (let b = 0; b < bars; b++) {
      const x = barX(b) + barW;
      el("line", { x1: x, x2: x, y1: TREBLE_Y - 40, y2: TREBLE_Y, class: "im-st-bar" }, host);
      el("line", { x1: x, x2: x, y1: BASS_Y - 40, y2: BASS_Y, class: "im-st-bar" }, host);
      text(host, barX(b) + 3, TREBLE_Y - 47, String(firstBar + b), "im-st-barno", 10);
    }

    const notes = exercise.notes;
    const active = (n) => R.isActive(exercise, n);

    // Heads are smaller when the music is dense, so sixteenths do not run into each other.
    const onsets = [...new Set(notes.map((n) => n.beat))].sort((a, b) => a - b);
    let gap = Infinity;
    for (let i = 1; i < onsets.length; i++) gap = Math.min(gap, onsets[i] - onsets[i - 1]);
    const rx = Math.min(6.2, Math.max(4.2, Number.isFinite(gap) ? bw * gap * 0.4 : 6.2));
    const ry = rx * 0.7;
    const edge = rx - 0.6;

    // Chords: one hand, one voice, one beat.
    const chordMap = new Map();
    notes.forEach((n, i) => {
      const key = `${n.hand}|${voiceOf(n)}|${n.beat}`;
      if (!chordMap.has(key)) chordMap.set(key, { hand: n.hand, voice: voiceOf(n), beat: n.beat, bar: n.bar, idx: [] });
      chordMap.get(key).idx.push(i);
    });
    const chords = [...chordMap.values()];
    const twoVoices = new Set();
    for (const n of notes) if (voiceOf(n) === 2) twoVoices.add(`${n.hand}|${n.bar}`);
    for (const c of chords) {
      c.dur = Math.min(...c.idx.map((i) => notes[i].dur));
      c.lo = Math.min(...c.idx.map((i) => notes[i].step));
      c.hi = Math.max(...c.idx.map((i) => notes[i].step));
    }

    // Beam groups: chords shorter than a beat, in one voice, touching, inside one beat.
    const lanes = new Map();
    for (const c of chords) {
      const key = `${c.hand}|${c.voice}`;
      if (!lanes.has(key)) lanes.set(key, []);
      lanes.get(key).push(c);
    }
    const groups = [];
    for (const lane of lanes.values()) {
      lane.sort((a, b) => a.beat - b.beat);
      let cur = null;
      for (const c of lane) {
        if (c.dur < 1 - EPS) {
          const joins = cur && Math.abs(cur.end - c.beat) < EPS && Math.floor(cur.members[0].beat + EPS) === Math.floor(c.beat + EPS);
          if (joins) cur.members.push(c);
          else {
            cur = { members: [c], end: 0 };
            groups.push(cur);
          }
          cur.end = c.beat + c.dur;
        } else {
          cur = null;
          groups.push({ members: [c], end: c.beat + c.dur });
        }
      }
    }
    for (const g of groups) {
      const first = g.members[0];
      const mid = (first.hand === "R" ? R.TREBLE.bottom : R.BASS.bottom) + 4;
      if (twoVoices.has(`${first.hand}|${first.bar}`)) g.up = first.voice === 1;
      else {
        const lo = Math.min(...g.members.map((c) => c.lo));
        const hi = Math.max(...g.members.map((c) => c.hi));
        g.up = mid - lo >= hi - mid;
      }
    }

    const layer = el("g", { class: "im-st-notes" }, host);
    const gs = notes.map((n, i) => el("g", { class: "im-st-note" + (active(n) ? "" : " im-st-other"), "data-index": i, tabindex: "-1" }, layer));

    const headX = notes.map((n) => noteX(n.beat));
    const headY = notes.map((n) => yOf(n.hand, n.step));
    const stemX = new Map();
    for (const g of groups) {
      for (const c of g.members) {
        const x = noteX(c.beat);
        const order = [...c.idx].sort((a, b) => notes[a].step - notes[b].step);
        if (!g.up) order.reverse();
        let prev = null;
        let prevFlipped = false;
        for (const i of order) {
          const touching = prev !== null && Math.abs(notes[i].step - notes[prev].step) === 1;
          const flipped = touching && !prevFlipped;
          if (flipped) headX[i] = x + (g.up ? 2 : -2) * edge;
          prev = i;
          prevFlipped = flipped;
        }
        stemX.set(c, x + (g.up ? edge : -edge));
      }
    }

    const ledger = (g, hand, step, x) => {
      const staff = hand === "R" ? R.TREBLE : R.BASS;
      const diff = step - staff.bottom;
      if (diff < 0) for (let d = -2; d >= diff; d -= 2) el("line", { x1: x - rx - 4, x2: x + rx + 4, y1: yOf(hand, staff.bottom + d), y2: yOf(hand, staff.bottom + d), class: "im-st-ledger" }, g);
      if (diff > 8) for (let d = 10; d <= diff; d += 2) el("line", { x1: x - rx - 4, x2: x + rx + 4, y1: yOf(hand, staff.bottom + d), y2: yOf(hand, staff.bottom + d), class: "im-st-ledger" }, g);
    };
    const head = (g, x, y, hollow) => el("ellipse", { cx: x, cy: y, rx, ry, transform: `rotate(-18 ${x} ${y})`, class: "im-st-head" + (hollow ? " im-st-hollow" : "") }, g);
    const dot = (g, x, y, step) => el("circle", { cx: x + rx + 4, cy: y - (step % 2 === 0 ? SP : 0), r: 1.6, class: "im-st-dot" }, g);

    notes.forEach((n, i) => {
      const g = gs[i];
      const x = headX[i];
      const y = headY[i];
      ledger(g, n.hand, n.step, x);
      head(g, x, y, n.dur >= 2);
      if (DOTTED.includes(n.dur)) dot(g, x, y, n.step);
      if (n.shown) text(g, x - rx - 12, y + 6, ACC_GLYPH[n.shown], "im-st-acc", 17);
    });

    // Stems, beams and flags belong to the first note of the chord, so they take its colour.
    for (const g of groups) {
      const beamed = g.members.length > 1;
      const dir = g.up ? -1 : 1;
      const lines = Math.min(...g.members.map((c) => c.dur)) <= 0.25 + EPS ? 2 : 1;
      const reach = STEM + (lines - 1) * 5;
      const tips = g.members.map((c) => {
        const ys = c.idx.map((i) => headY[i]);
        return g.up ? Math.min(...ys) - reach : Math.max(...ys) + reach;
      });
      const beamY = g.up ? Math.min(...tips) : Math.max(...tips);
      g.members.forEach((c, k) => {
        if (c.dur >= 4 - EPS) return;
        const lead = gs[c.idx[0]];
        const ys = c.idx.map((i) => headY[i]);
        const sx = stemX.get(c);
        const tip = beamed ? beamY : tips[k];
        el("line", { x1: sx, x2: sx, y1: g.up ? Math.max(...ys) : Math.min(...ys), y2: tip, class: "im-st-stem" }, lead);
        if (!beamed && c.dur < 1 - EPS) {
          const flags = c.dur <= 0.25 + EPS ? 2 : 1;
          for (let f = 0; f < flags; f++) {
            const ty = tip - dir * f * 5;
            el("path", { d: `M${sx} ${ty} q 7 ${-dir * -4} 5 ${-dir * -14}`, class: "im-st-flag" }, lead);
          }
        }
      });
      if (!beamed) continue;
      const lead = gs[g.members[0].idx[0]];
      const first = stemX.get(g.members[0]);
      const last = stemX.get(g.members[g.members.length - 1]);
      el("line", { x1: first - 0.75, x2: last + 0.75, y1: beamY, y2: beamY, class: "im-st-beam" }, lead);
      const short = g.members.map((c) => c.dur <= 0.25 + EPS);
      const second = beamY - dir * 5.5;
      short.forEach((isShort, k) => {
        if (!isShort) return;
        const sx = stemX.get(g.members[k]);
        if (k + 1 < short.length && short[k + 1]) {
          el("line", { x1: sx - 0.75, x2: stemX.get(g.members[k + 1]) + 0.75, y1: second, y2: second, class: "im-st-beam" }, lead);
        } else if (!(k > 0 && short[k - 1])) {
          const toward = k + 1 < short.length ? 1 : -1;
          el("line", { x1: sx, x2: sx + toward * 8, y1: second, y2: second, class: "im-st-beam" }, lead);
        }
      });
    }

    // A tied note is one note that goes on sounding: its later heads sit in the same group, joined by an arc.
    notes.forEach((n, i) => {
      if (!n.ties || !n.ties.length) return;
      const g = gs[i];
      const chord = chordMap.get(`${n.hand}|${voiceOf(n)}|${n.beat}`);
      const grp = groups.find((q) => q.members.includes(chord));
      const dir = grp.up ? -1 : 1;
      let fromX = headX[i];
      for (const [beat, dur] of n.ties) {
        const x = noteX(beat);
        const y = headY[i];
        ledger(g, n.hand, n.step, x);
        head(g, x, y, dur >= 2);
        if (DOTTED.includes(dur)) dot(g, x, y, n.step);
        if (dur < 4) {
          const sx = x + (grp.up ? edge : -edge);
          el("line", { x1: sx, x2: sx, y1: y, y2: y + dir * STEM, class: "im-st-stem" }, g);
        }
        const ay = y - dir * 5;
        el("path", { d: `M${fromX + rx * 0.6} ${ay} Q${(fromX + x) / 2} ${ay - dir * 9} ${x - rx * 0.6} ${ay}`, class: "im-st-tie" }, g);
        fromX = x;
      }
    });

    // Rests: a hand's first voice, wherever it falls silent inside a bar.
    const restLayer = el("g", { class: "im-st-rests" }, host);
    for (const hand of ["R", "L"]) {
      const base = hand === "R" ? TREBLE_Y : BASS_Y;
      const cls = "im-st-rest" + (active({ hand }) ? "" : " im-st-other");
      for (let b = 0; b < bars; b++) {
        const here = notes.filter((n) => n.hand === hand && n.bar === b);
        const shift = twoVoices.has(`${hand}|${b}`) ? -10 : 0;
        if (!here.length) {
          drawRest(restLayer, 4, barX(b) + barW / 2, base - 20, cls);
          continue;
        }
        const own = here.filter((n) => voiceOf(n) === 1);
        const onsetsHere = [...new Set(own.map((n) => n.beat))].sort((a, c) => a - c);
        let t = b * beats;
        const end = (b + 1) * beats;
        const fill = (from, to) => {
          for (const [at, kind] of restValues(from, to - from)) drawRest(restLayer, kind, noteX(at), base - 20 + shift, cls);
        };
        for (const onset of onsetsHere) {
          if (onset - t > EPS) fill(t, onset);
          const reachEnd = Math.max(...own.filter((n) => n.beat === onset).map((n) => n.beat + (n.hold || n.dur)));
          t = Math.max(t, reachEnd);
        }
        if (own.length && end - t > EPS) fill(t, end);
      }
    }

    const ghosts = el("g", { class: "im-st-ghosts" }, host);
    const curtain = el("rect", { class: "im-st-curtain", x: bar0, y: 0, width: 0, height: H, visibility: "hidden" }, host);
    const cursor = el("line", { class: "im-st-cursor", x1: 0, x2: 0, y1: 44, y2: 232, visibility: "hidden" }, host);

    const layout = {
      groups: gs,
      noteX,
      bar0,
      barW,
      pages,
      page: 0,
      perPage: per,
      pageOfBeat: (beat) => pageOfBar(barOfBeat(beat)),
      // Slides the view to a page of the picture.
      show(p) {
        const page = Math.max(0, Math.min(pages - 1, p));
        layout.page = page;
        svg.setAttribute("viewBox", `${page * W} 0 ${W} ${H}`);
        clipRect.setAttribute("x", page * W);
      },
      // Puts the cursor at a beat; with the curtain on, everything behind it is covered.
      place(beat, curtainOn, fromBar) {
        const x = noteX(beat);
        const page = pageOfBar(barOfBeat(beat));
        if (page !== layout.page) layout.show(page);
        cursor.setAttribute("x1", x);
        cursor.setAttribute("x2", x);
        cursor.setAttribute("visibility", "visible");
        if (curtainOn) {
          const from = Math.max(barX(Math.min(bars - 1, fromBar || 0)), page * W + bar0);
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
        const n = notes[index];
        const spelled = R.spell(midi, exercise.key);
        const x = noteX(n.beat) + 1;
        const y = yOf(n.hand, spelled.step);
        el("ellipse", { cx: x, cy: y, rx, ry, transform: `rotate(-18 ${x} ${y})`, class: "im-st-ghost", "data-ghost": index }, ghosts);
      },
      clearGhosts() {
        ghosts.textContent = "";
      },
    };
    return layout;
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
        else if (r.state === "out" && !g.classList.contains("im-st-other")) g.classList.add("im-st-out");
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
