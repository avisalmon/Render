// improv: the Reference screen. Browser glue only: read the menus, ask ImprovReference what
// the notes are, draw them on the keys. The rules live in reference.js and chart.js, which are
// tested under Node. Only text is ever put on the page.
(function () {
  "use strict";
  const Ref = window.ImprovReference;
  const Keys = window.ImprovKeyboardView;
  const $ = (id) => document.getElementById(id);
  const host = $("reference");

  const state = {
    spelling: "sharps",
    qualities: [],
    scales: [],
    chordScales: [],
    keys: null,
    range: null,
  };

  const say = (text) => ($("ref-status").textContent = text);

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  function make(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }

  function fillOptions(select, items, selected) {
    select.textContent = "";
    for (const [value, text] of items) {
      const option = make("option", text);
      option.value = String(value);
      select.appendChild(option);
    }
    if (selected !== undefined && selected !== null) select.value = String(selected);
  }

  // ------------------------------------------------------------------- drawing

  function drawKeyboard(view) {
    const range = Ref.keyboardRange(view);
    if (!state.keys || !state.range || range.from !== state.range.from || range.to !== state.range.to) {
      state.keys = Keys.draw($("ref-keyboard"), range.from, range.to);
      state.range = range;
    }
    Keys.light(state.keys, view.notes);
  }

  function listGoesWith(view) {
    const items = view.kind === "chord" ? view.scales : view.chords;
    const list = $("ref-goes");
    list.textContent = "";
    $("ref-goes-title").textContent = view.kind === "chord" ? "Scales that fit it" : "Chords it fits";
    $("ref-goes-empty").hidden = items.length > 0;
    for (const item of items) {
      const row = make("li", item.name, "im-list-item");
      if (item.note) row.appendChild(make("span", " " + item.note, "im-note-inline"));
      list.appendChild(row);
    }
  }

  function show() {
    const kind = $("ref-kind").value;
    const rootPc = Number($("ref-key").value);
    const options = { spelling: state.spelling };
    let view = null;
    if (kind === "chord") {
      const quality = state.qualities.find((q) => q.symbol === $("ref-chord").value);
      view = Ref.chordView(quality, rootPc, options);
    } else {
      const scale = state.scales.find((s) => s.slug === $("ref-scale").value);
      const fits = state.chordScales.filter((row) => row.scale_slug === $("ref-scale").value);
      view = Ref.scaleView(scale, rootPc, options, fits);
    }
    if (!view) {
      $("ref-name").textContent = "Nothing chosen yet";
      return;
    }
    $("ref-name").textContent = view.name;
    $("ref-notes").textContent = view.notes.map((n) => n.label).join("   ");
    $("ref-steps").textContent = view.notes
      .map((n) => (n.role ? `${n.step} (${n.role})` : n.step))
      .join(", ");
    drawKeyboard(view);
    listGoesWith(view);
  }

  function chooseKind() {
    const chord = $("ref-kind").value === "chord";
    $("ref-chord-row").hidden = !chord;
    $("ref-scale-row").hidden = chord;
    show();
  }

  // --------------------------------------------------------------------- start

  async function init() {
    try {
      const [profile, qualities, scales, chordScales] = await Promise.all([
        getJson(host.dataset.apiPlayer),
        getJson(host.dataset.apiQualities),
        getJson(host.dataset.apiScales),
        getJson(host.dataset.apiChordScales),
      ]);
      state.spelling = profile.note_names;
      state.qualities = qualities;
      state.scales = scales;
      state.chordScales = chordScales;
    } catch (e) {
      say("The reference could not load. " + e.message);
      return;
    }

    // The first row of each table is the opening choice: the table decides what is first,
    // so adding or reordering a chord in the admin does not need a change here.
    fillOptions($("ref-key"), Ref.keyChoices(state.spelling), 0);
    fillOptions($("ref-chord"), state.qualities.map((q) => [q.symbol, `${q.symbol}  ${q.name}`]), state.qualities[0].symbol);
    fillOptions($("ref-scale"), state.scales.map((s) => [s.slug, s.name]), state.scales[0].slug);
    say("Pick a chord or a scale and a key.");
    chooseKind();

    $("ref-kind").addEventListener("change", chooseKind);
    for (const id of ["ref-key", "ref-chord", "ref-scale"]) $(id).addEventListener("change", show);
  }

  if (!Ref || !Keys) say("The page's scripts did not load.");
  else init();
})();
