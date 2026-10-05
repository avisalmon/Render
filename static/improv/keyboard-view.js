// improv: draws a piano keyboard and lights notes on it. Browser only, and only text goes
// in, never markup. Used by the Reference screen, and meant for the Play screen's live
// feedback later, so the keys look the same wherever a note is shown.
(function () {
  "use strict";
  const BLACK = new Set([1, 3, 6, 8, 10]);

  // Gives back the key elements by MIDI note, so a caller can light them.
  function draw(host, from, to) {
    host.textContent = "";
    const keys = new Map();
    let whites = 0;
    for (let note = from; note <= to; note++) if (!BLACK.has(note % 12)) whites += 1;
    const width = 100 / Math.max(whites, 1);
    let index = 0;
    for (let note = from; note <= to; note++) {
      const key = document.createElement("div");
      key.dataset.note = String(note);
      if (BLACK.has(note % 12)) {
        key.className = "im-key im-key-black";
        key.style.left = index * width - width * 0.3 + "%";
        key.style.width = width * 0.6 + "%";
      } else {
        key.className = "im-key im-key-white";
        key.style.left = index * width + "%";
        key.style.width = width + "%";
        index += 1;
      }
      host.appendChild(key);
      keys.set(note, key);
    }
    return keys;
  }

  const LIT = ["im-key-on", "im-key-chord", "im-key-guide", "im-key-scale", "im-key-approach", "im-key-pending", "im-key-outside"];

  // notes is a list of { midi, step, className }: the step, if any, is written on the key, so
  // the shape and the intervals are read in one look; the class, if any, is the colour the
  // judge gave the note, and plain lit otherwise.
  function light(keys, notes) {
    for (const key of keys.values()) {
      key.classList.remove(...LIT);
      key.textContent = "";
    }
    for (const note of notes || []) {
      const key = keys.get(note.midi);
      if (!key) continue;
      key.classList.add(LIT.includes(note.className) ? note.className : "im-key-on");
      if (note.step) {
        const tag = document.createElement("span");
        tag.className = "im-key-step";
        tag.textContent = note.step;
        key.appendChild(tag);
      }
    }
  }

  window.ImprovKeyboardView = { draw, light };
})();
