// improv: the Library screen. Browser glue only: read the filters, call ImprovLibrary, draw cards.
// Every rule is in library.js, which is tested under Node. Only text is ever put on the page.
(function () {
  "use strict";
  const L = window.ImprovLibrary;
  const $ = (id) => document.getElementById(id);
  const host = $("library");

  const state = { all: [], qualities: [], facets: null, described: new Map() };

  const say = (text) => ($("lib-status").textContent = text);
  const cap = (word) => word.charAt(0).toUpperCase() + word.slice(1);

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function fillSelect(select, firstLabel, items, current) {
    select.textContent = "";
    const all = make("option", "", firstLabel);
    all.value = "";
    select.appendChild(all);
    for (const [value, label] of items) {
      const option = make("option", "", label);
      option.value = String(value);
      select.appendChild(option);
    }
    select.value = current;
    if (select.value !== current) select.value = "";
  }

  function fillFilters(filters) {
    const f = state.facets;
    fillSelect($("f-genre"), "Any genre", f.genres.map((g) => [g.value, `${cap(g.value)} (${g.count})`]), filters.genre);
    fillSelect($("f-tag"), "Any tag", f.tags.map((t) => [t.value, `${t.value} (${t.count})`]), filters.tag);
    fillSelect(
      $("f-difficulty"),
      "Any level",
      f.difficulties.map((d) => [d.value, `${L.difficultyName(d.value)} (${d.count})`]),
      filters.difficulty
    );
    $("f-q").value = filters.q;
    $("f-sort").value = filters.sort;
    $("f-mine").checked = filters.mine;
  }

  function readFilters() {
    return {
      genre: $("f-genre").value,
      tag: $("f-tag").value,
      difficulty: $("f-difficulty").value,
      q: $("f-q").value,
      sort: $("f-sort").value,
      mine: $("f-mine").checked,
    };
  }

  function descriptionOf(p) {
    if (!state.described.has(p.id)) state.described.set(p.id, L.describe(p, state.qualities));
    return state.described.get(p.id);
  }

  function card(p) {
    const d = descriptionOf(p);
    const el = make("article", "im-card");
    el.dataset.slug = p.slug;

    const head = make("div", "im-card-head");
    head.appendChild(make("h2", "im-card-title", p.title));
    head.appendChild(make("span", "im-level im-level-" + p.difficulty, L.difficultyName(p.difficulty)));
    el.appendChild(head);

    const meta = [cap(p.genre), p.home_key, `${p.default_tempo} bpm`, p.time_signature];
    if (d.ok) meta.push(d.bars === 1 ? "1 bar" : `${d.bars} bars`);
    el.appendChild(make("p", "im-card-meta", meta.join("  ·  ")));

    if (d.ok) el.appendChild(make("p", "im-card-preview im-mono", d.preview));
    else el.appendChild(make("p", "im-error", d.error));
    if (p.description) el.appendChild(make("p", "im-card-text", p.description));

    if (p.tags && p.tags.length) {
      const chips = make("div", "im-chips");
      for (const tag of p.tags) chips.appendChild(make("span", "im-chip", tag));
      el.appendChild(chips);
    }

    const actions = make("div", "im-card-actions");
    const play = make("a", "im-btn im-btn-link", "Play");
    play.href = host.dataset.playUrl + "?p=" + encodeURIComponent(p.slug);
    const edit = make("a", "im-btn im-btn-link im-btn-quiet", p.is_mine ? "Edit" : "Make my copy");
    edit.href = host.dataset.editorUrl + "?p=" + encodeURIComponent(p.slug);
    actions.append(play, edit);
    el.appendChild(actions);
    return el;
  }

  function render() {
    const filters = readFilters();
    const shown = L.sortProgressions(L.filterProgressions(state.all, filters), filters.sort);
    const list = $("lib-list");
    list.textContent = "";
    for (const p of shown) list.appendChild(card(p));
    $("lib-empty").hidden = shown.length > 0;
    $("lib-count").textContent = shown.length === state.all.length
      ? `${shown.length} progressions. `
      : `${shown.length} of ${state.all.length} progressions. `;
    const query = L.queryFromFilters(filters);
    window.history.replaceState(null, "", window.location.pathname + query);
  }

  function clearFilters() {
    fillFilters(L.filtersFromQuery(""));
    render();
  }

  async function init() {
    try {
      const [progressions, qualities] = await Promise.all([
        getJson(host.dataset.apiProgressions),
        getJson(host.dataset.apiQualities),
      ]);
      state.all = progressions;
      state.qualities = qualities;
    } catch (e) {
      say("The library could not be loaded. " + e.message);
      return;
    }
    state.facets = L.facets(state.all);
    fillFilters(L.filtersFromQuery(window.location.search));
    for (const id of ["f-genre", "f-tag", "f-difficulty", "f-sort", "f-mine"]) $(id).addEventListener("change", render);
    $("f-q").addEventListener("input", render);
    $("f-clear").addEventListener("click", clearFilters);
    render();
    say(state.all.length ? "Ready." : "The library is empty. Run seed_improv_library.");
  }

  if (!L) say("The page's scripts did not load.");
  else init();
})();
