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
    if (m.assumptions && m.assumptions.length) {
      var ul = el("ul", "d3-assume");
      m.assumptions.forEach(function (t) { ul.appendChild(el("li", "", t)); });
      a.appendChild(ul);
    }
    if (m.pictures && m.pictures.length) {
      var pics = el("div", "d3-pics");
      m.pictures.forEach(function (src) {
        var img = el("img");
        img.src = src; img.alt = "Picture sent"; img.width = 84; img.height = 84;
        pics.appendChild(img);
      });
      a.appendChild(pics);
    }
    if (m.version) a.appendChild(el("div", "d3-built", "Version " + m.version));
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

  function drawVersion(v) {
    if (!v || v.status !== "ready") return;
    if (window.d3View && v.stl) window.d3View.load(v.stl);
    var size = document.getElementById("d3-size");
    size.textContent = v.size + " mm";
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
  }

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
        var title = document.getElementById("d3-title");
        if (title && data.title && title.textContent !== data.title) {
          title.textContent = data.title;
          document.title = data.title + " · design3d";
        }
        if (data.messages.length) scrollDown();
        if (pending || data.building) timer = setTimeout(poll, 1500);
        else { send.disabled = false; }
      })
      .catch(function () { timer = setTimeout(poll, 4000); });
  }

  /* ---------- pictures chosen ---------- */

  var picked = [];
  function showChosen() {
    chosen.textContent = "";
    picked.forEach(function (f) {
      var img = el("img");
      img.src = URL.createObjectURL(f);
      img.alt = f.name;
      chosen.appendChild(img);
    });
  }
  [files, camera].forEach(function (input) {
    input.addEventListener("change", function () {
      Array.prototype.forEach.call(input.files, function (f) { if (picked.length < 4) picked.push(f); });
      input.value = "";
      showChosen();
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

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!text.value.trim() && !picked.length) return;
    var body = new FormData();
    body.append("text", text.value);
    picked.forEach(function (f) { body.append("pictures", f, f.name); });
    send.disabled = true;
    fetch(form.action, { method: "POST", body: body, credentials: "same-origin",
                         headers: { "X-CSRFToken": csrf(), "Accept": "application/json" } })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) { alertLine(res.d.error || "Could not send. Try again."); send.disabled = false; return; }
        text.value = ""; text.style.height = ""; picked = []; showChosen();
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

  scrollDown();
  if (msgs.querySelector('[data-state="thinking"], [data-state="building"]')) poll();
})();
