/* cohort: likes, stars and the comment thread, through the REST API (Rule 6).
   No framework: the page is rendered on the server, and this only talks to
   /cohort/api/ and updates what changed. */

(function () {
  "use strict";

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function api(method, path, body) {
    return fetch("/cohort/api/" + path, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      if (r.status === 204) return {};
      return r.json().then(function (data) {
        if (!r.ok) {
          var msg = (data && (data.detail || (data.non_field_errors && data.non_field_errors[0]) || (data.body && data.body[0]))) || "משהו השתבש. נסו שוב.";
          throw new Error(msg);
        }
        return data;
      });
    });
  }

  // Likes and stars (REQ-C.13, C.14).
  document.addEventListener("click", function (e) {
    var like = e.target.closest("[data-like]");
    var star = e.target.closest("[data-star]");
    var btn = like || star;
    if (!btn) return;
    e.preventDefault();
    if (btn.dataset.busy) return;
    btn.dataset.busy = "1";
    var id = like ? like.dataset.like : star.dataset.star;
    api("POST", "exhibits/" + id + "/" + (like ? "like" : "star") + "/").then(function (r) {
      document.querySelectorAll(like ? '[data-like="' + id + '"]' : '[data-star="' + id + '"]').forEach(function (b) {
        b.setAttribute("aria-pressed", r.on ? "true" : "false");
        var count = b.querySelector(".cb-count");
        if (count && typeof r.count === "number") count.textContent = r.count;
      });
    }).catch(function () {}).then(function () { delete btn.dataset.busy; });
  });

  // The comment thread (REQ-C.15, C.16).
  var thread = document.getElementById("thread");
  if (!thread) return;
  var exhibit = parseInt(thread.dataset.exhibit, 10);
  var form = document.getElementById("cb-comment-form");
  var body = document.getElementById("cb-comment-body");
  var replying = document.getElementById("cb-replying");
  var replyingTo = document.getElementById("cb-replying-to");
  var error = document.getElementById("cb-comment-error");
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
    } else if (e.target.id === "cb-replying-cancel") {
      replyTo = null;
      replying.hidden = true;
    } else if (del) {
      if (!window.confirm("למחוק את התגובה?")) return;
      api("DELETE", "comments/" + del.dataset.delete + "/").then(function () { location.reload(); }).catch(function (err) { fail(err.message); });
    } else if (edit) {
      var n = edit.closest("[data-comment]");
      var p = n.querySelector(".cb-note-body");
      if (n.querySelector(".cb-edit-box")) return;
      var box = document.createElement("div");
      box.className = "cb-edit-box";
      var ta = document.createElement("textarea");
      ta.rows = 3; ta.maxLength = 2000; ta.value = p.innerText;
      ta.setAttribute("aria-label", "עריכת התגובה");
      var save = document.createElement("button");
      save.type = "button"; save.className = "cb-btn"; save.textContent = "שמירה";
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
    if (!text) { fail("התגובה ריקה."); return; }
    var submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    api("POST", "comments/", { exhibit: exhibit, body: text, reply_to: replyTo }).then(function (c) {
      location.hash = "c" + c.id;
      location.reload();
    }).catch(function (err) { fail(err.message); submit.disabled = false; });
  });
})();
