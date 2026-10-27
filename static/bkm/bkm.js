/* bkm: the wall's few moving parts.

   - A visitor's click on anything opens the sign-in window (REQ-B.2, B.3),
     which brings them back to where they were.
   - Likes and stars toggle through the API (REQ-B.13, B.14).
   - Copy buttons for the four steps, quoted replies, a confirm on delete.
   - On a phone, the "made for a computer" notice, until dismissed
     (REQ-B.4); remembered on that device only. */

(function () {
  "use strict";

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  /* ---------- the menu stays on top: room for it under the page ---------- */

  var bar = document.querySelector(".bm-bar");
  function room() { document.body.style.setProperty("--bm-bar-h", bar.offsetHeight + "px"); }
  if (bar) {
    room();
    window.addEventListener("resize", room);
    if (window.ResizeObserver) new ResizeObserver(room).observe(bar);
  }

  /* ---------- the phone notice ---------- */

  var phone = document.getElementById("bm-phone");
  var small = window.matchMedia("(max-width: 760px)").matches ||
              window.matchMedia("(hover: none) and (pointer: coarse)").matches;
  var dismissed = false;
  try { dismissed = localStorage.getItem("bm-phone-ok") === "1"; } catch (e) { /* private mode */ }
  if (phone && small && !dismissed) {
    phone.hidden = false;
    document.getElementById("bm-phone-ok").addEventListener("click", function () {
      phone.hidden = true;
      try { localStorage.setItem("bm-phone-ok", "1"); } catch (e) { /* the notice comes back next visit */ }
    });
  }

  /* ---------- the sign-in window, for visitors ---------- */

  var gate = document.getElementById("bm-gate");
  if (gate) {
    var google = document.getElementById("bm-gate-google");
    var form = document.getElementById("bm-gate-form");
    var signup = document.getElementById("bm-gate-signup");

    document.addEventListener("click", function (e) {
      var el = e.target.closest("[data-gate]");
      if (!el) return;
      e.preventDefault();
      var card = el.closest("article[id]");
      var next = el.dataset.next || (location.pathname + (card ? "#" + card.id : ""));
      if (next.indexOf("/bkm/") !== 0) next = "/bkm/";
      google.href = "/accounts/google/login/?process=login&next=" + encodeURIComponent(next);
      form.elements.next.value = next;
      signup.href = "/bkm/signup/?next=" + encodeURIComponent(next);
      if (typeof gate.showModal === "function") gate.showModal();
      else location.href = "/bkm/login/?next=" + encodeURIComponent(next);
    });
    document.getElementById("bm-gate-close").addEventListener("click", function () { gate.close(); });
    gate.addEventListener("click", function (e) { if (e.target === gate) gate.close(); });
  }

  /* ---------- likes and stars ---------- */

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-like], [data-star], [data-plike]");
    if (!btn || btn.disabled) return;
    var url;
    if (btn.hasAttribute("data-plike")) {
      url = "/bkm/api/projects/" + encodeURIComponent(btn.dataset.plike) + "/like/";
    } else {
      var kind = btn.hasAttribute("data-like") ? "like" : "star";
      url = "/bkm/api/bkms/" + encodeURIComponent(btn.getAttribute("data-" + kind)) + "/" + kind + "/";
    }
    btn.disabled = true;
    fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: { "X-CSRFToken": csrf(), "Accept": "application/json" }
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (data) {
      btn.setAttribute("aria-pressed", data.on ? "true" : "false");
      var count = btn.querySelector("[data-count]");
      if (count && data.count !== null) count.textContent = String(data.count);
    }).catch(function () {
      btn.title = "Did not save. Try again.";
    }).then(function () { btn.disabled = false; });
  });

  /* ---------- a project's video, photo and form (REQ-B.32, B.31) ---------- */

  function embed(media, id) {
    var have = media.querySelector("iframe");
    if (have) return have;
    var box = document.createElement("div");
    box.className = "bm-video";
    var frame = document.createElement("iframe");
    frame.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1";
    frame.title = "Video";
    frame.allow = "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; fullscreen";
    frame.allowFullscreen = true;
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    box.appendChild(frame);
    media.innerHTML = "";
    media.appendChild(box);
    return frame;
  }

  document.addEventListener("click", function (e) {
    var play = e.target.closest("[data-embed]");
    if (play) {
      embed(play.closest("[data-media]"), play.dataset.embed);
      return;
    }
    var full = e.target.closest("[data-full]");
    if (full) {
      var card = full.closest("article");
      var media = card.querySelector("[data-media]");
      var frame = embed(media, full.dataset.full);
      var box = frame.parentNode;
      var go = box.requestFullscreen || box.webkitRequestFullscreen;
      if (go) {
        try {
          var p = go.call(box);
          if (p && p.catch) p.catch(function () { window.open("https://www.youtube.com/watch?v=" + full.dataset.full, "_blank", "noopener"); });
        } catch (err) { window.open("https://www.youtube.com/watch?v=" + full.dataset.full, "_blank", "noopener"); }
      } else {
        window.open("https://www.youtube.com/watch?v=" + full.dataset.full, "_blank", "noopener");
      }
      return;
    }
    var zoom = e.target.closest("[data-zoom]");
    var dialog = document.getElementById("bm-zoom");
    if (zoom && dialog) {
      document.getElementById("bm-zoom-img").src = zoom.dataset.zoom;
      dialog.showModal();
      return;
    }
    if (dialog && (e.target.closest("[data-zoom-close]") || e.target === dialog)) dialog.close();
  });

  var projectForm = document.getElementById("bm-project-form");
  if (projectForm) {
    var hints = {
      video: { url: "The YouTube link of your video", image: false },
      site: { url: "The link to your site", image: "A picture instead of the automatic screenshot (optional)" },
      image: { url: "A link about it (optional)", image: "Your photo" }
    };
    function shape() {
      var picked = projectForm.querySelector("input[name=kind]:checked");
      var h = hints[picked ? picked.value : "video"];
      var url = projectForm.querySelector('[data-field="url"]');
      var img = projectForm.querySelector('[data-field="image"]');
      url.querySelector("span").textContent = h.url;
      img.hidden = h.image === false;
      if (h.image) img.querySelector("span").textContent = h.image;
    }
    projectForm.addEventListener("change", function (e) { if (e.target.name === "kind") shape(); });
    shape();
  }

  // Any picture field: say which file was chosen, show it, and let it be
  // turned before saving (REQ-B.24). The server does the real turning.
  function turn(field, deg) {
    field.querySelector("[data-rot-value]").value = String(deg);
    field.querySelector("[data-rot-img]").style.transform = deg ? "rotate(" + deg + "deg)" : "";
  }
  document.addEventListener("change", function (e) {
    if (e.target.type !== "file" || !e.target.files.length) return;
    var field = e.target.closest(".bm-field");
    if (!field) return;
    var name = field.querySelector("[data-upload-name]");
    if (name) name.textContent = "Chosen: " + e.target.files[0].name;
    var rot = field.querySelector("[data-rot]");
    if (rot && window.URL) {
      field.querySelector("[data-rot-img]").src = URL.createObjectURL(e.target.files[0]);
      rot.hidden = false;
      turn(field, 0);
    }
  });
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-rot-by]");
    if (!btn) return;
    var field = btn.closest(".bm-field");
    var now = parseInt(field.querySelector("[data-rot-value]").value, 10) || 0;
    turn(field, (now + parseInt(btn.dataset.rotBy, 10) + 360) % 360);
  });

  /* ---------- copy ---------- */

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    var src = document.querySelector(btn.dataset.copy);
    var text = src ? src.textContent.trim() : "";
    function done() {
      btn.textContent = "Copied";
      btn.classList.add("is-done");
      setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("is-done"); }, 1800);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { select(src); });
    } else {
      select(src);
    }
  });

  function select(el) {
    if (!el) return;
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  /* ---------- replies and deleting ---------- */

  var commentForm = document.getElementById("bm-comment-form");
  if (commentForm) {
    var replying = document.getElementById("bm-replying");
    var who = document.getElementById("bm-replying-who");
    var replyTo = commentForm.elements.reply_to;
    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-reply]");
      if (!btn) return;
      replyTo.value = btn.dataset.reply;
      who.textContent = btn.dataset.who;
      replying.hidden = false;
      commentForm.scrollIntoView({ behavior: "smooth", block: "center" });
      commentForm.elements.body.focus({ preventScroll: true });
    });
    document.getElementById("bm-replying-cancel").addEventListener("click", function () {
      replyTo.value = "";
      replying.hidden = true;
    });
  }

  document.addEventListener("submit", function (e) {
    var f = e.target.closest("[data-confirm]");
    if (f && !confirm(f.dataset.confirm)) e.preventDefault();
  });
})();
