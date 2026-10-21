/* My thoughts on the book, while the timer runs (Avi, 2026-10-21).

   1. The microphone, for any form on the page that has one ([data-voice-mic]
      with [data-voice-text], [data-voice-status], [data-voice-source]): tap to
      record, tap to stop; the recording is sent once to be written down, and
      the words land in the box to be read and fixed. The audio is not kept.
   2. "What I think" on the reading screen (Avi, 2026-10-21): one tap on the
      breathing button and it listens; a second tap stops, and the words come
      back in a card with "save the thought". "Type instead" opens the same
      card for the keyboard. Saving goes by fetch, so the timer never reloads;
      without script the form still posts.
   3. The sheet of earlier thoughts on this book, opened from the count. */
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
          form.dispatchEvent(new CustomEvent("bk:voice-text"));
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

  // ---- 2. what I think ---------------------------------------------------------------
  var think = document.querySelector("[data-think]");
  var list = document.querySelector("[data-notes-list]");
  var sheet = document.querySelector("[data-notes]");
  if (!think) return;
  var orb = think.querySelector("[data-orb]");
  var card = think.querySelector("[data-think-card]");
  var body = think.querySelector("[data-voice-text]");
  var source = think.querySelector("[data-voice-source]");
  var status = think.querySelector("[data-voice-status]");
  var page = think.querySelector("[data-notes-page]");
  var countLink = think.querySelector("[data-notes-open]");
  var count = think.querySelector("[data-notes-count]");
  var listens = orb.hasAttribute("data-voice-mic") && canRecord;
  var sattr = function (k) { return sheet ? sheet.getAttribute("data-" + k) || "" : ""; };

  var currentPage = function () {
    var f = document.querySelector("[data-flip-input]");
    return f && f.value ? f.value : page.value;
  };
  var showCard = function (focus) {
    card.hidden = false;
    if (focus) body.focus();
    else card.scrollIntoView({block: "nearest", behavior: "smooth"});
  };
  var reset = function () {
    card.hidden = true; body.value = ""; if (source) source.value = "typed"; status.textContent = "";
  };
  // Without a microphone (or without voice on the server) the button opens the keyboard card.
  if (!listens) orb.addEventListener("click", function () { showCard(true); });
  think.addEventListener("bk:voice-text", function () { showCard(false); });
  think.querySelector("[data-think-type]").addEventListener("click", function () { window.bkStopRecording(); showCard(true); });
  think.querySelector("[data-think-cancel]").addEventListener("click", function () { window.bkStopRecording(); reset(); });

  var addRow = function (n) {
    if (!list) return;
    var li = document.createElement("li");
    li.setAttribute("data-note", n.id);
    var p = document.createElement("p");
    p.textContent = n.body;
    var meta = document.createElement("span");
    meta.className = "bk-notes-meta";
    var bits = [];
    if (n.page) bits.push(sattr("page-tpl").replace("{n}", n.page));
    var d = new Date(n.when);
    bits.push(String(d.getDate()).padStart(2, "0") + "." + String(d.getMonth() + 1).padStart(2, "0"));
    if (n.source === "voice") bits.push(sattr("voice-label"));
    meta.textContent = bits.join(" · ");
    var del = document.createElement("button");
    del.type = "button"; del.className = "bk-notes-del"; del.setAttribute("data-note-del", n.id);
    del.textContent = sattr("delete-label");
    li.appendChild(p); li.appendChild(meta); li.appendChild(del);
    list.appendChild(li);
  };
  var refreshCount = function () {
    var n = list ? list.children.length : 0;
    count.textContent = String(n);
    countLink.hidden = n === 0;
  };

  think.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!body.value.trim()) { showCard(true); return; }
    page.value = currentPage();
    fetch(think.getAttribute("action"), {method: "POST", body: new FormData(think),
      headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (res) {
        if (!res.ok) { status.textContent = res.d.error || ""; return; }
        addRow(res.d.note);
        reset();
        body.blur();
        refreshCount();
        status.textContent = think.getAttribute("data-saved") || "";
        setTimeout(function () { if (card.hidden) status.textContent = ""; }, 2200);
      })
      .catch(function () { think.submit(); });
  });

  // ---- 3. the sheet of earlier thoughts ---------------------------------------------
  if (!sheet) return;
  var close = function () { sheet.close(); };
  countLink.addEventListener("click", function () {
    if (sheet.showModal) sheet.showModal(); else sheet.setAttribute("open", "");
    sheet.querySelector("[data-notes-close]").focus({preventScroll: true});
  });
  sheet.querySelector("[data-notes-close]").addEventListener("click", close);
  sheet.addEventListener("click", function (e) { if (e.target === sheet) close(); });
  list.addEventListener("click", function (e) {
    var b = e.target.closest("[data-note-del]");
    if (!b) return;
    var id = b.getAttribute("data-note-del");
    fetch(sattr("del-tpl").replace("/0/", "/" + id + "/"), {method: "POST",
      headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
      .then(function (r) { if (r.ok) { b.closest("li").remove(); refreshCount(); } });
  });
})();
