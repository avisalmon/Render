// improv: draws a chart as a grid of bars. Browser only, and only text goes in, never markup:
// chord names and titles come from the database. Used by the Play screen and the editor.
(function () {
  "use strict";

  function span(className, text) {
    const el = document.createElement("span");
    el.className = className;
    el.textContent = text;
    return el;
  }

  // rows is what ImprovPlay.layoutBars returns. Gives back the cells by played-bar index, so
  // the caller can light one: { el, beat }.
  function draw(view, rows) {
    view.textContent = "";
    const cells = [];
    for (const row of rows) {
      const line = document.createElement("div");
      line.className = "im-chart-row";
      for (const cell of row) {
        const el = document.createElement("div");
        el.className = "im-bar" + (cell.inLoop ? "" : " im-bar-out");
        el.dataset.bar = String(cell.index);
        el.appendChild(span("im-bar-num", String(cell.number)));
        if (cell.keyChange) el.appendChild(span("im-bar-key", "key " + cell.keyChange));
        el.appendChild(span("im-bar-chords", cell.chords.join("   ")));
        const beat = span("im-bar-beat", "");
        el.appendChild(beat);
        line.appendChild(el);
        cells[cell.index] = { el, beat };
      }
      view.appendChild(line);
    }
    return cells;
  }

  window.ImprovChartView = { draw };
})();
