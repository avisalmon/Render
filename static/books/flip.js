/* The page wheel on the reading screen (Avi, 2026-10-21): flick the pages
   with a finger instead of typing a number. A ruler of pages slides under the
   finger with momentum, and each new page turns a leaf in the open book above
   it. The number input stays in the form (and can still be typed into); the
   wheel only writes to it. Reading direction follows the page: in Hebrew a
   page turns from left to right, so a finger moving right goes forward. */
(function () {
  "use strict";
  var STEP = 14;           // px of drag per page
  var FRICTION = 0.93;     // momentum kept per frame
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function Flip(root) {
    this.root = root;
    this.input = root.querySelector("[data-flip-input]");
    this.num = root.querySelector("[data-flip-n]");
    this.read = root.querySelector("[data-flip-read]");
    this.ruler = root.querySelector("[data-flip-ruler]");
    this.leaf = root.querySelector("[data-flip-leaf]");
    this.min = parseInt(root.getAttribute("data-min"), 10) || 0;
    var max = parseInt(root.getAttribute("data-max"), 10);
    this.max = max > this.min ? max : 99999;
    this.rtl = document.documentElement.getAttribute("dir") === "rtl";
    this.readTpl = root.getAttribute("data-read-tpl") || "+{n}";
    this.value = Math.max(this.min, parseInt(this.input.value, 10) || this.min);
    this.offset = 0;       // px into the current page, for the ruler's smooth slide
    this.v = 0;
    this.raf = 0;
    this.buildRuler();
    this.bind();
    this.render(false);
  }

  Flip.prototype.buildRuler = function () {
    var html = "";
    for (var i = -8; i <= 8; i++) html += '<span class="bk-flip-tick' + (i % 5 === 0 ? " is-five" : "") + '" data-i="' + i + '"></span>';
    this.ruler.innerHTML = html;
    this.ticks = this.ruler.children;
  };

  Flip.prototype.set = function (n, animate) {
    n = Math.min(this.max, Math.max(this.min, n));
    if (n === this.value) return false;
    var forward = n > this.value;
    this.value = n;
    this.render(animate !== false, forward);
    return true;
  };

  Flip.prototype.render = function (animate, forward) {
    this.input.value = this.value;
    this.num.textContent = this.value;
    this.root.setAttribute("aria-valuenow", this.value);
    var gained = this.value - this.min;
    this.read.textContent = gained ? this.readTpl.replace("{n}", gained) : "";
    // The ruler: ticks numbered around the current page, slid by the drag's
    // remainder. The pages ahead sit on the side the finger pulls from (the
    // left in Hebrew), so a forward drag brings the next page to the middle.
    var s = this.rtl ? 1 : -1;  // the finger's direction for "forward"
    for (var k = 0; k < this.ticks.length; k++) {
      var i = k - 8, page = this.value + i, t = this.ticks[k];
      t.style.transform = "translateX(" + (s * (this.offset - i * STEP) * 1.3) + "px)";
      t.style.opacity = page < this.min || page > this.max ? "0" : String(1 - Math.min(1, Math.abs(i) / 8) * 0.85);
      t.setAttribute("data-page", page % 5 === 0 ? page : "");
      t.classList.toggle("is-five", page % 5 === 0);
    }
    if (animate && !reduce && this.leaf) {
      this.leaf.classList.remove("is-turning", "is-back");
      void this.leaf.offsetWidth;  // restart the turn
      this.leaf.classList.add(forward ? "is-turning" : "is-back");
      if (navigator.vibrate) { try { navigator.vibrate(3); } catch (e) { /* ignore */ } }
    }
  };

  Flip.prototype.move = function (dx) {
    // dx in px along the reading direction: positive is forward.
    this.offset += dx;
    var turned = false;
    while (this.offset >= STEP) { this.offset -= STEP; if (!this.set(this.value + 1)) { this.offset = 0; this.v = 0; } turned = true; }
    while (this.offset <= -STEP) { this.offset += STEP; if (!this.set(this.value - 1)) { this.offset = 0; this.v = 0; } turned = true; }
    if (!turned) this.render(false);
  };

  Flip.prototype.glide = function () {
    var self = this;
    cancelAnimationFrame(this.raf);
    var frame = function () {
      if (Math.abs(self.v) < 0.4) { self.v = 0; self.settle(); return; }
      self.move(self.v);
      self.v *= FRICTION;
      self.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  };

  Flip.prototype.settle = function () {
    // Snap to the nearest page.
    if (this.offset > STEP / 2) this.set(this.value + 1);
    else if (this.offset < -STEP / 2) this.set(this.value - 1);
    this.offset = 0;
    this.render(false);
  };

  Flip.prototype.bind = function () {
    var self = this, pad = this.root.querySelector("[data-flip-pad]"), lastX = 0, lastT = 0, down = false;
    var sign = function () { return self.rtl ? 1 : -1; };
    pad.addEventListener("pointerdown", function (e) {
      down = true; lastX = e.clientX; lastT = e.timeStamp; self.v = 0;
      cancelAnimationFrame(self.raf);
      pad.setPointerCapture(e.pointerId);
      self.root.classList.add("is-held");
    });
    pad.addEventListener("pointermove", function (e) {
      if (!down) return;
      var dx = (e.clientX - lastX) * sign(), dt = Math.max(1, e.timeStamp - lastT);
      self.v = 0.8 * (dx / dt * 16) + 0.2 * self.v;  // px per frame, smoothed
      lastX = e.clientX; lastT = e.timeStamp;
      self.move(dx);
    });
    var up = function () {
      if (!down) return;
      down = false;
      self.root.classList.remove("is-held");
      self.glide();
    };
    pad.addEventListener("pointerup", up);
    pad.addEventListener("pointercancel", up);
    // The wheel on a desktop, arrows on a keyboard, and the two buttons.
    pad.addEventListener("wheel", function (e) {
      e.preventDefault();
      self.set(self.value + (e.deltaY > 0 || e.deltaX > 0 ? 1 : -1));
    }, {passive: false});
    this.root.addEventListener("keydown", function (e) {
      var step = e.shiftKey ? 10 : 1, fwd = self.rtl ? "ArrowLeft" : "ArrowRight", back = self.rtl ? "ArrowRight" : "ArrowLeft";
      if (e.key === "ArrowUp" || e.key === fwd) { self.set(self.value + step); e.preventDefault(); }
      else if (e.key === "ArrowDown" || e.key === back) { self.set(self.value - step); e.preventDefault(); }
      else if (e.key === "PageUp") { self.set(self.value + 10); e.preventDefault(); }
      else if (e.key === "PageDown") { self.set(self.value - 10); e.preventDefault(); }
    });
    this.root.querySelectorAll("[data-flip-step]").forEach(function (b) {
      b.addEventListener("click", function () { self.set(self.value + parseInt(b.getAttribute("data-flip-step"), 10)); });
    });
    // Typed by hand: the wheel follows the box.
    this.input.addEventListener("input", function () {
      var n = parseInt(self.input.value, 10);
      if (!isNaN(n) && n >= self.min) { self.value = Math.min(self.max, n); self.offset = 0; self.num.textContent = self.value; self.render(false); }
    });
  };

  document.querySelectorAll("[data-flip]").forEach(function (root) { root.bkFlip = new Flip(root); });
})();
