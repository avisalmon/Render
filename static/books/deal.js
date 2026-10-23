/* The request as a conversation (Avi, 2026-10-23): messages are sent without
   a page reload and new ones arrive on their own; the composer stays at the
   bottom. Without script the form still posts. */
(function () {
  "use strict";
  var chat = document.querySelector("[data-chat]");
  if (!chat) return;
  var csrf = document.body.getAttribute("data-csrf");
  var list = chat.querySelector("[data-chat-list]");
  var form = chat.querySelector("[data-chat-form]");
  var empty = chat.querySelector("[data-chat-empty]");
  var me = chat.getAttribute("data-me");
  var last = parseInt(chat.getAttribute("data-last") || "0", 10) || 0;

  var bubble = function (m) {
    var p = document.createElement("p");
    p.className = "bk-bubble" + (String(m.sender) === me ? " bk-bubble--mine" : "");
    p.setAttribute("data-message", m.id);
    var body = document.createElement("span");
    body.className = "bk-bubble-body";
    body.textContent = m.body;
    var meta = document.createElement("span");
    meta.className = "bk-bubble-meta";
    meta.textContent = m.when;
    p.appendChild(body); p.appendChild(meta);
    return p;
  };
  var add = function (rows) {
    var grew = false;
    rows.forEach(function (m) {
      if (m.id <= last || list.querySelector('[data-message="' + m.id + '"]')) return;
      list.appendChild(bubble(m));
      last = Math.max(last, m.id);
      grew = true;
    });
    if (grew) {
      if (empty) empty.hidden = true;
      list.scrollTop = list.scrollHeight;
    }
    return grew;
  };
  var fetchNew = function () {
    return fetch(chat.getAttribute("data-url") + "?after=" + last, {headers: {"Accept": "application/json"}})
      .then(function (r) { return r.ok ? r.json() : {messages: []}; })
      .then(function (d) { return add(d.messages || []); })
      .catch(function () { return false; });
  };

  if (form) {
    var field = form.querySelector("[name=body]");
    var send = form.querySelector("[data-chat-send]");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = (field.value || "").trim();
      if (!text) { field.focus(); return; }
      send.disabled = true;
      var fd = new FormData(form);
      fetch(form.getAttribute("action"), {method: "POST", body: fd, headers: {"Accept": "application/json", "X-CSRFToken": csrf}})
        .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
        .then(function (res) {
          send.disabled = false;
          if (!res.ok) { form.submit(); return; }
          field.value = "";
          field.style.height = "";
          return fetchNew();
        })
        .catch(function () { send.disabled = false; form.submit(); });
    });
    // Enter sends on a computer; on a phone the keyboard's Enter makes a new line.
    field.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && window.matchMedia("(pointer: fine)").matches) {
        e.preventDefault();
        form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", {cancelable: true}));
      }
    });
    field.addEventListener("input", function () {
      field.style.height = "auto";
      field.style.height = Math.min(140, field.scrollHeight) + "px";
    });
  }

  list.scrollTop = list.scrollHeight;
  var every = parseInt(chat.getAttribute("data-every") || "15000", 10);
  setInterval(function () { if (document.visibilityState === "visible") fetchNew(); }, every);
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") fetchNew(); });
  window.bkChat = {fetchNew: fetchNew};
})();
