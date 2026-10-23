/* "I finished the book!" (Avi, 2026-10-21): the clock stops, fireworks and
   confetti go up, and there is room for a summary and thoughts (it can be
   skipped). Saving or skipping ends the session as a finished book and goes
   home; "not yet" closes it and the clock runs again. */
(function () {
  "use strict";
  var dialog = document.querySelector("[data-finish]");
  var openBtn = document.querySelector("[data-finish-open]");
  if (!dialog || !openBtn) return;
  var form = dialog.querySelector("[data-finish-form]");
  var pageField = form.querySelector("[data-finish-page]");
  // The sky itself lives in sky.js, shared with the five-minute moment (Avi, 2026-10-23).
  var sky = window.bkSky(dialog.querySelector("[data-sky]"));
  var celebrate = function () { sky.start(); };
  var calm = function () { sky.stop(); };

  openBtn.addEventListener("click", function () {
    if (window.bkReading) window.bkReading.pause();  // the clock stops when the book is done
    var flip = document.querySelector("[data-flip-input]");
    var reached = flip ? parseInt(flip.value, 10) || 0 : 0;
    var pages = parseInt(pageField.getAttribute("data-pages"), 10) || 0;
    pageField.value = String(Math.max(reached, pages));
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "");
    dialog.querySelector(".bk-finish-card").focus({preventScroll: true});
    celebrate();
    if (navigator.vibrate) { try { navigator.vibrate([30, 60, 30]); } catch (e) { /* ignore */ } }
  });
  window.addEventListener("resize", function () { if (dialog.open) sky.size(); });

  dialog.querySelector("[data-finish-cancel]").addEventListener("click", function () {
    if (window.bkStopRecording) window.bkStopRecording();
    calm();
    dialog.close();
    if (window.bkReading) window.bkReading.resume();
  });
  dialog.addEventListener("cancel", function () { calm(); if (window.bkReading) window.bkReading.resume(); });
  form.querySelector("[data-finish-skip]").addEventListener("click", function () {
    form.querySelector("[data-voice-text]").value = "";
  });
  form.addEventListener("submit", function () { if (window.bkReading) window.bkReading.end(); });
})();
