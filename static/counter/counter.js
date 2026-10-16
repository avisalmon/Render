// Dashboard behaviour: the page is one consumer of the REST API (Rule 6).
(function () {
  var csrf = document.body.getAttribute("data-csrf");

  function api(method, url, body) {
    return fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      credentials: "same-origin",
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      if (r.status === 204) return {};
      return r.json().then(function (d) { if (!r.ok) throw d; return d; });
    });
  }

  function fail(form, err) {
    var box = form.querySelector("[data-form-error]");
    box.textContent = typeof err === "object" ? JSON.stringify(err) : String(err);
    box.hidden = false;
  }

  function fields(form) {
    var out = {};
    new FormData(form).forEach(function (v, k) { out[k] = v; });
    var active = form.querySelector("[name=is_active]");
    if (active) out.is_active = active.checked;
    return out;
  }

  var add = document.querySelector("[data-site-form]");
  if (add) add.addEventListener("submit", function (e) {
    e.preventDefault();
    api("POST", "/counter/api/sites/", fields(add)).then(function (s) {
      location.href = "/counter/sites/" + s.id + "/";
    }).catch(function (err) { fail(add, err); });
  });

  var edit = document.querySelector("[data-site-edit]");
  if (edit) {
    var url = "/counter/api/sites/" + edit.getAttribute("data-site-id") + "/";
    edit.addEventListener("submit", function (e) {
      e.preventDefault();
      api("PATCH", url, fields(edit)).then(function () { location.reload(); })
        .catch(function (err) { fail(edit, err); });
    });
    edit.querySelector("[data-site-delete]").addEventListener("click", function () {
      if (!confirm("Delete this site and every count it has? This cannot be undone.")) return;
      api("DELETE", url).then(function () { location.href = "/counter/"; })
        .catch(function (err) { fail(edit, err); });
    });
  }
})();
