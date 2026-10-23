/* The first time with a book (Avi, 2026-10-22).
   The cover: the book is found in the photo and straightened to its own
   proportions here on the phone (rectify.js, Avi 2026-10-23: "I always shoot
   at an angle"); shown at once and sent; nothing is spent on a model. If no
   book is found, the middle of the photo is cut to 2 by 3, as before, and a
   straightening that came out wrong can be undone with one tap.
   The back cover: Android phones read the barcode themselves (free) and the
   ISBN goes along; the server reads the rest once, on request. */
(function () {
  "use strict";
  var csrf = document.body.getAttribute("data-csrf");

  var loadImage = function (file) {
    return new Promise(function (ok, fail) {
      var img = new Image();
      img.onload = function () { ok(img); };
      img.onerror = fail;
      img.src = URL.createObjectURL(file);
    });
  };
  var straighten = function (img) {
    if (window.bkRectify) return window.bkRectify(img);
    return {canvas: plain(img), found: false};
  };
  var plain = function (img) {
    var w = img.naturalWidth, h = img.naturalHeight, cw = w, ch = h;
    if (w / h > 2 / 3) cw = Math.round(h * 2 / 3); else ch = Math.round(w * 3 / 2);
    var scale = Math.min(1, 1400 / Math.max(cw, ch));
    var c = document.createElement("canvas");
    c.width = Math.round(cw * scale); c.height = Math.round(ch * scale);
    c.getContext("2d").drawImage(img, (w - cw) / 2, (h - ch) / 2, cw, ch, 0, 0, c.width, c.height);
    return c;
  };
  var send = function (url, blob, name, extra) {
    var fd = new FormData();
    fd.append("photo", blob, name);
    Object.keys(extra || {}).forEach(function (k) { fd.append(k, extra[k]); });
    return fetch(url, {method: "POST", body: fd, headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); });
  };

  // ---- the cover ----
  var coverInput = document.querySelector("[data-first-cover-input]");
  var coverBox = document.querySelector("[data-first-cover]");
  var coverStatus = document.querySelector("[data-first-cover-status]");
  var cattr = function (k) { return coverInput.getAttribute("data-" + k) || ""; };
  var showAndSend = function (c, done) {
    coverBox.classList.remove("bk-cover-drawn");
    coverBox.removeAttribute("style");
    coverBox.innerHTML = "";
    var shown = new Image();
    shown.alt = "";
    shown.src = c.toDataURL("image/jpeg", 0.85);
    coverBox.appendChild(shown);
    c.toBlob(function (blob) {
      send(coverInput.getAttribute("data-url"), blob, "cover.jpg").then(function (res) {
        if (!res.ok) { coverStatus.textContent = res.d.error || ""; return; }
        done();
      });
    }, "image/jpeg", 0.88);
  };
  if (coverInput) coverInput.addEventListener("change", function () {
    var f = coverInput.files && coverInput.files[0];
    if (!f) return;
    coverStatus.textContent = cattr("working");
    loadImage(f).then(function (img) {
      setTimeout(function () {  // let "straightening" show before the work starts
        var r = straighten(img);
        coverInput.setAttribute("data-found", r.found ? "1" : "0");
        showAndSend(r.canvas, function () {
          coverStatus.textContent = r.found ? cattr("straight") : cattr("saved");
          if (!r.found) return;
          // Came out wrong? One tap keeps the photo as it was taken.
          var undo = document.createElement("button");
          undo.type = "button";
          undo.className = "bk-cover-undo";
          undo.setAttribute("data-first-cover-undo", "");
          undo.textContent = cattr("undo");
          undo.addEventListener("click", function () {
            undo.remove();
            coverStatus.textContent = cattr("working");
            showAndSend(plain(img), function () { coverStatus.textContent = cattr("saved"); });
          });
          coverStatus.appendChild(document.createTextNode(" "));
          coverStatus.appendChild(undo);
        });
      }, 30);
    }).catch(function () { coverStatus.textContent = ""; });
  });

  // ---- the back cover ----
  var backInput = document.querySelector("[data-first-back-input]");
  var backStatus = document.querySelector("[data-first-back-status]");
  var pages = document.querySelector("[data-first-pages]");
  var attr = function (k) { return backInput.getAttribute("data-" + k) || ""; };
  var readBarcode = function (img) {
    if (!("BarcodeDetector" in window)) return Promise.resolve("");
    try {
      var det = new window.BarcodeDetector({formats: ["ean_13"]});
      return det.detect(img).then(function (codes) {
        var hit = codes.map(function (c) { return c.rawValue; }).filter(function (v) { return /^97[89]\d{10}$/.test(v); })[0];
        return hit || "";
      }).catch(function () { return ""; });
    } catch (e) { return Promise.resolve(""); }
  };
  if (backInput) backInput.addEventListener("change", function () {
    var f = backInput.files && backInput.files[0];
    if (!f) return;
    backStatus.textContent = attr("working");
    loadImage(f).then(function (img) {
      return readBarcode(img).then(function (isbn) {
        return send(attr("url"), f, f.name || "back.jpg", isbn ? {isbn: isbn} : {});
      });
    }).then(function (res) {
      if (!res.ok) { backStatus.textContent = res.d.error || ""; return; }
      var bits = [];
      if (res.d.filled.length) bits.push(attr("filled") + " " + res.d.filled.join(", "));
      if (res.d.suggested.length) bits.push(attr("suggested") + " " + res.d.suggested.join(", "));
      backStatus.textContent = bits.length ? bits.join(" · ") : attr("nothing");
      if (res.d.pages && pages && !pages.value) pages.value = res.d.pages;
    }).catch(function () { backStatus.textContent = ""; });
  });
})();
