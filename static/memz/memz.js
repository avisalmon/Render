/* memz — the shared page helper (spec Rule 12.3.2): pages are consumers of
   the API. One CSRF read, one fetch wrapper that throws on a non-2xx, and
   a player-token hook for the game (SPR-Z.3). Nothing else lives here. */
(function () {
  "use strict";

  var csrf = document.body.getAttribute("data-csrf") || "";

  function playerToken() {
    try {
      return window.localStorage.getItem("memz.player") || "";
    } catch (e) {
      return "";
    }
  }

  async function api(method, url, body) {
    var headers = { "Accept": "application/json", "X-CSRFToken": csrf };
    var token = playerToken();
    if (token) headers["X-Memz-Player"] = token;
    var options = { method: method, headers: headers, credentials: "same-origin" };
    if (body instanceof FormData) {
      options.body = body;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    var response = await fetch(url, options);
    var data = null;
    var type = response.headers.get("Content-Type") || "";
    if (type.indexOf("application/json") === 0) data = await response.json();
    if (!response.ok) {
      var error = new Error("memz api " + response.status + " " + url);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  window.memz = { csrf: csrf, api: api, playerToken: playerToken };
})();
