/* counter snippet. Served at /counter/c.js, so a page needs only:
 *
 *   <script defer src="https://babook.co.il/counter/c.js" data-site="KEY"></script>
 *
 * It records one view per page load and fills any element carrying
 * data-counter="views" or data-counter="uniques" with that page's number
 * (data-counter-scope="site" for the whole site). An element with
 * data-counter-click="name" records a click event. counter.track("name")
 * records a custom event from your own code. No cookies; the anonymous
 * visitor id lives in localStorage.
 */
(function () {
  var script = document.currentScript;
  if (!script) return;
  var key = script.getAttribute("data-site");
  if (!key) return;
  var base = script.src.replace(/\/c\.js(\?.*)?$/, "");
  var local = /^(localhost|127\.0\.0\.1|)$/.test(location.hostname) && !script.hasAttribute("data-allow-local");

  function visitor() {
    try {
      var v = localStorage.getItem("counter_vid");
      if (!v) {
        v = Math.random().toString(36).slice(2) + Date.now().toString(36);
        localStorage.setItem("counter_vid", v);
      }
      return v;
    } catch (e) {
      return "";
    }
  }

  function send(extra) {
    var body = {
      key: key,
      path: location.pathname,
      title: document.title,
      referrer: document.referrer,
      visitor: visitor()
    };
    for (var k in extra) body[k] = extra[k];
    // text/plain keeps this a "simple" request: no CORS preflight.
    return fetch(base + "/api/hit/", {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: JSON.stringify(body),
      keepalive: true
    }).then(function (r) { return r.json(); });
  }

  function siteFill() {
    var els = document.querySelectorAll('[data-counter][data-counter-scope="site"]');
    if (!els.length) return;
    fetch(base + "/api/stats/" + key + "/").then(function (r) { return r.json(); }).then(function (d) {
      for (var i = 0; i < els.length; i++) {
        var n = d[els[i].getAttribute("data-counter")];
        if (n !== undefined) els[i].textContent = n;
      }
    }).catch(function () {});
  }

  window.counter = {
    track: function (name) { return local ? Promise.resolve() : send({ kind: "custom", name: name }).catch(function () {}); }
  };

  function start() {
    document.addEventListener("click", function (e) {
      var el = e.target.closest && e.target.closest("[data-counter-click]");
      if (el && !local) send({ kind: "click", name: el.getAttribute("data-counter-click") }).catch(function () {});
    });
    var send_view = local
      ? fetch(base + "/api/stats/" + key + "/?path=" + encodeURIComponent(location.pathname)).then(function (r) { return r.json(); })
      : send({ kind: "view" });
    send_view.then(function (d) {
      // Page-scope counters only; site-scope ones were filled above.
      var els = document.querySelectorAll("[data-counter]:not([data-counter-scope='site'])");
      for (var i = 0; i < els.length; i++) {
        var n = d[els[i].getAttribute("data-counter")];
        if (n !== undefined) els[i].textContent = n;
      }
    }).catch(function () {}).then(siteFill);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
