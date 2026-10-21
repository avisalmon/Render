/* My thoughts on the book, while the timer runs (Avi, 2026-10-21). A sheet
   over the reading screen: earlier notes on this book, a box to add one, and
   a microphone. A spoken note is recorded here, sent once to be written down,
   and lands in the box to be read and fixed before it is saved. Saving and
   deleting go by fetch, so the timer page never reloads; without script the
   form still posts. */
(function () {
  "use strict";
  var sheet = document.querySelector("[data-notes]");
  if (!sheet) return;
  var openBtn = document.querySelector("[data-notes-open]");
  var count = document.querySelector("[data-notes-count]");
  var list = sheet.querySelector("[data-notes-list]");
  var empty = sheet.querySelector("[data-notes-empty]");
  var form = sheet.querySelector("[data-notes-form]");
  var body = sheet.querySelector("[data-notes-body]");
  var source = sheet.querySelector("[data-notes-source]");
  var page = sheet.querySelector("[data-notes-page]");
  var status = sheet.querySelector("[data-notes-status]");
  var mic = sheet.querySelector("[data-notes-mic]");
  var csrf = document.body.getAttribute("data-csrf");
  var attr = function (k) { return sheet.getAttribute("data-" + k) || ""; };
  var stopRecording = function () {};  // replaced below when a microphone is there

  var refreshCount = function () {
    var n = list.children.length;
    count.textContent = n ? String(n) : "";
    empty.hidden = n > 0;
  };
  var currentPage = function () {
    var p = document.querySelector("[data-flip-input]");
    return p && p.value ? p.value : page.value;
  };

  openBtn.addEventListener("click", function () {
    page.value = currentPage();
    if (sheet.showModal) sheet.showModal(); else sheet.setAttribute("open", "");
    setTimeout(function () { body.focus(); }, 60);
  });
  sheet.querySelector("[data-notes-close]").addEventListener("click", function () { stopRecording(true); sheet.close(); });
  sheet.addEventListener("click", function (e) { if (e.target === sheet) { stopRecording(true); sheet.close(); } });

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
    li.scrollIntoView({block: "nearest"});
    refreshCount();
  };

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!body.value.trim()) { body.focus(); return; }
    page.value = currentPage();
    fetch(form.getAttribute("action"), {method: "POST", body: new FormData(form),
      headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (res) {
        if (!res.ok) { status.textContent = res.d.error || ""; return; }
        addRow(res.d.note);
        body.value = ""; source.value = "typed"; status.textContent = "";
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

  // ---- the microphone --------------------------------------------------------------
  if (!mic) return;
  var canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  if (!canRecord) return;
  mic.hidden = false;
  var label = mic.querySelector("[data-notes-mic-label]");
  var rec = null, chunks = [], stream = null, startedAt = 0, timer = 0, discard = false;

  var pickType = function () {
    var types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    for (var i = 0; i < types.length; i++) if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(types[i])) return types[i];
    return "";
  };
  stopRecording = function (drop) {
    discard = !!drop;
    if (rec && rec.state !== "inactive") rec.stop();
  };
  window.bkNotesStop = stopRecording;

  var send = function (blob, seconds) {
    status.textContent = attr("working");
    mic.disabled = true;
    var fd = new FormData();
    var type = (blob.type || "audio/webm").split(";")[0];
    fd.append("audio", blob, "note." + (type.indexOf("mp4") >= 0 ? "mp4" : type.indexOf("ogg") >= 0 ? "ogg" : "webm"));
    fd.append("seconds", String(seconds));
    fetch(attr("voice-url"), {method: "POST", body: fd, headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (res) {
        mic.disabled = false;
        if (!res.ok) { status.textContent = res.d.error || ""; return; }
        body.value = (body.value.trim() ? body.value.trim() + " " : "") + res.d.text;
        source.value = "voice";
        status.textContent = attr("check");
        body.focus();
      })
      .catch(function () { mic.disabled = false; status.textContent = ""; });
  };

  mic.addEventListener("click", function () {
    if (rec && rec.state === "recording") { stopRecording(false); return; }
    navigator.mediaDevices.getUserMedia({audio: true}).then(function (s) {
      stream = s; chunks = []; discard = false;
      var type = pickType();
      rec = type ? new MediaRecorder(s, {mimeType: type}) : new MediaRecorder(s);
      rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      rec.onstop = function () {
        clearInterval(timer);
        stream.getTracks().forEach(function (t) { t.stop(); });
        mic.classList.remove("is-on");
        label.textContent = attr("record");
        var seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
        if (discard || !chunks.length) { status.textContent = ""; return; }
        send(new Blob(chunks, {type: rec.mimeType || type || "audio/webm"}), seconds);
      };
      rec.start();
      startedAt = Date.now();
      mic.classList.add("is-on");
      label.textContent = attr("stop");
      var tick = function () {
        var s = Math.round((Date.now() - startedAt) / 1000);
        status.textContent = attr("listening") + " " + Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
        if (s >= 120) stopRecording(false);  // two minutes at most
      };
      tick();
      timer = setInterval(tick, 500);
    }).catch(function () { status.textContent = attr("mic-error"); });
  });
})();
