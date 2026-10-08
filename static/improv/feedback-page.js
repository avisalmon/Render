// improv: the Feedback screen. Browser glue only: send one note, list the notes already sent.
// Only text is ever put on the page.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const host = $("feedback");
  if (!host) return;
  const api = host.dataset.apiFeedback;
  const from = host.dataset.from || "";
  const KINDS = { idea: "Idea", problem: "Problem", praise: "Liked", other: "Other" };
  let sending = false;

  function make(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function showError(text) {
    $("fb-error").textContent = text;
    $("fb-error").hidden = !text;
  }

  function row(item) {
    const li = make("li");
    li.appendChild(make("span", `${KINDS[item.kind] || item.kind}: `, "im-note"));
    li.appendChild(make("span", item.message));
    return li;
  }

  function show(items) {
    const list = $("fb-list");
    list.textContent = "";
    for (const item of items) list.appendChild(row(item));
    $("fb-empty").hidden = items.length > 0;
  }

  function headers() {
    return { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": host.dataset.csrf };
  }

  async function load() {
    try {
      const response = await fetch(api, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) return;
      const body = await response.json();
      show(Array.isArray(body) ? body : body.results || []);
    } catch (error) {
      /* the list is a courtesy; sending still works */
    }
  }

  async function send() {
    if (sending) return;
    const message = $("fb-message").value.trim();
    showError("");
    if (!message) {
      showError("Write a few words first.");
      return;
    }
    sending = true;
    $("fb-send").disabled = true;
    try {
      const response = await fetch(api, {
        method: "POST",
        credentials: "same-origin",
        headers: headers(),
        body: JSON.stringify({ kind: $("fb-kind").value, message, page: from.slice(0, 200) }),
      });
      if (response.ok) {
        $("fb-message").value = "";
        $("fb-count").textContent = "0 / 2000";
        $("fb-status").textContent = "Thank you. That reached us.";
        await load();
      } else {
        let detail = "";
        try {
          const body = await response.json();
          detail = body.detail || (body.message && body.message[0]) || "";
        } catch (error) {
          detail = "";
        }
        showError(detail || "That did not go through. Please try again.");
      }
    } catch (error) {
      showError("No connection. Please try again.");
    } finally {
      sending = false;
      $("fb-send").disabled = false;
    }
  }

  $("fb-send").addEventListener("click", send);
  $("fb-message").addEventListener("input", () => {
    $("fb-count").textContent = `${$("fb-message").value.length} / 2000`;
  });
  load();
})();
