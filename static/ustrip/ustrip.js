/* ustrip's REST layer (docs/ustrip/spec.md §0b): every write a page makes
 * goes through /ustrip/api/... via fetch, and the page updates itself from
 * the JSON response instead of reloading. One tiny helper, no framework. */
(function () {
  function request(url, { json, formData } = {}) {
    const opts = { method: "POST", headers: { "X-CSRFToken": document.body.dataset.csrf } };
    if (formData) {
      opts.body = formData;
    } else {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(json || {});
    }
    return fetch(url, opts).then(async (res) => {
      let data = {};
      try {
        data = await res.json();
      } catch (e) {
        /* empty/non-JSON body — leave data as {} */
      }
      if (!res.ok) throw Object.assign(new Error(data.error || "Something went wrong"), { data, status: res.status });
      return data;
    });
  }

  function el(html) {
    const wrap = document.createElement("div");
    wrap.innerHTML = html.trim();
    return wrap.firstElementChild;
  }

  window.ustrip = { request, el };
})();
