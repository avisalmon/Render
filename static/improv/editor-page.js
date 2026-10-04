// improv: the chart editor screen. Browser glue only: read the fields, call ImprovEditor, draw.
// The rules live in editor.js and chart.js, which are tested under Node. The server only
// checks that a chart is not blank, so this page is where a bad chart is refused: Save stays
// off until the chart parses. Only text is ever put on the page.
(function () {
  "use strict";
  const E = window.ImprovEditor;
  const L = window.ImprovLibrary;
  const P = window.ImprovPlay;
  const View = window.ImprovChartView;
  const $ = (id) => document.getElementById(id);
  const host = $("editor");

  const state = {
    qualities: [],
    styles: [],
    tags: [],
    mode: "new",
    draft: null,
    original: null,
    check: null,
    saving: false,
    armed: false,
    armTimer: 0,
  };

  const say = (text) => ($("editor-status").textContent = text);

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  function make(tag, text) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function fillOptions(select, items, selected) {
    select.textContent = "";
    for (const [value, label] of items) {
      const option = make("option", label);
      option.value = String(value);
      select.appendChild(option);
    }
    if (selected !== undefined && selected !== null) select.value = String(selected);
  }

  function signatures() {
    const found = new Set(state.styles.map((s) => s.time_signature));
    found.add(state.draft ? state.draft.time_signature : "4/4");
    return [...found].sort((a, b) => L.beatsOf(a) - L.beatsOf(b));
  }

  function fillStyles(signature, genre, keep) {
    const fits = state.styles.filter((s) => s.time_signature === signature);
    fillOptions($("style"), fits.map((s) => [s.id, `${s.name} (${s.genre})`]));
    const kept = fits.find((s) => s.id === keep);
    const id = kept ? kept.id : E.suggestStyle(state.styles, genre, signature);
    $("style").value = id === null ? "" : String(id);
  }

  function buildTags() {
    const box = $("tags");
    box.textContent = "";
    for (const tag of state.tags) {
      const label = make("label");
      label.className = "im-check im-chip-check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = tag.slug;
      label.appendChild(input);
      label.appendChild(document.createTextNode(" " + tag.name));
      box.appendChild(label);
    }
  }

  // ---------------------------------------------------------------- the fields

  function writeFields(draft) {
    $("title").value = draft.title;
    fillOptions($("genre"), E.GENRES.map((g) => [g, g.charAt(0).toUpperCase() + g.slice(1)]), draft.genre);
    fillOptions($("home-key"), E.HOME_KEYS.map((k) => [k, k]), draft.home_key);
    fillOptions($("signature"), signatures().map((s) => [s, s]), draft.time_signature);
    $("tempo").value = draft.default_tempo;
    fillStyles(draft.time_signature, draft.genre, draft.default_style);
    fillOptions($("difficulty"), L.DIFFICULTY_NAMES.map((n, i) => [i + 1, `${i + 1}  ${n}`]), draft.difficulty);
    $("description").value = draft.description;
    $("chart-text").value = draft.chart;
    for (const box of $("tags").querySelectorAll("input")) box.checked = draft.tags.includes(box.value);
  }

  function readFields() {
    const draft = { ...state.draft };
    draft.title = $("title").value;
    draft.genre = $("genre").value;
    draft.home_key = $("home-key").value;
    draft.time_signature = $("signature").value;
    draft.default_tempo = $("tempo").value;
    draft.default_style = $("style").value === "" ? null : Number($("style").value);
    draft.difficulty = $("difficulty").value;
    draft.description = $("description").value;
    draft.chart = $("chart-text").value;
    draft.tags = [...$("tags").querySelectorAll("input")].filter((b) => b.checked).map((b) => b.value);
    return draft;
  }

  // ----------------------------------------------------------------- the check

  function showCheck() {
    const c = state.check;
    const line = $("chart-check");
    const box = $("chart-error");
    line.classList.toggle("im-ok", c.ok);
    line.classList.toggle("im-bad", !c.ok);
    if (c.ok) {
      line.textContent = "OK: " + c.summary;
      box.hidden = true;
      return;
    }
    line.textContent = c.where ? `${c.where}: ${c.message}` : c.message;
    box.hidden = c.line === undefined;
    if (c.line !== undefined) $("chart-error-line").textContent = c.lineText + "\n" + c.caret;
  }

  function drawPreview() {
    const view = $("chart-preview");
    view.textContent = "";
    if (state.check && state.check.ok) {
      const parsed = state.check.parsed;
      View.draw(view, P.layoutBars(parsed, 0, parsed.bars.length));
    }
  }

  function showProblems(found) {
    const list = Object.values(found);
    $("editor-problems").hidden = list.length === 0;
    $("editor-problems").textContent = list.join(" ");
  }

  function update() {
    state.draft = readFields();
    state.check = E.checkChart(state.draft.chart, state.qualities, {
      signature: state.draft.time_signature,
      homeKey: state.draft.home_key,
    });
    showCheck();
    drawPreview();
    const found = E.problems(state.draft);
    showProblems(found);
    const changed = state.mode !== "edit" || E.isDirty(state.draft, state.original);
    $("save").disabled = state.saving || Object.keys(found).length > 0 || !state.check.ok || !changed;
  }

  function jumpToError() {
    const c = state.check;
    if (!c || c.ok || c.offset === undefined) return;
    const area = $("chart-text");
    const rest = area.value.slice(c.offset);
    const word = /^[^\s|]+/.exec(rest);
    area.focus();
    area.setSelectionRange(c.offset, c.offset + (word ? word[0].length : 1));
  }

  // -------------------------------------------------------------------- saving

  function describeErrors(data) {
    if (!data || typeof data !== "object") return "The server refused it.";
    const parts = [];
    for (const [field, value] of Object.entries(data)) {
      const text = Array.isArray(value) ? value.join(" ") : String(value);
      parts.push(field === "detail" || field === "non_field_errors" ? text : `${field}: ${text}`);
    }
    return parts.join(" ");
  }

  async function send(method, url, body) {
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": host.dataset.csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(describeErrors(data));
    return data;
  }

  function enterEdit(saved) {
    state.mode = "edit";
    state.draft = E.draftFrom(saved);
    state.original = E.draftFrom(saved);
    $("editor-title").textContent = "Edit progression";
    $("open-play").href = host.dataset.playUrl + "?p=" + encodeURIComponent(saved.slug);
    $("open-play").hidden = false;
    $("delete").hidden = false;
    window.history.replaceState(null, "", window.location.pathname + "?p=" + encodeURIComponent(saved.slug));
  }

  async function save() {
    update();
    if ($("save").disabled) return;
    state.saving = true;
    $("save").disabled = true;
    say("Saving.");
    try {
      const body = E.toBody(state.draft);
      const base = host.dataset.apiProgressions;
      const saved =
        state.mode === "edit" ? await send("PATCH", `${base}${state.draft.id}/`, body) : await send("POST", base, body);
      enterEdit(saved);
      writeFields(state.draft);
      say(`Saved "${saved.title}".`);
    } catch (e) {
      say("It was not saved. " + e.message);
    }
    state.saving = false;
    update();
  }

  function disarm() {
    state.armed = false;
    window.clearTimeout(state.armTimer);
    $("delete").textContent = "Delete";
  }

  async function remove() {
    if (state.mode !== "edit") return;
    if (!state.armed) {
      state.armed = true;
      $("delete").textContent = "Click again to delete";
      state.armTimer = window.setTimeout(disarm, 5000);
      return;
    }
    disarm();
    try {
      await send("DELETE", `${host.dataset.apiProgressions}${state.draft.id}/`);
      state.original = state.draft;
      window.location.assign(host.dataset.libraryUrl);
    } catch (e) {
      say("It was not deleted. " + e.message);
    }
  }

  // --------------------------------------------------------------------- start

  function onSignatureOrGenre() {
    fillStyles($("signature").value, $("genre").value, $("style").value === "" ? null : Number($("style").value));
    update();
  }

  async function init() {
    try {
      const [qualities, styles, tags] = await Promise.all([
        getJson(host.dataset.apiQualities),
        getJson(host.dataset.apiStyles),
        getJson(host.dataset.apiTags),
      ]);
      state.qualities = qualities;
      state.styles = styles;
      state.tags = tags;
    } catch (e) {
      say("The editor could not load. " + e.message);
      return;
    }

    let source = null;
    const asked = new URLSearchParams(window.location.search).get("p");
    if (asked) {
      try {
        const all = await getJson(host.dataset.apiProgressions);
        source = all.find((p) => p.slug === asked) || null;
      } catch (e) {
        say("The progression could not be loaded. " + e.message);
        return;
      }
      if (!source) say(`There is no progression "${asked}". Starting a new one.`);
    }

    state.mode = E.modeFor(source);
    state.draft = source ? E.draftFrom(source) : E.blankDraft();
    if (!source || state.mode === "copy") {
      if (state.draft.default_style === null) state.draft.default_style = E.suggestStyle(state.styles, state.draft.genre, state.draft.time_signature);
    }
    state.original = { ...state.draft, tags: [...state.draft.tags] };

    buildTags();
    writeFields(state.draft);
    if (state.mode === "edit") {
      $("editor-title").textContent = "Edit progression";
      $("open-play").href = host.dataset.playUrl + "?p=" + encodeURIComponent(source.slug);
      $("open-play").hidden = false;
      $("delete").hidden = false;
      say("Change what you like, then Save.");
    } else if (state.mode === "copy") {
      $("editor-title").textContent = "Make my copy";
      say("This is a ready-made progression, so it saves as your own copy.");
    } else {
      $("editor-title").textContent = "New progression";
      if (!asked) say("Write the chart, give it a title, then Save.");
    }
    update();

    for (const id of ["title", "home-key", "tempo", "style", "difficulty", "description", "chart-text"]) {
      $(id).addEventListener("input", update);
    }
    $("genre").addEventListener("change", onSignatureOrGenre);
    $("signature").addEventListener("change", onSignatureOrGenre);
    $("tags").addEventListener("change", update);
    $("chart-goto").addEventListener("click", jumpToError);
    $("save").addEventListener("click", save);
    $("delete").addEventListener("click", remove);
    $("delete").addEventListener("blur", disarm);
    window.addEventListener("beforeunload", (e) => {
      if (state.saving || !state.original) return;
      if (E.isDirty(readFields(), state.original)) {
        e.preventDefault();
        e.returnValue = "";
      }
    });
  }

  if (!E || !L || !P || !View) say("The page's scripts did not load.");
  else init();
})();
