/* exo's small shared helpers.
 *
 * Deliberately one file with no framework and no build step. A five-screen
 * journey needs the page not to reload when someone taps a checkbox; it does
 * not need a bundler. Same call ustrip made, and the same reasoning.
 */
(function () {
  "use strict";

  const csrf = () => document.body.getAttribute("data-csrf") || "";

  /**
   * fetch with the CSRF token attached, that THROWS on a non-2xx.
   *
   * The throw is the point: `fetch` resolves happily on a 500, so code that
   * forgets to check `response.ok` treats a server error as success and shows
   * the user nothing. Every caller in this app gets the error instead.
   */
  async function api(url, options) {
    const opts = Object.assign({ method: "GET", headers: {} }, options || {});
    opts.headers = Object.assign(
      {
        "X-CSRFToken": csrf(),
        "X-Requested-With": "XMLHttpRequest",
      },
      opts.headers
    );
    if (opts.json !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
      delete opts.json;
    }
    const response = await fetch(url, opts);
    if (!response.ok) {
      let detail = "";
      try {
        detail = (await response.json()).detail || "";
      } catch (e) {
        /* a non-JSON error body is still an error */
      }
      const error = new Error(detail || "HTTP " + response.status);
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    const type = response.headers.get("content-type") || "";
    return type.includes("application/json") ? response.json() : response.text();
  }

  /** A brief, non-blocking message. Never `alert()`, which blocks the page. */
  function toast(message, kind) {
    let host = document.querySelector(".exo-toasts");
    if (!host) {
      host = document.createElement("div");
      host.className = "exo-toasts";
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = "exo-toast" + (kind ? " exo-toast-" + kind : "");
    el.setAttribute("role", "status");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => {
      el.classList.add("is-going");
      setTimeout(() => el.remove(), 250);
    }, 3200);
  }

  window.exo = { api, toast, csrf };
})();
