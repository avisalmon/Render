/* design3d: a design page (REQ-D3.11, D3.12, D3.22, D3.23).

   - Sending: text and pictures go up with fetch; the person's message shows
     at once, then the assistant's turn is polled until it is done.
   - Polling: new and pending messages are drawn; when the current version
     changes, the 3D view, the size, the sliders and the versions follow.
   - Sliders: show their value as they move; "Apply sizes" builds a new
     version in the background, with no call to the model.
   - On a computer the sizes panel is open; on a phone it is folded. */

(function () {
  "use strict";

  var work = document.getElementById("d3-work");
  if (!work) return;
  var msgs = document.getElementById("d3-msgs");
  var form = document.getElementById("d3-composer");
  var text = document.getElementById("d3-text");
  var files = document.getElementById("d3-files");
  var camera = document.getElementById("d3-camera");
  var chosen = document.getElementById("d3-chosen");
  var send = document.getElementById("d3-send");
  var tools = document.getElementById("d3-tools");
  var busy = document.getElementById("d3-busy");
  var current = work.dataset.current;
  var timer = null;

  if (window.matchMedia("(min-width: 980px)").matches) tools.open = true;

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined) e.textContent = txt;
    return e;
  }

  // Ask again from the oldest unfinished message, so a turn that finishes
  // after a newer one was sent is still redrawn (Avi, 2026-10-28: a done
  // turn kept saying "Building" once the next one had started).
  function lastId() {
    var pending = msgs.querySelectorAll('.d3-msg[data-state="thinking"], .d3-msg[data-state="building"]');
    if (pending.length) return Number(pending[0].dataset.id) - 1;
    var all = msgs.querySelectorAll(".d3-msg[data-id]");
    return all.length ? all[all.length - 1].dataset.id : 0;
  }

  // The running clock beside a turn's step. The seconds come from the
  // server (a phone's clock may be off) and are counted on from there.
  function tick() {
    var now = Date.now();
    Array.prototype.forEach.call(msgs.querySelectorAll(".d3-elapsed[data-seconds]"), function (e) {
      var s = Math.max(0, Math.round(Number(e.dataset.seconds) + (now - Number(e.dataset.at)) / 1000));
      e.textContent = "· " + (s < 60 ? s + " s" : Math.floor(s / 60) + " min " + (s % 60) + " s");
      var msg = e.closest(".d3-msg");
      if (s >= 120 && !msg.querySelector(".d3-slow")) {
        msg.appendChild(el("span", "d3-slow", "Taking longer than usual. It is still working; if nothing changes in 10 minutes it stops and you can send it again."));
      }
    });
  }
  setInterval(tick, 1000);

  function scrollDown() { msgs.scrollTop = msgs.scrollHeight; }

  function drawMessage(m) {
    var a = el("article", "d3-msg " + m.role + " " + m.state);
    a.id = "m" + m.id;
    a.dataset.id = m.id;
    a.dataset.state = m.state;
    if (m.state === "thinking" || m.state === "building") {
      a.appendChild(el("span", "d3-thinking", m.step || "Reading your message"));
      a.appendChild(document.createTextNode(" "));
      var clock = el("span", "d3-elapsed d3-mono");
      clock.dataset.seconds = m.seconds || 0;
      clock.dataset.at = Date.now();
      a.appendChild(clock);
    } else {
      a.appendChild(el("span", "d3-msg-text", m.text || ""));
    }
    if (m.pin) a.appendChild(el("span", "d3-pin-tag", "Point marked on the part"));
    (m.references || []).forEach(function (r) { a.appendChild(el("span", "d3-ref-tag d3-mono", r.name + " · " + r.size + " mm")); });
    if (m.assumptions && m.assumptions.length) {
      var ul = el("ul", "d3-assume");
      m.assumptions.forEach(function (t) { ul.appendChild(el("li", "", t)); });
      a.appendChild(ul);
    }
    if (m.pictures && m.pictures.length) {
      var pics = el("div", "d3-pics");
      m.pictures.forEach(function (src) {
        var b = el("button", "d3-pic");
        b.type = "button";
        b.dataset.full = src;
        b.setAttribute("aria-label", "Open the picture");
        var img = el("img");
        img.src = src; img.alt = "Picture sent"; img.width = 84; img.height = 84;
        b.appendChild(img);
        pics.appendChild(b);
      });
      a.appendChild(pics);
    }
    if (m.version) {
      var built = el("div", "d3-built", "Version " + m.version);
      if (m.print) {
        built.appendChild(document.createTextNode(" · "));
        built.appendChild(el("span", m.print === "ready to print" ? "d3-ok" : "d3-warn", m.print));
      }
      a.appendChild(built);
    }
    var old = document.getElementById("m" + m.id);
    // The trail: a look inside the turn, open while it runs, folded when
    // it ends; a person's own open/close is kept across redraws.
    if (m.trail && m.trail.length) {
      var det = el("details", "d3-trail");
      var was = old && old.querySelector(".d3-trail");
      det.open = was && was.dataset.touched ? was.open : (m.state === "thinking" || m.state === "building");
      if (was && was.dataset.touched) det.dataset.touched = "1";
      var sum = el("summary", "", "How this turn went");
      sum.addEventListener("click", function () { det.dataset.touched = "1"; });
      det.appendChild(sum);
      var ol = el("ol");
      m.trail.forEach(function (t) {
        var li = el("li");
        li.appendChild(el("span", "d3-mono", t[0] + " s"));
        li.appendChild(document.createTextNode(" " + t[1]));
        ol.appendChild(li);
      });
      det.appendChild(ol);
      a.appendChild(det);
    }
    if (old) old.replaceWith(a); else msgs.appendChild(a);
    var hello = document.getElementById("d3-hello");
    if (hello) hello.remove();
  }

  /* ---------- several parts (Chapter 7) ---------- */

  var shownParts = null;
  function drawParts(v) {
    var bar = document.getElementById("d3-parts-bar");
    var list = document.getElementById("d3-partlist");
    var mf = document.getElementById("d3-3mf");
    bar.textContent = "";
    list.textContent = "";
    var multi = !!(v && v.parts && v.parts.length);
    bar.hidden = list.hidden = !multi;
    mf.hidden = !(v && v.file_3mf);
    if (v && v.file_3mf) mf.href = v.file_3mf;
    shownParts = multi ? v : null;
    if (!multi) return;

    var views = el("div", "d3-seg");
    [["assembled", "Assembled"], ["plate", "Print plate"]].forEach(function (pair) {
      var b = el("button", "d3-chip", pair[1]);
      b.type = "button";
      b.dataset.view = pair[0];
      b.setAttribute("aria-pressed", String(pair[0] === "assembled"));
      views.appendChild(b);
    });
    bar.appendChild(views);
    var chips = el("div", "d3-part-chips");
    v.parts.forEach(function (p) {
      var b = el("button", "d3-chip d3-part-chip");
      b.type = "button";
      b.dataset.part = p.name;
      b.setAttribute("aria-pressed", "true");
      var dot = el("span", "d3-part-dot");
      dot.style.background = p.color;
      b.appendChild(dot);
      b.appendChild(document.createTextNode(p.label + (p.count > 1 ? " x" + p.count : "")));
      chips.appendChild(b);
    });
    bar.appendChild(chips);
    var ex = el("label", "d3-explode");
    ex.appendChild(el("span", "", "Pull apart"));
    var range = el("input");
    range.type = "range"; range.min = 0; range.max = 1; range.step = 0.05; range.value = 0;
    range.id = "d3-explode";
    ex.appendChild(range);
    bar.appendChild(ex);

    v.parts.forEach(function (p) {
      var li = el("li");
      var dot = el("span", "d3-part-dot");
      dot.style.background = p.color;
      li.appendChild(dot);
      li.appendChild(el("span", "d3-part-name", p.label + (p.count > 1 ? " x" + p.count : "") + (p.printed ? "" : " (bought, not printed)")));
      li.appendChild(el("span", "d3-small d3-muted d3-mono", p.size + " mm"));
      var warns = (p.checks || []).filter(function (c) { return c.level === "warn"; }).length;
      if (p.printed && p.checks) li.appendChild(el("span", warns ? "d3-warn" : "d3-ok", warns ? warns + " print warning" + (warns > 1 ? "s" : "") : "ready"));
      var a = el("a", "d3-btn d3-btn-small d3-btn-quiet", "STL");
      a.href = p.download;
      li.appendChild(a);
      list.appendChild(li);
    });
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest("#d3-parts-bar [data-view]");
    if (b && shownParts && window.d3View) {
      document.querySelectorAll("#d3-parts-bar [data-view]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      var assembled = b.dataset.view === "assembled";
      document.querySelector(".d3-part-chips").hidden = !assembled;
      document.querySelector(".d3-explode").hidden = !assembled;
      if (assembled) window.d3View.loadParts(shownParts.parts); else window.d3View.load(shownParts.stl);
      window.d3View.plate(!assembled);
      return;
    }
    var c = e.target.closest("#d3-parts-bar [data-part]");
    if (c && window.d3View) {
      var on = c.getAttribute("aria-pressed") !== "true";
      c.setAttribute("aria-pressed", String(on));
      window.d3View.setVisible(c.dataset.part, on);
    }
  });
  document.addEventListener("input", function (e) {
    if (e.target.id === "d3-explode" && window.d3View) window.d3View.explode(Number(e.target.value));
  });

  /* ---------- sizes on the part, and sizes to measure (Avi, 2026-10-30) ---------- */

  var shownVersion = null;
  function drawMeasureForm(v) {
    var form = document.getElementById("d3-to-measure");
    form.textContent = "";
    var todo = (v && v.parameters || []).filter(function (p) { return p.measure; });
    form.hidden = !todo.length;
    if (!todo.length) return;
    form.appendChild(el("p", "d3-small", "Please measure. My estimates are filled in; type the real sizes:"));
    todo.forEach(function (p) {
      var label = el("label", "d3-measure-row");
      label.appendChild(el("b", "d3-mono", p.tag));
      label.appendChild(el("span", "", p.label));
      var input = el("input");
      input.type = "number"; input.step = "any"; input.min = "0"; input.name = p.name; input.value = fmt(p.value);
      input.inputMode = "decimal";
      label.appendChild(input);
      label.appendChild(el("span", "d3-small d3-muted", p.unit || "mm"));
      form.appendChild(label);
    });
    var go = el("button", "d3-btn d3-btn-small", "Apply the sizes");
    go.type = "submit";
    form.appendChild(go);
  }

  // A new value for one or more sizes: set them on the sliders form and build.
  function applySizes(values, measured) {
    var sl = document.getElementById("d3-sliders");
    // The typed values go as typed: a range input would clamp them to its
    // own minimum and maximum, and a real measurement may lie outside.
    var extra = new FormData(sl);
    Object.keys(values).forEach(function (name) { extra.set(name, values[name]); });
    (measured || []).forEach(function (n) { extra.append("measured", n); });
    if (Object.keys(values).length === 1) extra.append("typed", Object.keys(values)[0]);
    busy.hidden = false;
    fetch(sl.action, { method: "POST", body: extra, credentials: "same-origin",
                       headers: { "X-CSRFToken": csrf(), "Accept": "application/json" } })
      .then(function () { setTimeout(poll, 600); })
      .catch(function () { busy.hidden = true; });
  }

  document.getElementById("d3-to-measure").addEventListener("submit", function (e) {
    e.preventDefault();
    var values = {}, measured = [];
    Array.prototype.forEach.call(e.target.querySelectorAll("input"), function (i) {
      if (i.value !== "") { values[i.name] = i.value; measured.push(i.name); }
    });
    applySizes(values, measured);
  });

  // A tap on a size on the part opens a small form for its new value.
  var dimEdit = document.getElementById("d3-dim-edit");
  var dimNow = null;
  document.addEventListener("d3:dim", function (e) {
    dimNow = e.detail;
    document.getElementById("d3-dim-what").textContent = dimNow.measure
      ? dimNow.tag + ": my estimate. Measure the real thing and type it."
      : dimNow.tag + " on the part.";
    document.getElementById("d3-dim-label").textContent = dimNow.label + " (" + (dimNow.unit || "mm") + ")";
    var input = document.getElementById("d3-dim-value");
    input.value = fmt(dimNow.value);
    if (dimEdit.showModal) dimEdit.showModal(); else dimEdit.setAttribute("open", "");
    input.focus();
    input.select();
  });
  dimEdit.addEventListener("close", function () {
    var v = document.getElementById("d3-dim-value").value.trim();
    if (dimEdit.returnValue !== "apply" || !dimNow || v === "" || isNaN(Number(v))) return;
    var o = {};
    o[dimNow.name] = v;
    applySizes(o, dimNow.measure ? [dimNow.name] : []);
  });

  var sizesBtn = document.getElementById("d3-sizes");
  sizesBtn.addEventListener("click", function () {
    var on = sizesBtn.getAttribute("aria-pressed") !== "true";
    sizesBtn.setAttribute("aria-pressed", String(on));
    if (window.d3View) window.d3View.showSizes(on);
  });

  function drawVersion(v) {
    if (!v || v.status !== "ready") return;
    shownVersion = v;
    if (window.d3View) window.d3View.setDims(v.parameters);
    drawMeasureForm(v);
    if (window.d3View) {
      if (v.parts && v.parts.length) window.d3View.loadParts(v.parts);
      else if (v.stl) window.d3View.load(v.stl);
    }
    drawParts(v);
    var size = document.getElementById("d3-size");
    size.textContent = v.size + " mm · grid 10 mm";
    size.hidden = !v.size;
    var list = document.getElementById("d3-slider-list");
    list.textContent = "";
    v.parameters.forEach(function (p) {
      var label = el("label", "d3-slider");
      label.appendChild(el("span", "", p.label));
      var out = el("output", "", fmt(p.value) + p.unit);
      label.appendChild(out);
      var input = el("input");
      input.type = "range"; input.name = p.name; input.min = p.min; input.max = p.max; input.step = p.step;
      input.value = p.value; input.dataset.unit = p.unit;
      label.appendChild(input);
      list.appendChild(label);
    });
    var apply = document.getElementById("d3-apply");
    apply.hidden = !v.parameters.length;
    apply.disabled = true;
    document.querySelector('#d3-sliders input[name="from"]').value = v.number;
    // The files, the share button and "continue from" follow the new part.
    var box = document.getElementById("d3-filebox");
    var stl = document.getElementById("d3-stl");
    stl.href = box.dataset.stl.replace("/v/0/", "/v/" + v.number + "/");
    stl.textContent = "Download STL (v" + v.number + ")";
    document.getElementById("d3-scad").href = box.dataset.scad.replace("/v/0/", "/v/" + v.number + "/");
    box.hidden = false;
    drawChecks(v.checks === null || v.checks === undefined ? v.checks : (v.checks || []).concat(v.fit || []));
    work.dataset.shown = v.number;  // a marked point names the version it is on
    document.getElementById("d3-view-tools").hidden = false;
    document.getElementById("d3-done").hidden = false;
    var share = document.getElementById("d3-share");
    if (share) { share.disabled = false; share.removeAttribute("title"); }
    var cont = document.getElementById("d3-continue");
    if (cont) cont.closest("form").remove();
  }

  // Print-ready checks (D3.7): the same markup as _checks.html.
  function drawChecks(checks) {
    var box = document.getElementById("d3-checks");
    box.textContent = "";
    if (checks === null || checks === undefined) return;
    if (!checks.length) {
      box.appendChild(el("p", "d3-check d3-ok", "Ready to print: it lies flat, nothing floats, no wall is too thin, and it fits a 220 mm bed."));
      return;
    }
    var ul = el("ul", "d3-check-list");
    checks.forEach(function (c) {
      var li = el("li", "d3-check " + (c.level === "warn" ? "d3-warn" : "d3-note"));
      li.appendChild(el("span", "", c.text));
      if (c.level === "warn") {
        var b = el("button", "d3-btn d3-btn-small d3-btn-quiet d3-fix", "Fix it");
        b.type = "button";
        b.dataset.fix = c.fix;
        li.appendChild(document.createTextNode(" "));
        li.appendChild(b);
      }
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  // Tapping "N print warnings" in the chat opens the panel at the findings.
  msgs.addEventListener("click", function (e) {
    if (!e.target.closest(".d3-built .d3-warn")) return;
    tools.open = true;
    document.getElementById("d3-checks").scrollIntoView({ behavior: "smooth", block: "center" });
  });

  // "Fix it" sends the finding to the chat as the person's own message.
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".d3-fix");
    if (!b || send.disabled) return;
    text.value = "Before I print: " + b.dataset.fix;
    if (window.matchMedia("(max-width: 979px)").matches) tools.open = false;
    form.requestSubmit();
  });

  function drawVersions(list) {
    var box = document.getElementById("d3-versions");
    box.textContent = "";
    list.forEach(function (v) {
      var e;
      if (v.status === "ready") { e = el("a", String(v.number) === String(current) ? "on" : "", "v" + v.number); e.href = "?v=" + v.number; }
      else if (v.status === "failed") e = el("span", "failed", "v" + v.number + " ✕");
      else e = el("span", "", "v" + v.number + "…");
      box.appendChild(e);
    });
  }

  function fmt(n) { return String(Math.round(Number(n) * 1000) / 1000); }

  function poll() {
    clearTimeout(timer);
    fetch(work.dataset.poll + "?after=" + lastId(), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var pending = false;
        data.messages.forEach(function (m) {
          drawMessage(m);
          if (m.state === "thinking" || m.state === "building") pending = true;
        });
        var working = data.messages.filter(function (m) { return m.state === "building"; })[0];
        busy.hidden = !(data.building || working);
        busy.textContent = working && working.step ? working.step + "…" : "Building…";
        tick();
        var cur = data.current;
        if (cur && String(cur.number) !== String(current)) {
          current = cur.number;
          drawVersion(cur);
        }
        drawVersions(data.versions);
        var turns = document.getElementById("d3-turns");
        if (turns && data.turns_left !== null && data.turns_left !== undefined) {
          turns.textContent = data.turns_left + " turn" + (data.turns_left === 1 ? "" : "s") + " left";
          turns.classList.toggle("low", data.turns_left <= 5);
        }
        var title = document.getElementById("d3-title");
        if (title && data.title && title.textContent !== data.title) {
          title.textContent = data.title;
          document.title = data.title + " · design3d";
          var rename = document.querySelector('input[name="title"]');
          if (rename && document.activeElement !== rename) rename.value = data.title;
        }
        if (data.messages.length) scrollDown();
        if (pending || data.building) timer = setTimeout(poll, 1500);
        else { send.disabled = false; }
      })
      .catch(function () { timer = setTimeout(poll, 4000); });
  }

  /* ---------- pictures chosen ---------- */

  var picked = [];
  // What is about to be sent: pictures, and at most one STL, each with a
  // button to take it out again (Avi, 2026-10-30).
  function isStl(f) { return /\.stl$/i.test(f.name); }
  function showChosen() {
    chosen.textContent = "";
    picked.forEach(function (f, i) {
      var item = el("span", "d3-chosen-item");
      if (isStl(f)) item.appendChild(el("span", "d3-ref-tag d3-mono", f.name));
      else {
        var img = el("img");
        img.src = URL.createObjectURL(f);
        img.alt = f.name;
        item.appendChild(img);
      }
      var x = el("button", "d3-chosen-x", "\u00d7");
      x.type = "button";
      x.setAttribute("aria-label", "Remove " + f.name);
      x.addEventListener("click", function () { picked.splice(i, 1); showChosen(); });
      item.appendChild(x);
      chosen.appendChild(item);
    });
  }
  [files, camera].forEach(function (input) {
    input.addEventListener("change", function () {
      Array.prototype.forEach.call(input.files, function (f) {
        if (isStl(f)) {
          picked = picked.filter(function (p) { return !isStl(p); });
          picked.push(f);
        } else if (picked.filter(function (p) { return !isStl(p); }).length < 4) picked.push(f);
      });
      input.value = "";
      showChosen();
    });
  });

  /* ---------- saying it (Avi, 2026-10-31) ---------- */
  // Tap the mic, talk, tap again: the words land in the box to read and
  // fix, nothing is sent to the design chat until Send. Each clip's token
  // goes with the message so its cost counts toward the day's limit.
  var mic = document.getElementById("d3-mic");
  var recLine = document.getElementById("d3-recording");
  var recTime = document.getElementById("d3-rec-time");
  var voiceTokens = [];
  var rec = null, recChunks = [], recStart = 0, recTimer = null, recStream = null;
  var MAX_REC = 120;
  if (mic && window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) mic.hidden = false;

  function recType() {
    var kinds = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
    for (var i = 0; i < kinds.length; i++) if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(kinds[i])) return kinds[i];
    return "";
  }
  function stopTracks() {
    if (recStream) recStream.getTracks().forEach(function (t) { t.stop(); });
    recStream = null;
  }
  function showRec(on) {
    mic.setAttribute("aria-pressed", String(on));
    mic.setAttribute("aria-label", on ? "Stop and write it" : "Say it");
    recLine.hidden = !on;
    clearInterval(recTimer);
    if (on) {
      recTime.textContent = "0:00";
      recTimer = setInterval(function () {
        var s = Math.round((Date.now() - recStart) / 1000);
        recTime.textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
        if (s >= MAX_REC && rec && rec.state === "recording") rec.stop();
      }, 250);
    }
  }
  function addWords(words) {
    var cur = text.value.replace(/\s+$/, "");
    text.value = cur ? cur + " " + words : words;
    text.dispatchEvent(new Event("input"));
    text.focus();
  }
  function upload(blob, seconds) {
    var body = new FormData();
    var ext = /mp4/.test(blob.type) ? "mp4" : /ogg/.test(blob.type) ? "ogg" : "webm";
    body.append("audio", blob, "clip." + ext);
    body.append("seconds", String(seconds));
    mic.classList.add("d3-busy");
    mic.disabled = true;
    return fetch(mic.dataset.url, { method: "POST", body: body, credentials: "same-origin",
                                    headers: { "X-CSRFToken": csrf(), "Accept": "application/json" } })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) { alertLine(res.d.error || "Could not turn it into text. Try again."); return; }
        voiceTokens.push(res.d.token);
        addWords(res.d.text);
      })
      .catch(function () { alertLine("Could not send the recording. Check the connection and try again."); })
      .then(function () { mic.classList.remove("d3-busy"); mic.disabled = false; });
  }
  if (mic) mic.addEventListener("click", function () {
    if (rec && rec.state === "recording") { rec.stop(); return; }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      recStream = stream;
      var type = recType();
      rec = type ? new MediaRecorder(stream, { mimeType: type }) : new MediaRecorder(stream);
      recChunks = [];
      rec.addEventListener("dataavailable", function (e) { if (e.data && e.data.size) recChunks.push(e.data); });
      rec.addEventListener("stop", function () {
        var seconds = Math.max(1, Math.round((Date.now() - recStart) / 1000));
        showRec(false);
        stopTracks();
        var blob = new Blob(recChunks, { type: (rec.mimeType || type || "audio/webm").split(";")[0] });
        if (blob.size) upload(blob, seconds);
      });
      recStart = Date.now();
      rec.start();
      showRec(true);
    }).catch(function () {
      alertLine("The microphone is blocked. Allow it for this site in the browser, or type instead.");
    });
  });

  /* ---------- sending ---------- */

  text.addEventListener("input", function () {
    text.style.height = "auto";
    text.style.height = Math.min(text.scrollHeight, 160) + "px";
  });
  text.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && window.matchMedia("(min-width: 980px)").matches) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // A marked point goes with the message, with a picture of the view
  // showing the marker (D3.9).
  function withPin(body) {
    var pin = window.d3View && window.d3View.getPin();
    if (!pin) return Promise.resolve(body);
    body.append("pin", JSON.stringify(pin));
    if (picked.length >= 4) return Promise.resolve(body);
    return window.d3View.snapshot().then(function (blob) {
      if (blob) body.append("pictures", blob, "marked-point.jpg");
      return body;
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!text.value.trim() && !picked.length) return;
    var body = new FormData();
    body.append("text", text.value);
    voiceTokens.forEach(function (t) { body.append("voice", t); });
    picked.forEach(function (f) { body.append("pictures", f, f.name); });
    send.disabled = true;
    withPin(body).then(function (body) {
      return fetch(form.action, { method: "POST", body: body, credentials: "same-origin",
                                  headers: { "X-CSRFToken": csrf(), "Accept": "application/json" } });
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) { alertLine(res.d.error || "Could not send. Try again."); send.disabled = false; return; }
        text.value = ""; text.style.height = ""; picked = []; voiceTokens = []; showChosen();
        if (window.d3View) { window.d3View.clearPin(); window.d3View.setMode(""); }
        poll();
      })
      .catch(function () { alertLine("Could not send. Check the connection and try again."); send.disabled = false; });
  });

  function alertLine(t) {
    var p = el("p", "d3-limit", t);
    form.insertBefore(p, form.firstChild.nextSibling);
    setTimeout(function () { p.remove(); }, 6000);
  }

  /* ---------- sliders ---------- */

  var sliders = document.getElementById("d3-sliders");
  sliders.addEventListener("input", function (e) {
    if (e.target.type !== "range") return;
    e.target.parentNode.querySelector("output").textContent = fmt(e.target.value) + (e.target.dataset.unit || "");
    document.getElementById("d3-apply").disabled = false;
  });
  sliders.addEventListener("submit", function (e) {
    e.preventDefault();
    var apply = document.getElementById("d3-apply");
    apply.disabled = true;
    busy.hidden = false;
    fetch(sliders.action, { method: "POST", body: new FormData(sliders), credentials: "same-origin",
                            headers: { "X-CSRFToken": csrf(), "Accept": "application/json" } })
      .then(function () { setTimeout(poll, 600); })
      .catch(function () { busy.hidden = true; apply.disabled = false; });
  });

  /* ---------- confirm before deleting ---------- */

  document.addEventListener("submit", function (e) {
    var f = e.target.closest("[data-confirm]");
    if (f && !confirm(f.dataset.confirm)) e.preventDefault();
  });

  try {
    var firstShown = JSON.parse((document.getElementById("design3d-shown") || {}).textContent || "null");
    if (firstShown) { drawParts(firstShown); drawMeasureForm(firstShown); shownVersion = firstShown; }
  } catch (err) { /* no version yet */ }

  /* ---------- a picture, full size: save or share (Avi, 2026-10-29) ---------- */

  var box3 = document.getElementById("d3-lightbox");
  var shown = null;
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".d3-pic");
    if (!b) return;
    shown = b.dataset.full;
    box3.querySelector("img").src = shown;
    box3.querySelector("#d3-pic-save").href = shown + "?download=1";
    var share = box3.querySelector("#d3-pic-share");
    share.hidden = !(navigator.canShare && window.File);
    if (box3.showModal) box3.showModal(); else box3.setAttribute("open", "");
  });
  box3.querySelector("#d3-pic-close").addEventListener("click", function () { box3.close ? box3.close() : box3.removeAttribute("open"); });
  box3.addEventListener("click", function (e) { if (e.target === box3) box3.close(); });
  box3.querySelector("#d3-pic-share").addEventListener("click", function () {
    fetch(shown, { credentials: "same-origin" }).then(function (r) { return r.blob(); }).then(function (blob) {
      var file = new File([blob], "design3d-picture.jpg", { type: blob.type || "image/jpeg" });
      if (navigator.canShare({ files: [file] })) return navigator.share({ files: [file], title: document.title });
    }).catch(function () { /* the person closed the share sheet */ });
  });

  /* ---------- the marked point, and the part pinned to the top ---------- */

  var pinned = document.getElementById("d3-pinned");
  document.addEventListener("d3:pin", function (e) {
    pinned.hidden = !e.detail;
    if (e.detail && !text.value) text.focus({ preventScroll: true });
  });
  document.getElementById("d3-unpin").addEventListener("click", function () {
    if (window.d3View) window.d3View.clearPin();
  });

  var bar = document.querySelector(".d3-bar");
  function barHeight() { document.documentElement.style.setProperty("--d3-bar-h", (bar ? bar.offsetHeight : 0) + "px"); }
  if (bar && window.ResizeObserver) new ResizeObserver(barHeight).observe(bar);
  barHeight();

  var stick = document.getElementById("d3-stick");
  function setStuck(on) {
    work.classList.toggle("d3-unstuck", !on);
    stick.setAttribute("aria-pressed", String(on));
    stick.textContent = on ? "Pinned" : "Pin to top";
    try { localStorage.setItem("design3d.stuck", on ? "1" : "0"); } catch (err) { /* private mode */ }
  }
  var stuckWas = "1";
  try { stuckWas = localStorage.getItem("design3d.stuck") || "1"; } catch (err) { /* private mode */ }
  setStuck(stuckWas !== "0");
  stick.addEventListener("click", function () { setStuck(work.classList.contains("d3-unstuck")); });

  scrollDown();
  if (msgs.querySelector('[data-state="thinking"], [data-state="building"]')) poll();
})();
