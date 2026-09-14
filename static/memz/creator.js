/* The solo creator's live preview (spec F-Z.2.2): the browser twin of
   memz/render.py's layout math, so what a person sees while typing is what
   they get. Same font (Heebo Black, loaded via the @font-face in memz.css),
   the same wrap-then-shrink loop, and the same width. Bidi reordering here
   is a small hand-rolled reshaper, not a full Unicode bidi implementation —
   good enough for a live preview of Hebrew plus embedded Latin/digits; the
   server's `python-bidi` render is what actually gets saved and shared. */
(function () {
  "use strict";

  var form = document.querySelector("[data-creator-form]");
  if (!form) return;

  var canvas = document.querySelector("[data-creator-preview]");
  var ctx = canvas.getContext("2d");
  var captionInput = form.querySelector("[data-creator-caption]");
  var counter = document.querySelector("[data-creator-count]");
  var thumbs = form.querySelectorAll("[data-creator-thumb]");

  var RENDER_WIDTH = 1080;
  var DISPLAY_WIDTH = canvas.width; // set in the template, canvas CSS scales it down
  var SCALE = DISPLAY_WIDTH / RENDER_WIDTH;
  var FONT_MAX = 64 * SCALE, FONT_MIN = 36 * SCALE;
  var PAD_X = 36 * SCALE, PAD_Y = 28 * SCALE;
  var LINE_SPACING = 1.18;
  var MAX_LINES = parseInt(canvas.dataset.maxLines || "3", 10);
  var BAR_BG = "#ffffff", BAR_INK = "#111111";

  function isHebrew(ch) {
    var cp = ch.codePointAt(0);
    return (cp >= 0x0590 && cp <= 0x05FF) || (cp >= 0xFB1D && cp <= 0xFB4F);
  }

  function reshape(line) {
    if (!line || !/[֐-׿יִ-ﭏ]/.test(line)) return line;
    var tokens = [], i = 0, n = line.length;
    while (i < n) {
      var ch = line[i];
      if (isHebrew(ch)) {
        var j = i;
        while (j < n && isHebrew(line[j])) j++;
        tokens.push({ t: "rtl", s: line.slice(i, j) });
        i = j;
      } else if (/[A-Za-z0-9]/.test(ch)) {
        var k = i;
        while (k < n && /[A-Za-z0-9]/.test(line[k])) k++;
        tokens.push({ t: "ltr", s: line.slice(i, k) });
        i = k;
      } else {
        tokens.push({ t: "n", s: ch });
        i++;
      }
    }
    // neutrals take the neighbouring direction, RTL by default
    for (var idx = 0; idx < tokens.length; idx++) {
      if (tokens[idx].t !== "n") continue;
      var prev = null, next = null;
      for (var p = idx - 1; p >= 0; p--) { if (tokens[p].t !== "n") { prev = tokens[p].t; break; } }
      for (var q = idx + 1; q < tokens.length; q++) { if (tokens[q].t !== "n") { next = tokens[q].t; break; } }
      tokens[idx].t = (prev === next && prev) ? prev : "rtl";
    }
    var runs = [];
    tokens.forEach(function (tok) {
      var last = runs[runs.length - 1];
      if (last && last.t === tok.t) last.s += tok.s; else runs.push({ t: tok.t, s: tok.s });
    });
    runs.reverse();
    return runs.map(function (r) { return r.t === "rtl" ? r.s.split("").reverse().join("") : r.s; }).join("");
  }

  function wrapLines(text, fontSize, maxWidth) {
    ctx.font = fontSize + "px 'Heebo Black', 'Heebo', sans-serif";
    var words = text.split(/\s+/).filter(Boolean);
    if (!words.length) return [""];
    var lines = [], current = words[0];
    for (var i = 1; i < words.length; i++) {
      var candidate = current + " " + words[i];
      if (ctx.measureText(candidate).width <= maxWidth) current = candidate;
      else { lines.push(current); current = words[i]; }
    }
    lines.push(current);
    return lines;
  }

  function fitCaption(text, maxWidth) {
    for (var size = FONT_MAX; size >= FONT_MIN; size -= 2) {
      var lines = wrapLines(text, size, maxWidth);
      if (lines.length <= MAX_LINES) return { size: size, lines: lines };
    }
    var lines2 = wrapLines(text, FONT_MIN, maxWidth).slice(0, MAX_LINES);
    return { size: FONT_MIN, lines: lines2 };
  }

  var currentImage = null;

  function loadImage(url) {
    return new Promise(function (resolve) {
      var img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = function () { resolve(img); };
      img.onerror = function () { resolve(null); };
      img.src = url;
    });
  }

  function draw() {
    var maxWidth = DISPLAY_WIDTH - 2 * PAD_X;
    var caption = captionInput.value || "";
    var fit = fitCaption(caption, maxWidth);
    var lineHeight = fit.size * LINE_SPACING;
    var barHeight = 2 * PAD_Y + lineHeight * fit.lines.length;

    var imgHeight = currentImage ? Math.round(currentImage.height * (DISPLAY_WIDTH / currentImage.width)) : DISPLAY_WIDTH * 0.75;
    canvas.height = Math.round(barHeight + imgHeight);

    ctx.fillStyle = BAR_BG;
    ctx.fillRect(0, 0, DISPLAY_WIDTH, canvas.height);

    if (currentImage) ctx.drawImage(currentImage, 0, barHeight, DISPLAY_WIDTH, imgHeight);

    ctx.fillStyle = BAR_INK;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    var y = PAD_Y;
    fit.lines.forEach(function (line) {
      ctx.font = fit.size + "px 'Heebo Black', 'Heebo', sans-serif";
      ctx.fillText(reshape(line), DISPLAY_WIDTH / 2, y, maxWidth);
      y += lineHeight;
    });
  }

  function selectThumb(el) {
    thumbs.forEach(function (t) { t.classList.remove("memz-thumb--selected"); });
    el.classList.add("memz-thumb--selected");
    var radio = el.querySelector("input[type=radio]");
    if (radio) radio.checked = true;
    loadImage(el.dataset.creatorThumb).then(function (img) { currentImage = img; draw(); });
  }

  thumbs.forEach(function (el) {
    el.addEventListener("click", function () { selectThumb(el); });
  });
  var checked = form.querySelector("input[name=image]:checked");
  if (checked) {
    var initial = checked.closest("[data-creator-thumb]");
    if (initial) selectThumb(initial);
  }

  captionInput.addEventListener("input", function () {
    if (counter) counter.textContent = String(captionInput.value.length) + "/" + captionInput.maxLength;
    draw();
  });

  var submitBtn = form.querySelector("[data-creator-submit]");
  form.addEventListener("submit", function () {
    if (submitBtn) submitBtn.disabled = true; // Rule 11.1: never a second submit in flight
  });

  draw();
})();
