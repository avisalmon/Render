// Academia360: pages work with JavaScript off; this file only enhances.
(function () {
  "use strict";
  document.documentElement.classList.add("a360-js");

  // The map of the institutions (B.2): a layer over the list, drawn from the
  // same rows the page printed. Without Leaflet or without rows, nothing.
  var COLOURS = { university: "#1E7C88", academic_college: "#F6C21A", teacher_training: "#EE6B67", research_institute: "#8FC457" };
  var mapNode = document.getElementById("a360-map");
  var dataNode = document.getElementById("a360-map-data");
  var map = null;

  function draw() {
    if (!mapNode || !dataNode || typeof L === "undefined" || map) return;
    var rows;
    try { rows = JSON.parse(dataNode.textContent || "[]"); } catch (e) { return; }
    if (!rows.length) return;
    map = L.map(mapNode, { scrollWheelZoom: false, attributionControl: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, className: "a360-tiles",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);
    var bounds = [];
    rows.forEach(function (r) {
      var colour = r.applied ? (COLOURS[r.kind] || "#323435") : "#B7BABA";
      var m = L.circleMarker([r.lat, r.lng], { radius: 8, color: "#fff", weight: 2, fillColor: colour, fillOpacity: 0.95 }).addTo(map);
      var city = r.city ? " · " + r.city : "";
      m.bindPopup('<a href="' + r.url + '">' + r.name + "</a>" + city + (r.applied ? "" : "<br><small>לא ניגש למחזור תשפ״ה</small>"));
      m.on("mouseover", function () { m.setRadius(11); }).on("mouseout", function () { m.setRadius(8); });
      bounds.push([r.lat, r.lng]);
    });
    map.fitBounds(bounds, { padding: [24, 24], maxZoom: 11 });
  }

  var toggle = document.getElementById("a360-map-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var grid = toggle.closest(".a360-mapgrid");
      var open = grid.classList.toggle("a360-map-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.textContent = open ? "בלי המפה" : "המפה";
      if (open) { draw(); if (map) { setTimeout(function () { map.invalidateSize(); }, 50); } }
    });
  }

  // On a phone the kind chips start folded unless a kind is chosen (mistake 84).
  var tools = document.querySelector(".a360-tools");
  if (tools && window.innerWidth < 900 && !tools.dataset.active) tools.open = false;

  // On a phone the tab row may scroll; the current tab comes into view.
  var current = document.querySelector(".a360-nav [aria-current]");
  if (current && window.innerWidth < 700 && current.scrollIntoView) current.scrollIntoView({ inline: "center", block: "nearest" });

  if (document.readyState === "complete") draw();
  else window.addEventListener("load", draw);
})();
