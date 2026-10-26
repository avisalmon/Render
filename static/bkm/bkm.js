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
      var card = el.closest("[data-slug]");
      var next = location.pathname + (card ? "#" + card.dataset.slug : "");
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
    var btn = e.target.closest("[data-like], [data-star]");
    if (!btn || btn.disabled) return;
    var kind = btn.hasAttribute("data-like") ? "like" : "star";
    var slug = btn.getAttribute("data-" + kind);
    btn.disabled = true;
    fetch("/bkm/api/bkms/" + encodeURIComponent(slug) + "/" + kind + "/", {
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
