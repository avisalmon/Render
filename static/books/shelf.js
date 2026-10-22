/* Books: the shelf component (spec BK1 §1.1a, board C3; views from boards C1 and C2).
 *
 * A shelf is a container with data-shelf and a JSON script of books:
 *   { id, title, author, status, color, ink, w, h, lean, rare, url }
 * The spines are drawn from that data: colour, proportions and title are
 * the book's own. Swipe along the shelf (native scrolling), tap a spine to
 * lift it into the light; a label below shows the book. Keyboard: the
 * spines are buttons, arrows walk the shelf, Enter or Space lifts.
 *
 * Physics (Avi, 2026-10-20: "a physical feeling of moving the books, as if
 * they lean and move in a natural way"): every spine has three springs,
 * its place along the shelf, its tilt and its lift. A book picked up hangs
 * from where it is held and swings with the hand; the others slide to make
 * room, tipping a little as they move; the book beside the gap leans into
 * it; a dropped book falls into its place and settles with a small wobble.
 * In the living view a book is picked up at once; in the others by a long
 * press, so a plain swipe still scrolls the shelf. Reduced motion: no
 * springs, things simply move.
 *
 * Titles too long for a spine break onto two lines (and shrink a little if
 * they must).
 *
 * data-shelf-view: "lamp" (one long shelf), "bookcase" (two shelves),
 * "living" (drag to arrange at once). Events: bkshelf:lift, bkshelf:reorder.
 */
(function () {
  "use strict";

  var STATUS_KEYS = { private: "status.private", public: "status.public", lend: "status.lend",
                      exchange: "status.exchange", sell: "status.sell" };
  var GAP = 3;                 // px between standing books
  var LIFT = -14;              // px a tapped book rises
  var HOLD_LIFT = -18;         // px a held book rises
  var ZOOM_ROOM = 150;         // px the row grows upward while a tapped book is enlarged (Avi, 2026-10-22)
  var ZOOM_MAX = 2.2;
  var LONG_PRESS = 320;        // ms to pick a book up outside the living view
  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function rad(deg) { return deg * Math.PI / 180; }

  // ---- one spring per quantity -------------------------------------------------------------
  // Semi-implicit Euler; `k` stiffness, `z` damping ratio (below 1 overshoots a little).
  function step(p, v, target, k, z, dt) {
    var c = 2 * Math.sqrt(k) * z;
    v += (k * (target - p) - c * v) * dt;
    p += v * dt;
    return [p, v];
  }

  function Shelf(root) {
    this.root = root;
    this.books = readJSON(root);
    this.t = strings(root);
    this.view = root.getAttribute("data-shelf-view") || "lamp";
    this.label = document.getElementById(root.getAttribute("data-shelf-label") || "") || root.querySelector("[data-shelf-label]");
    this.lifted = root.getAttribute("data-shelf-lifted") || null;
    this.order = this.books.map(function (b) { return String(b.id); });
    this.rows = [];
    this.render();
  }

  Shelf.prototype.byId = function (id) {
    for (var i = 0; i < this.books.length; i++) if (String(this.books[i].id) === String(id)) return this.books[i];
    return null;
  };

  function dims(b, drawn) {
    // A drawn spine is at least 24px (its title, a thumb). A photographed one keeps the
    // book's true width; its tap area is widened around it in CSS (.bk-spine--photo::before).
    // When the shelf is set to drawn spines, a photographed book needs room for its title too.
    var real = b.photo && !drawn;
    return { w: real ? Math.max(b.w || 28, 8) : Math.max(b.w || 28, 24), h: b.h || 170, lean: b.lean || 0 };
  }

  // Where every book of a row stands at rest, with an optional gap (a book
  // being carried) at `gapAt` of width `gapW`. A book leaning right pivots on
  // its bottom-right corner and rests its top on the next one, so the next
  // one stands h·sin(lean) further on; a book leaning left, the mirror.
  Shelf.prototype.layout = function (ids, startX, gapAt, gapW) {
    var x = startX, map = {}, self = this;
    ids.forEach(function (id, i) {
      if (gapAt === i) x += gapW + GAP;
      var d = dims(self.byId(id), self.root.classList.contains("is-drawn"));
      // A book at either end of the row has nothing on its outer side: it
      // leans inward, against its neighbour, or it would fall.
      if (i === ids.length - 1 && d.lean > 0 && ids.length > 1) d.lean = -d.lean;
      if (i === 0 && d.lean < 0 && ids.length > 1) d.lean = -d.lean;
      if (d.lean < 0) x += Math.round(d.h * Math.sin(rad(-d.lean)));
      map[id] = { left: x, w: d.w, h: d.h, lean: d.lean };
      x += d.w + GAP + (d.lean > 0 ? Math.round(d.h * Math.sin(rad(d.lean))) : 0);
    });
    if (gapAt === ids.length) x += gapW + GAP;
    return { map: map, width: x + 16 };
  };

  // ---- spines -------------------------------------------------------------------------------

  Shelf.prototype.spine = function (b) {
    var btn = el("button", "bk-spine" + (b.rare ? " bk-spine--rare" : "") + (b.photo ? " bk-spine--photo" : ""), {
      type: "button", "data-book": b.id, "aria-pressed": "false",
      "aria-label": (b.title || "") + (b.author ? ", " + b.author : "")
    });
    var d = dims(b, this.root.classList.contains("is-drawn"));
    btn.style.setProperty("--spine-w", d.w + "px");
    btn.style.setProperty("--spine-h", d.h + "px");
    btn.style.setProperty("--spine-bg", b.color || "#3A3128");
    btn.style.setProperty("--spine-ink", b.ink || "#EFE6D2");
    btn.style.setProperty("--spine-font", (d.w >= 32 ? 15 : 13) + "px");
    // The real book, as photographed (Avi, 2026-10-22); its title stays for screen readers and the card.
    btn.appendChild(el("span", "bk-spine-band"));
    var title = el("span", "bk-spine-title"); title.textContent = b.title || ""; btn.appendChild(title);
    var author = el("span", "bk-spine-author"); author.textContent = b.author || ""; btn.appendChild(author);
    if (b.photo) {
      var url = String(b.photo).replace(/"/g, "");
      btn.style.setProperty("--spine-img", 'url("' + url + '")');
      // No picture after all (not cut yet, or it failed): the book shows its title instead.
      var probe = new Image();
      probe.onerror = function () {
        btn.classList.remove("bk-spine--photo");
        btn.style.removeProperty("--spine-img");
        if (btn.offsetWidth < 24) btn.style.setProperty("--spine-w", "24px");
        fitTitle(title, Math.max(btn.offsetWidth, 24));
      };
      probe.src = url;
    }
    return btn;
  };

  // A title that does not fit breaks onto two lines, then shrinks to fit.
  function fitTitle(span, w) {
    if (!span.textContent) return;
    if (span.scrollHeight <= span.clientHeight + 1) return;
    span.classList.add("is-two");
    var size = Math.min(parseFloat(getComputedStyle(span).fontSize) || 13, Math.floor((w - 4) / 2.2));
    span.style.fontSize = size + "px";
    while (span.scrollHeight > span.clientHeight + 1 && size > 9) {
      size -= 1;
      span.style.fontSize = size + "px";
    }
  }

  // ---- a row and its physics ------------------------------------------------------------------

  function Row(shelf, ids, extraClass) {
    var self = this;
    this.shelf = shelf;
    this.ids = ids;
    this.el = el("div", "bk-shelf-row" + (extraClass ? " " + extraClass : ""));
    this.state = {};
    this.running = false;
    var lay = shelf.layout(ids, 16);
    this.el.style.width = lay.width + "px";
    ids.forEach(function (id) {
      var b = shelf.byId(id);
      var btn = shelf.spine(b);
      var p = lay.map[id];
      self.el.appendChild(btn);
      self.state[id] = { el: btn, w: p.w, h: p.h, rest: p.lean,
                         x: p.left, vx: 0, tx: p.left, a: p.lean, va: 0, ta: p.lean, y: 0, vy: 0, ty: 0,
                         z: 1, vz: 0, tz: 1, origin: "" };
      btn.style.setProperty("--spine-left", p.left + "px");
    });
    this.draw();
  }

  Row.prototype.fit = function () {
    var self = this;
    this.ids.forEach(function (id) {
      var s = self.state[id];
      // A photographed spine shows no text, unless the shelf is set to drawn spines.
      if (!s.el.classList.contains("bk-spine--photo") || self.shelf.root.classList.contains("is-drawn")) {
        fitTitle(s.el.querySelector(".bk-spine-title"), s.w);
      }
    });
  };

  // Pivot on the corner the book leans toward; a held book hangs from the top.
  function originFor(s, held) {
    if (held) return "50% 12%";
    if (s.a > 0.2) return "100% 100%";
    if (s.a < -0.2) return "0% 100%";
    return "50% 100%";
  }

  Row.prototype.draw = function () {
    var self = this;
    this.ids.forEach(function (id) {
      var s = self.state[id];
      // A sliding book tips a little with its speed, as a real one would.
      var tip = s.held ? 0 : clamp(s.vx * 0.012, -5, 5);
      var o = originFor(s, s.held);
      if (o !== s.origin) { s.el.style.transformOrigin = o; s.origin = o; }
      s.el.style.transform = "translate3d(" + s.x.toFixed(2) + "px," + s.y.toFixed(2) + "px,0) rotate(" +
        (s.a + tip).toFixed(2) + "deg)" + (Math.abs(s.z - 1) > 0.001 ? " scale(" + s.z.toFixed(3) + ")" : "");
    });
  };

  Row.prototype.kick = function () {
    if (REDUCED) { this.snap(); return; }
    if (this.running) return;
    this.running = true;
    var self = this, last = performance.now();
    function frame(now) {
      var dt = Math.min(0.033, (now - last) / 1000); last = now;
      var busy = false;
      self.ids.forEach(function (id) {
        var s = self.state[id];
        if (!s.held) {
          var r = step(s.x, s.vx, s.tx, 170, 0.62, dt); s.x = r[0]; s.vx = r[1];
          r = step(s.y, s.vy, s.ty, 240, 0.45, dt); s.y = r[0]; s.vy = r[1];
        }
        var q = step(s.a, s.va, s.ta, s.held ? 90 : 210, s.held ? 0.35 : 0.42, dt); s.a = q[0]; s.va = q[1];
        var zq = step(s.z, s.vz, s.tz, 180, 0.62, dt); s.z = zq[0]; s.vz = zq[1];
        if (Math.abs(s.tx - s.x) > 0.3 || Math.abs(s.vx) > 2 || Math.abs(s.ta - s.a) > 0.15 || Math.abs(s.va) > 1 ||
            Math.abs(s.ty - s.y) > 0.3 || Math.abs(s.vy) > 2 || Math.abs(s.tz - s.z) > 0.002 || Math.abs(s.vz) > 0.01 ||
            s.held) busy = true;
      });
      self.draw();
      if (busy) requestAnimationFrame(frame); else { self.running = false; self.settle(); }
    }
    requestAnimationFrame(frame);
  };

  Row.prototype.snap = function () {
    var self = this;
    this.ids.forEach(function (id) {
      var s = self.state[id];
      if (!s.held) { s.x = s.tx; s.y = s.ty; }
      s.a = s.ta; s.z = s.tz; s.vx = s.vy = s.va = s.vz = 0;
    });
    this.draw();
  };

  Row.prototype.settle = function () {
    var self = this;
    this.ids.forEach(function (id) {
      var s = self.state[id];
      s.x = s.tx; s.y = s.ty; s.a = s.ta; s.z = s.tz; s.vx = s.vy = s.va = s.vz = 0;
    });
    this.draw();
  };

  // Targets for the books at rest, or around a gap where a book is carried.
  Row.prototype.retarget = function (gapAt, carried) {
    var self = this, shelf = this.shelf;
    var ids = carried ? this.ids.filter(function (k) { return k !== carried; }) : this.ids;
    var gapW = carried ? this.state[carried].w : 0;
    var lay = shelf.layout(ids, 16, carried ? gapAt : null, gapW);
    ids.forEach(function (id) {
      var s = self.state[id], p = lay.map[id];
      s.tx = p.left;
      s.ta = s.rest;
      if (!s.lifted) s.ty = 0;
      s.el.style.setProperty("--spine-left", p.left + "px");
    });
    // The book beside an open gap leans into it (the taller one; a gap is
    // wide enough for one book to lean, not two).
    if (carried && gapAt !== null) {
      var left = ids[gapAt - 1], right = ids[gapAt];
      var cand = [left && { id: left, dir: 1 }, right && { id: right, dir: -1 }].filter(Boolean);
      cand.sort(function (p, q) { return self.state[q.id].h - self.state[p.id].h; });
      var c = cand[0];
      if (c) {
        var s = self.state[c.id];
        var max = Math.asin(clamp((gapW - 2) / s.h, 0, 1)) * 180 / Math.PI;
        s.ta = c.dir * Math.min(9, max);  // pivots on its own bottom corner
      }
    }
    this.el.style.width = Math.max(lay.width, parseFloat(this.el.style.width) || 0) + "px";
    this.kick();
  };

  // A tapped book rises, stands straight and grows to fill the room the row
  // makes for it above the shelf; tapped again, or another tapped, it shrinks back.
  Row.prototype.liftOnly = function (id) {
    var self = this;
    var base = this.baseHeight || (this.baseHeight = this.el.offsetHeight || 214);
    this.el.classList.toggle("is-zoomed", id !== null);
    this.el.style.setProperty("--zoom-room", ZOOM_ROOM + "px");
    this.ids.forEach(function (k) {
      var s = self.state[k];
      s.lifted = k === id;
      s.ty = s.lifted ? LIFT : 0;
      s.ta = s.lifted ? 0 : s.rest;
      s.tz = s.lifted ? Math.max(1.3, Math.min(ZOOM_MAX, (base + ZOOM_ROOM + LIFT - 14) / s.h)) : 1;
    });
    this.kick();
  };

  // Where would the carried book go, from its centre?
  Row.prototype.slotFor = function (carried, centre) {
    var self = this;
    var rest = this.ids.filter(function (k) { return k !== carried; });
    return rest.filter(function (k) { var s = self.state[k]; return s.tx + s.w / 2 < centre; }).length;
  };

  // ---- dragging ------------------------------------------------------------------------------

  Row.prototype.enableDrag = function (immediate) {
    var self = this, drag = null, pending = null;
    var scroller = function () { return self.el.closest(".bk-shelf-scroll"); };

    function begin(e, btn) {
      var id = btn.getAttribute("data-book");
      var s = self.state[id];
      drag = { id: id, btn: btn, sx: e.clientX, start: s.x, lastX: e.clientX, lastT: performance.now(),
               slot: self.ids.indexOf(id), moved: false };
      s.held = true; s.ty = HOLD_LIFT; s.y = HOLD_LIFT; s.lifted = false;
      btn.classList.add("is-dragging");
      self.el.classList.add("is-arranging");
      try { btn.setPointerCapture(e.pointerId); } catch (err) {}
      if (navigator.vibrate) { try { navigator.vibrate(12); } catch (err) {} }
      self.retarget(drag.slot, id);
    }

    // A mouse has no swipe (Avi, 2026-10-22): dragging pans the shelf, with a
    // glide after release, and holding still picks a book up, as on a phone.
    var pan = null, glide = 0;
    function startPan(e) {
      var sc = scroller();
      if (!sc) return;
      cancelAnimationFrame(glide);
      pan = { sc: sc, x: e.clientX, left: sc.scrollLeft, lastX: e.clientX, lastT: performance.now(), v: 0 };
      self.el.classList.add("is-panning");
    }
    function endPan() {
      if (!pan) return;
      var p = pan; pan = null;
      self.el.classList.remove("is-panning");
      self.el._dragMoved = true;
      setTimeout(function () { self.el._dragMoved = false; }, 0);
      var v = p.v;
      var step = function () {
        if (Math.abs(v) < 0.3) return;
        p.sc.scrollLeft -= v;
        v *= 0.92;
        glide = requestAnimationFrame(step);
      };
      glide = requestAnimationFrame(step);
    }

    self.el.addEventListener("pointerdown", function (e) {
      var btn = e.target.closest(".bk-spine");
      var mouse = e.pointerType === "mouse";
      if (mouse && e.button !== 0) return;
      self.el._dragMoved = false;
      if (mouse) e.preventDefault();  // no text selection while panning
      if (!btn) { if (mouse) { startPan(e); pending = { pan: true, x: e.clientX, y: e.clientY }; } return; }
      if (immediate && !mouse) { begin(e, btn); return; }
      pending = { btn: btn, x: e.clientX, y: e.clientY, e: e, mouse: mouse,
                  timer: setTimeout(function () { var p = pending; pending = null; if (p) begin(p.e, p.btn); }, LONG_PRESS) };
    });

    self.el.addEventListener("pointermove", function (e) {
      if (pending) {
        if (Math.abs(e.clientX - pending.x) > 8 || Math.abs(e.clientY - pending.y) > 8) {
          clearTimeout(pending.timer);
          var wasMouse = pending.mouse || pending.pan;
          pending = null;  // a swipe: the shelf scrolls (by itself under a finger, by us under a mouse)
          if (wasMouse && !pan) startPan(e);
        }
        if (!pan) return;
      }
      if (pan) {
        var now = performance.now();
        pan.v = 0.8 * ((e.clientX - pan.lastX) / Math.max(1, now - pan.lastT) * 16) + 0.2 * pan.v;
        pan.lastX = e.clientX; pan.lastT = now;
        pan.sc.scrollLeft = pan.left - (e.clientX - pan.x);
        return;
      }
      if (!drag) return;
      var dx = e.clientX - drag.sx;
      if (!drag.moved && Math.abs(dx) > 3) drag.moved = true;
      var s = self.state[drag.id];
      var now = performance.now();
      var v = (e.clientX - drag.lastX) / Math.max(1, now - drag.lastT) * 1000;  // px/s
      drag.lastX = e.clientX; drag.lastT = now;
      s.x = drag.start + dx;
      // Held at the top, it swings with the hand: the bottom trails the motion.
      s.ta = clamp(v * 0.018, -16, 16);
      var slot = self.slotFor(drag.id, s.x + s.w / 2);
      if (slot !== drag.slot) { drag.slot = slot; self.retarget(slot, drag.id); } else { self.kick(); }
      // Near an edge of the scroller, the shelf scrolls under the held book.
      var sc = scroller();
      if (sc) {
        var r = sc.getBoundingClientRect();
        if (e.clientX < r.left + 40) sc.scrollLeft -= 12;
        else if (e.clientX > r.right - 40) sc.scrollLeft += 12;
      }
    });

    // Holding a book must not scroll the page or the shelf (touch).
    self.el.addEventListener("touchmove", function (e) { if (drag) e.preventDefault(); }, { passive: false });

    function finish() {
      if (pending) { clearTimeout(pending.timer); pending = null; }
      if (pan) { endPan(); return; }
      if (!drag) return;
      var d = drag; drag = null;
      var s = self.state[d.id];
      d.btn.classList.remove("is-dragging");
      self.el.classList.remove("is-arranging");
      if (!d.moved) { s.held = false; s.ty = 0; s.ta = s.rest; self.retarget(null, null); return; }
      self.el._dragMoved = true;
      setTimeout(function () { self.el._dragMoved = false; }, 0);
      var rest = self.ids.filter(function (k) { return k !== d.id; });
      rest.splice(d.slot, 0, d.id);
      self.ids.splice.apply(self.ids, [0, self.ids.length].concat(rest));
      s.held = false;
      s.ty = 0;
      s.va += clamp(s.a * -4, -120, 120);  // lands and wobbles
      self.retarget(null, null);
      self.shelf.reordered();
    }
    self.el.addEventListener("pointerup", finish);
    self.el.addEventListener("pointercancel", finish);
    window.addEventListener("pointerup", function () { if (pan) endPan(); });
    // The mouse wheel slides the shelf sideways while there is more of it to see.
    self.el.addEventListener("wheel", function (e) {
      var sc = scroller();
      if (!sc || sc.scrollWidth <= sc.clientWidth + 1 || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      var before = sc.scrollLeft;
      sc.scrollLeft += e.deltaY;
      if (sc.scrollLeft !== before) e.preventDefault();
    }, { passive: false });
  };

  // ---- the shelf ------------------------------------------------------------------------------

  Shelf.prototype.rowFor = function (ids, extraClass) {
    var self = this;
    var row = new Row(this, ids, extraClass);
    this.rows.push(row);
    row.el.addEventListener("click", function (e) {
      var btn = e.target.closest(".bk-spine");
      if (!btn || row.el._dragMoved) return;
      self.toggle(btn.getAttribute("data-book"));
    });
    row.el.addEventListener("keydown", function (e) {
      var btn = e.target.closest(".bk-spine");
      if (!btn) return;
      var spines = row.ids.map(function (k) { return row.state[k].el; });
      var i = spines.indexOf(btn);
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        var next = spines[e.key === "ArrowRight" ? i + 1 : i - 1];
        if (next) { next.focus(); e.preventDefault(); }
      }
    });
    row.enableDrag(this.view === "living");
    return row;
  };

  Shelf.prototype.reordered = function () {
    var order = [];
    this.rows.forEach(function (r) { order = order.concat(r.ids); });
    this.order = order;
    this.root.dispatchEvent(new CustomEvent("bkshelf:reorder", { detail: { order: order.slice() } }));
  };

  Shelf.prototype.render = function () {
    var self = this;
    this.root.innerHTML = "";
    this.rows = [];
    this.root.classList.toggle("bk-shelf--living", this.view === "living");
    if (!this.books.length) return;
    if (this.view === "bookcase") {
      var half = Math.ceil(this.order.length / 2);
      var kase = el("div", "bk-case");
      [this.order.slice(0, half), this.order.slice(half)].forEach(function (ids, i) {
        var back = el("div", "bk-case-back");
        var scroll = el("div", "bk-shelf-scroll");
        scroll.appendChild(self.rowFor(ids).el);
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
      var row = this.rowFor(this.order.slice());
      scroll1.appendChild(row.el);
      var board1 = el("div", "bk-shelf-board");
      board1.style.minWidth = row.el.style.width;
      scroll1.appendChild(board1);
      this.root.appendChild(scroll1);
    }
    this.rows.forEach(function (r) { r.fit(); });
    if (this.lifted) this.toggle(this.lifted, true);
  };

  Shelf.prototype.rowOf = function (id) {
    for (var i = 0; i < this.rows.length; i++) if (this.rows[i].state[String(id)]) return this.rows[i];
    return null;
  };

  Shelf.prototype.toggle = function (id, force) {
    var self = this;
    var already = this.liftedId === String(id);
    this.root.querySelectorAll(".bk-spine.is-lifted").forEach(function (s) {
      s.classList.remove("is-lifted"); s.setAttribute("aria-pressed", "false");
    });
    this.rows.forEach(function (r) { r.liftOnly(null); });
    if (already && !force) {
      this.liftedId = null; this.showLabel(null);
      var back = this.root.querySelector('.bk-spine[data-book="' + id + '"]');
      if (back) setTimeout(function () { back.style.zIndex = ""; }, 450);
      return;
    }
    var btn = this.root.querySelector('.bk-spine[data-book="' + id + '"]');
    if (!btn) return;
    btn.classList.add("is-lifted"); btn.setAttribute("aria-pressed", "true");
    var row = this.rowOf(id);
    if (row) row.liftOnly(String(id));
    this.liftedId = String(id);
    if (!force) btn.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    btn.style.zIndex = "6";
    this.root.querySelectorAll(".bk-spine").forEach(function (s) { if (s !== btn) s.style.zIndex = ""; });
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

  function boot() {
    document.querySelectorAll("[data-shelf]").forEach(function (root) {
      if (!root._bkShelf) root._bkShelf = new Shelf(root);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
  window.BkShelf = Shelf;
  // The looks switched from outside (the arrows beside the shelf): fit the titles again.
  // The books take their new widths and slide to their places (the springs do the rest).
  Shelf.prototype.refit = function () {
    var shelf = this, drawn = this.root.classList.contains("is-drawn");
    this.rows.forEach(function (r) {
      r.ids.forEach(function (id) {
        var s = r.state[id], d = dims(shelf.byId(id), drawn);
        s.w = d.w;
        s.el.style.setProperty("--spine-w", d.w + "px");
      });
      var lay = shelf.layout(r.ids, 16);
      r.el.style.width = lay.width + "px";
      r.retarget(null, null);
      r.fit();
    });
  };
})();
