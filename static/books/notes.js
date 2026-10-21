/* My thoughts on the book, while the timer runs (Avi, 2026-10-21).

   1. The microphone, for any form on the page that has one ([data-voice-mic]
      with [data-voice-text], [data-voice-status], [data-voice-source]): tap to
      record, tap to stop; the recording is sent once to be written down, and
      the words land in the box to be read and fixed. The audio is not kept.
   2. The notes sheet over the reading screen: earlier notes on this book and
      a box to add one. It opens without the keyboard (the box takes focus
      only when tapped; most notes will be spoken), and saving goes straight
      back to the timer. Saving and deleting go by fetch, so the timer page
      never reloads; without script the form still posts. */
(function () {
  "use strict";
  var csrf = document.body.getAttribute("data-csrf");

  // ---- 1. the microphone ------------------------------------------------------------
  var canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  var stoppers = [];
  window.bkStopRecording = function () { stoppers.forEach(function (f) { f(true); }); };

  var pickType = function () {
    var types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    for (var i = 0; i < types.length; i++) if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(types[i])) return types[i];
    return "";
  };

  document.querySelectorAll("[data-voice-mic]").forEach(function (mic) {
    if (!canRecord) return;
    var form = mic.closest("form");
    var text = form.querySelector("[data-voice-text]");
    var status = form.querySelector("[data-voice-status]");
    var source = form.querySelector("[data-voice-source]");
    var label = mic.querySelector("[data-voice-label]");
    var attr = function (k) { return mic.getAttribute("data-" + k) || ""; };
    var rec = null, chunks = [], stream = null, startedAt = 0, timer = 0, drop = false;
    mic.hidden = false;
    form.classList.add("has-mic");

    var stop = function (discard) {
      drop = !!discard;
      if (rec && rec.state !== "inactive") rec.stop();
    };
    stoppers.push(stop);

    var send = function (blob, seconds) {
      status.textContent = attr("working");
      mic.disabled = true;
      var fd = new FormData();
      var type = (blob.type || "audio/webm").split(";")[0];
      fd.append("audio", blob, "note." + (type.indexOf("mp4") >= 0 ? "mp4" : type.indexOf("ogg") >= 0 ? "ogg" : "webm"));
      fd.append("seconds", String(seconds));
      fetch(attr("url"), {method: "POST", body: fd, headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
        .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
        .then(function (res) {
          mic.disabled = false;
          if (!res.ok) { status.textContent = res.d.error || ""; return; }
          text.value = (text.value.trim() ? text.value.trim() + " " : "") + res.d.text;
          if (source) source.value = "voice";
          status.textContent = attr("check");
        })
        .catch(function () { mic.disabled = false; status.textContent = ""; });
    };

    mic.addEventListener("click", function () {
      if (rec && rec.state === "recording") { stop(false); return; }
      navigator.mediaDevices.getUserMedia({audio: true}).then(function (s) {
        stream = s; chunks = []; drop = false;
        var type = pickType();
        rec = type ? new MediaRecorder(s, {mimeType: type}) : new MediaRecorder(s);
        rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
        rec.onstop = function () {
          clearInterval(timer);
          stream.getTracks().forEach(function (t) { t.stop(); });
          mic.classList.remove("is-on");
          label.textContent = attr("record");
          var seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
          if (drop || !chunks.length) { status.textContent = ""; return; }
          send(new Blob(chunks, {type: rec.mimeType || type || "audio/webm"}), seconds);
        };
        rec.start();
        startedAt = Date.now();
        mic.classList.add("is-on");
        label.textContent = attr("stop");
        var tick = function () {
          var sec = Math.round((Date.now() - startedAt) / 1000);
          status.textContent = attr("listening") + " " + Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0");
          if (sec >= 120) stop(false);  // two minutes at most
        };
        tick();
        timer = setInterval(tick, 500);
      }).catch(function () { status.textContent = attr("mic-error"); });
    });
  });

  // ---- 2. the notes sheet ----------------------------------------------------------
  var sheet = document.querySelector("[data-notes]");
  if (!sheet) return;
  var openBtn = document.querySelector("[data-notes-open]");
  var count = document.querySelector("[data-notes-count]");
  var list = sheet.querySelector("[data-notes-list]");
  var empty = sheet.querySelector("[data-notes-empty]");
  var form = sheet.querySelector("[data-notes-form]");
  var body = form.querySelector("[data-voice-text]");
  var source = form.querySelector("[data-voice-source]");
  var status = form.querySelector("[data-voice-status]");
  var page = form.querySelector("[data-notes-page]");
  var attr = function (k) { return sheet.getAttribute("data-" + k) || ""; };

  var refreshCount = function () {
    var n = list.children.length;
    count.textContent = n ? String(n) : "";
    empty.hidden = n > 0;
  };
  var currentPage = function () {
    var p = document.querySelector("[data-flip-input]");
    return p && p.value ? p.value : page.value;
  };
  var close = function () { window.bkStopRecording(); sheet.close(); };

  openBtn.addEventListener("click", function () {
    page.value = currentPage();
    status.textContent = "";
    if (sheet.showModal) sheet.showModal(); else sheet.setAttribute("open", "");
    // No focus on the box: the keyboard opens only when the box is tapped.
    var first = sheet.querySelector("[data-voice-mic]:not([hidden])") || sheet.querySelector("[data-notes-close]");
    if (first) first.focus({preventScroll: true});
  });
  sheet.querySelector("[data-notes-close]").addEventListener("click", close);
  sheet.addEventListener("click", function (e) { if (e.target === sheet) close(); });

  var addRow = function (n) {
    var li = document.createElement("li");
    li.setAttribute("data-note", n.id);
    var p = document.createElement("p");
    p.textContent = n.body;
    var meta = document.createElement("span");
    meta.className = "bk-notes-meta";
    var bits = [];
    if (n.page) bits.push(attr("page-tpl").replace("{n}", n.page));
    var d = new Date(n.when);
    bits.push(String(d.getDate()).padStart(2, "0") + "." + String(d.getMonth() + 1).padStart(2, "0"));
    if (n.source === "voice") bits.push(attr("voice-label"));
    meta.textContent = bits.join(" · ");
    var del = document.createElement("button");
    del.type = "button"; del.className = "bk-notes-del"; del.setAttribute("data-note-del", n.id);
    del.textContent = attr("delete-label");
    li.appendChild(p); li.appendChild(meta); li.appendChild(del);
    list.appendChild(li);
    refreshCount();
  };

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!body.value.trim()) return;
    page.value = currentPage();
    fetch(form.getAttribute("action"), {method: "POST", body: new FormData(form),
      headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (res) {
        if (!res.ok) { status.textContent = res.d.error || ""; return; }
        addRow(res.d.note);
        body.value = ""; if (source) source.value = "typed"; status.textContent = "";
        body.blur();
        close();  // saved: straight back to the timer
        openBtn.classList.remove("is-saved"); void openBtn.offsetWidth; openBtn.classList.add("is-saved");
        openBtn.setAttribute("data-flash", attr("saved"));
      })
      .catch(function () { form.submit(); });
  });

  list.addEventListener("click", function (e) {
    var b = e.target.closest("[data-note-del]");
    if (!b) return;
    var id = b.getAttribute("data-note-del");
    fetch(attr("del-tpl").replace("/0/", "/" + id + "/"), {method: "POST",
      headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
      .then(function (r) { if (r.ok) { b.closest("li").remove(); refreshCount(); } });
  });
})();
