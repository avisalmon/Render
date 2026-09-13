/* ustrip's REST layer (building_an_app.md Rule 6): every write a page makes
 * goes through the DRF API at /ustrip/api/... via fetch, and the page
 * updates itself from the JSON response instead of reloading. One tiny
 * helper, no framework. */
(function () {
  function request(url, { method, json, formData } = {}) {
    var opts = { method: method || (formData || json !== undefined ? "POST" : "GET") };
    opts.headers = { "X-CSRFToken": document.body.dataset.csrf };
    if (formData) {
      opts.body = formData;
    } else if (json !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(json);
    }
    return fetch(url, opts).then(async (res) => {
      let data = {};
      try {
        data = await res.json();
      } catch (e) {
        /* empty/non-JSON body (e.g. a 204 from DELETE) — leave data as {} */
      }
      if (!res.ok) {
        var message = data.detail || data.error || firstFieldError(data) || "Something went wrong";
        throw Object.assign(new Error(message), { data: data, status: res.status });
      }
      return data;
    });
  }

  function firstFieldError(data) {
    // DRF validation errors come back as {field: ["message", ...]}.
    for (var key in data) {
      if (Array.isArray(data[key]) && data[key].length) return data[key][0];
    }
    return null;
  }

  function el(html) {
    const wrap = document.createElement("div");
    wrap.innerHTML = html.trim();
    return wrap.firstElementChild;
  }

  window.ustrip = { request: request, el: el };
})();
