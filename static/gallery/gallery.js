/* gallery: likes, stars and the comment thread, through the REST API (Rule 6).
   No framework: the page is rendered on the server, and this only talks to
   /gallery/api/ and updates what changed. A visitor who presses like or star
   is sent to sign in and comes back to the same page (REQ-G.2). */

(function () {
  "use strict";

  var signedIn = document.body.dataset.signedIn === "1";

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function api(method, path, body) {
    return fetch("/gallery/api/" + path, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      if (r.status === 204) return {};
      return r.json().then(function (data) {
        if (!r.ok) {
          var msg = (data && (data.detail || (data.non_field_errors && data.non_field_errors[0]) || (data.body && data.body[0]))) || "Error";
          throw new Error(msg);
        }
        return data;
      });
    });
  }

  // Confirm before a destructive form posts (taking a card down).
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (f.dataset && f.dataset.confirm && !window.confirm(f.dataset.confirm)) e.preventDefault();
  });

  // Likes and stars (REQ-G.20, G.21).
  document.addEventListener("click", function (e) {
    var like = e.target.closest("[data-like]");
    var star = e.target.closest("[data-star]");
    var btn = like || star;
    if (!btn) return;
    e.preventDefault();
    if (!signedIn) { location.href = document.body.dataset.login; return; }
    if (btn.dataset.busy) return;
    btn.dataset.busy = "1";
    var id = like ? like.dataset.like : star.dataset.star;
    api("POST", "exhibits/" + id + "/" + (like ? "like" : "star") + "/").then(function (r) {
      document.querySelectorAll(like ? '[data-like="' + id + '"]' : '[data-star="' + id + '"]').forEach(function (b) {
        b.setAttribute("aria-pressed", r.on ? "true" : "false");
        var count = b.querySelector(".gl-count");
        if (count && typeof r.count === "number") count.textContent = r.count;
      });
    }).catch(function () {}).then(function () { delete btn.dataset.busy; });
  });

  // The comment thread (REQ-G.22, G.23).
  var thread = document.getElementById("thread");
  var form = document.getElementById("gl-comment-form");
  if (!thread || !form) return;
  var exhibit = parseInt(thread.dataset.exhibit, 10);
  var body = document.getElementById("gl-comment-body");
  var replying = document.getElementById("gl-replying");
  var replyingTo = document.getElementById("gl-replying-to");
  var error = document.getElementById("gl-comment-error");
  var replyTo = null;

  function fail(msg) { error.textContent = msg; error.hidden = false; }

  thread.addEventListener("click", function (e) {
    var reply = e.target.closest("[data-reply]");
    var edit = e.target.closest("[data-edit]");
    var del = e.target.closest("[data-delete]");
    if (reply) {
      var note = reply.closest("[data-comment]");
      replyTo = parseInt(reply.dataset.reply, 10);
      replyingTo.textContent = note.dataset.author;
      replying.hidden = false;
      body.focus();
    } else if (e.target.id === "gl-replying-cancel") {
      replyTo = null;
      replying.hidden = true;
    } else if (del) {
      if (!window.confirm(form.dataset.confirmDelete)) return;
      api("DELETE", "comments/" + del.dataset.delete + "/").then(function () { location.reload(); }).catch(function (err) { fail(err.message); });
    } else if (edit) {
      var n = edit.closest("[data-comment]");
      var p = n.querySelector(".gl-note-body");
      if (n.querySelector(".gl-edit-box")) return;
      var box = document.createElement("div");
      box.className = "gl-edit-box";
      var ta = document.createElement("textarea");
      ta.rows = 3; ta.maxLength = 2000; ta.value = p.innerText;
      var save = document.createElement("button");
      save.type = "button"; save.className = "gl-btn"; save.textContent = form.dataset.save;
      save.addEventListener("click", function () {
        api("PATCH", "comments/" + edit.dataset.edit + "/", { body: ta.value }).then(function () { location.reload(); }).catch(function (err) { fail(err.message); });
      });
      box.appendChild(ta); box.appendChild(save);
      p.hidden = true;
      p.parentNode.insertBefore(box, p.nextSibling);
      ta.focus();
    }
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    error.hidden = true;
    var text = body.value.trim();
    if (!text) { fail(form.dataset.empty); return; }
    var submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    api("POST", "comments/", { exhibit: exhibit, body: text, reply_to: replyTo }).then(function (c) {
      location.hash = "c" + c.id;
      location.reload();
    }).catch(function (err) { fail(err.message); submit.disabled = false; });
  });
})();

/* The skill chat: a press that calls the model takes a few seconds. Say so,
   and do not let a second press send it twice. */
(function () {
  "use strict";
  document.querySelectorAll("form.gl-busy").forEach(function (f) {
    f.addEventListener("submit", function () {
      var wait = document.getElementById("gl-wait");
      if (wait) wait.hidden = false;
      document.querySelectorAll(".gl-chat button").forEach(function (b) { b.disabled = true; });
    });
  });
})();


/* The search hides behind the magnifier (Avi, 2026-11-10): only the cards
   show until it is pressed; pressing it again hides the fields. */
(function () {
  "use strict";
  var find = document.getElementById("gl-find");
  var form = document.getElementById("gl-search");
  if (!find || !form) return;
  find.addEventListener("toggle", function () {
    form.hidden = !find.open;
    if (find.open) { var q = document.getElementById("gl-q"); if (q) q.focus(); }
  });
})();
