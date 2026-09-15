/* memz — the shared page helper (spec Rule 12.3.2): pages are consumers of
   the API. One CSRF read, one fetch wrapper that throws on a non-2xx, and
   a player-token hook for the game (SPR-Z.3). Nothing else lives here. */
(function () {
  "use strict";

  var csrf = document.body.getAttribute("data-csrf") || "";

  // A token is scoped to the one session it was issued for (spec Rule
  // 3.1.3), so the storage key carries the room code.
  function tokenKey(code) { return "memz.player." + String(code || "").toUpperCase(); }

  function getPlayerToken(code) {
    try {
      return window.localStorage.getItem(tokenKey(code)) || "";
    } catch (e) {
      return "";
    }
  }

  function setPlayerToken(code, token) {
    try {
      window.localStorage.setItem(tokenKey(code), token);
    } catch (e) { /* private mode or full storage: the tab still works this visit */ }
  }

  async function api(method, url, body, playerToken) {
    var headers = { "Accept": "application/json", "X-CSRFToken": csrf };
    if (playerToken) headers["X-Memz-Player"] = playerToken;
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

  window.memz = { csrf: csrf, api: api, getPlayerToken: getPlayerToken, setPlayerToken: setPlayerToken };
})();
