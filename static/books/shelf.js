/* Books: the shelf component (spec BK1 §1.1a, board C3; views from boards C1 and C2).
 *
 * A shelf is a container with data-shelf and a JSON script of books:
 *   { id, title, author, status, color, ink, w, h, lean, rare, url }
 * The spines are drawn from that data: colour, proportions and title are
 * the book's own. The person swipes along the shelf (native scrolling),
 * taps a spine to lift it into the light, and a label below shows the book.
 * Keyboard: the spines are buttons; arrows move along the shelf inside the
 * row, Enter or Space lifts. No global key handlers.
 *
 * data-shelf-view: "lamp" (one long shelf), "bookcase" (two shelves, tap
 * pulls out), "living" (drag to arrange, tap to pull).
 */
(function () {
  "use strict";

  var STATUS_KEYS = { private: "status.private", public: "status.public", lend: "status.lend",
                      exchange: "status.exchange", sell: "status.sell" };

  function el(tag, cls, attrs) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (attrs) Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    return node;
  }

  function readJSON(root) {
    var id = root.getAttribute("data-shelf-source");
    var script = id ? document.getElementById(id) : root.querySelector("script[type='application/json']");
    if (!script) return [];
    try { return JSON.parse(script.textContent || "[]"); } catch (e) { return []; }
  }

  function strings(root) {
    var id = root.getAttribute("data-shelf-strings");
    var script = id ? document.getElementById(id) : null;
    if (!script) return {};
    try { return JSON.parse(script.textContent || "{}"); } catch (e) { return {}; }
  }

  function Shelf(root) {
    this.root = root;
    this.books = readJSON(root);
    this.t = strings(root);
    this.view = root.getAttribute("data-shelf-view") || "lamp";
    this.label = document.getElementById(root.getAttribute("data-shelf-label") || "") || root.querySelector("[data-shelf-label]");
    this.lifted = root.getAttribute("data-shelf-lifted") || null;
    this.order = this.books.map(function (b) { return String(b.id); });
    this.render();
  }

  Shelf.prototype.byId = function (id) {
    for (var i = 0; i < this.books.length; i++) if (String(this.books[i].id) === String(id)) return this.books[i];
    return null;
  };

  Shelf.prototype.layout = function (ids, startX) {
    var x = startX, map = {}, self = this;
    ids.forEach(function (id) {
      var b = self.byId(id);
      var w = Math.max(b.w || 28, 24), h = b.h || 170, lean = b.lean || 0;
      map[id] = { left: x, w: w };
      x += w + 3 + (lean ? Math.round(h * Math.sin(Math.abs(lean) * Math.PI / 180)) : 0);
    });
    return { map: map, width: x + 16 };
  };

  Shelf.prototype.spine = function (b, pos) {
    var btn = el("button", "bk-spine" + (b.rare ? " bk-spine--rare" : ""), {
      type: "button", "data-book": b.id, "aria-pressed": "false",
      "aria-label": (b.title || "") + (b.author ? ", " + b.author : "")
    });
    var w = Math.max(b.w || 28, 24), h = b.h || 170, lean = b.lean || 0;
    btn.style.setProperty("--spine-left", pos.left + "px");
    btn.style.setProperty("--spine-w", w + "px");
    btn.style.setProperty("--spine-h", h + "px");
    btn.style.setProperty("--spine-bg", b.color || "#3A3128");
    btn.style.setProperty("--spine-ink", b.ink || "#EFE6D2");
    btn.style.setProperty("--spine-lean", lean + "deg");
    btn.style.setProperty("--spine-origin", lean > 0 ? "bottom left" : (lean < 0 ? "bottom right" : "bottom center"));
    btn.style.setProperty("--spine-font", (w >= 32 ? 15 : 13) + "px");
    btn.appendChild(el("span", "bk-spine-band"));
    var title = el("span", "bk-spine-title"); title.textContent = b.title || ""; btn.appendChild(title);
    var author = el("span", "bk-spine-author"); author.textContent = b.author || ""; btn.appendChild(author);
    return btn;
  };

  Shelf.prototype.rowFor = function (ids, extraClass) {
    var self = this;
    var row = el("div", "bk-shelf-row" + (extraClass ? " " + extraClass : ""));
    var lay = this.layout(ids, 16);
    row.style.width = lay.width + "px";
    ids.forEach(function (id) { row.appendChild(self.spine(self.byId(id), lay.map[id])); });
    row.addEventListener("click", function (e) {
      var btn = e.target.closest(".bk-spine");
      if (!btn || row._dragMoved) return;
      self.toggle(btn.getAttribute("data-book"));
    });
    row.addEventListener("keydown", function (e) {
      var btn = e.target.closest(".bk-spine");
      if (!btn) return;
      var spines = Array.prototype.slice.call(row.querySelectorAll(".bk-spine"));
      var i = spines.indexOf(btn);
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        var next = spines[e.key === "ArrowRight" ? i + 1 : i - 1];
        if (next) { next.focus(); e.preventDefault(); }
      }
    });
    if (this.view === "living") this.makeDraggable(row, ids);
    return row;
  };

  Shelf.prototype.render = function () {
    var self = this;
    this.root.innerHTML = "";
    this.root.classList.toggle("bk-shelf--living", this.view === "living");
    if (!this.books.length) return;
    if (this.view === "bookcase") {
      var half = Math.ceil(this.order.length / 2);
      var kase = el("div", "bk-case");
      [this.order.slice(0, half), this.order.slice(half)].forEach(function (ids, i) {
        var back = el("div", "bk-case-back");
        var scroll = el("div", "bk-shelf-scroll");
        scroll.appendChild(self.rowFor(ids));
        back.appendChild(scroll);
        kase.appendChild(back);
        var board = el("div", "bk-case-board");
        var plate = el("span", "bk-case-plate");
        plate.textContent = self.root.getAttribute(i === 0 ? "data-shelf-plate-1" : "data-shelf-plate-2") || "";
        board.appendChild(plate);
        kase.appendChild(board);
      });
      this.root.appendChild(kase);
    } else {
      var scroll1 = el("div", "bk-shelf-scroll");
      scroll1.setAttribute("aria-label", this.root.getAttribute("data-shelf-aria") || "");
      var row = this.rowFor(this.order);
      scroll1.appendChild(row);
      var board1 = el("div", "bk-shelf-board");
      board1.style.minWidth = row.style.width;
      scroll1.appendChild(board1);
      this.root.appendChild(scroll1);
    }
    if (this.lifted) this.toggle(this.lifted, true);
  };

  Shelf.prototype.toggle = function (id, force) {
    var self = this;
    var already = this.liftedId === String(id);
    this.root.querySelectorAll(".bk-spine.is-lifted").forEach(function (s) {
      s.classList.remove("is-lifted"); s.setAttribute("aria-pressed", "false");
    });
    if (already && !force) { this.liftedId = null; this.showLabel(null); return; }
    var btn = this.root.querySelector('.bk-spine[data-book="' + id + '"]');
    if (!btn) return;
    btn.classList.add("is-lifted"); btn.setAttribute("aria-pressed", "true");
    this.liftedId = String(id);
    if (!force) btn.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    this.showLabel(this.byId(id));
    this.root.dispatchEvent(new CustomEvent("bkshelf:lift", { detail: { id: id, book: self.byId(id) } }));
  };

  Shelf.prototype.showLabel = function (b) {
    if (!this.label) return;
    if (!b) { this.label.hidden = true; return; }
    this.label.hidden = false;
    var kind = this.label.querySelector("[data-label-kind]");
    var title = this.label.querySelector("[data-label-title]");
    var author = this.label.querySelector("[data-label-author]");
    var status = this.label.querySelector("[data-label-status]");
    var link = this.label.querySelector("[data-label-link]");
    if (kind) kind.textContent = b.rare ? (this.t["shelf.rare"] || "") : (this.t["shelf.from_yours"] || "");
    if (title) title.textContent = b.title || "";
    if (author) author.textContent = b.author || "";
    if (status) status.textContent = b.status_text || this.t[STATUS_KEYS[b.status]] || "";
    if (link) { if (b.url) { link.hidden = false; link.setAttribute("href", b.url); } else { link.hidden = true; } }
  };

  // Living shelf: pointer-drag a spine sideways; the others make room.
  Shelf.prototype.makeDraggable = function (row, ids) {
    var self = this, drag = null;
    row.addEventListener("pointerdown", function (e) {
      var btn = e.target.closest(".bk-spine");
      if (!btn || e.button !== 0) return;
      drag = { btn: btn, id: btn.getAttribute("data-book"), sx: e.clientX, moved: false,
               start: parseFloat(btn.style.getPropertyValue("--spine-left")) || 0 };
      row._dragMoved = false;
      try { btn.setPointerCapture(e.pointerId); } catch (err) {}
    });
    row.addEventListener("pointermove", function (e) {
      if (!drag) return;
      var dx = e.clientX - drag.sx;
      if (!drag.moved && Math.abs(dx) > 4) { drag.moved = true; drag.btn.classList.add("is-dragging"); }
      if (!drag.moved) return;
      drag.btn.style.setProperty("--spine-left", (drag.start + dx) + "px");
    });
    function finish(e) {
      if (!drag) return;
      var d = drag; drag = null;
      d.btn.classList.remove("is-dragging");
      if (!d.moved) return;
      row._dragMoved = true;
      setTimeout(function () { row._dragMoved = false; }, 0);
      var lay = self.layout(ids, 16);
      var center = (parseFloat(d.btn.style.getPropertyValue("--spine-left")) || 0) + lay.map[d.id].w / 2;
      var rest = ids.filter(function (k) { return k !== d.id; });
      var idx = rest.filter(function (k) { return lay.map[k].left + lay.map[k].w / 2 < center; }).length;
      rest.splice(idx, 0, d.id);
      ids.splice.apply(ids, [0, ids.length].concat(rest));
      self.order = ids.slice();
      var relaid = self.layout(ids, 16);
      ids.forEach(function (k) {
        var s = row.querySelector('.bk-spine[data-book="' + k + '"]');
        if (s) s.style.setProperty("--spine-left", relaid.map[k].left + "px");
      });
      self.root.dispatchEvent(new CustomEvent("bkshelf:reorder", { detail: { order: ids.slice() } }));
    }
    row.addEventListener("pointerup", finish);
    row.addEventListener("pointercancel", finish);
  };

  function boot() {
    document.querySelectorAll("[data-shelf]").forEach(function (root) {
      if (!root._bkShelf) root._bkShelf = new Shelf(root);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
  window.BkShelf = Shelf;
})();
