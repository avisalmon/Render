/* The history graph's readout: touch, hover or arrow across the plot and the
   line under it says the exact percentage and time of the nearest batch.

   The numbers on the dots and the dates on the axis are already in the page,
   so with this script missing the graph is complete except for the readout. */

(function () {
  "use strict";

  var plot = document.querySelector(".bj-plot");
  if (!plot) return;

  var dots = Array.prototype.slice.call(plot.querySelectorAll(".bj-dot"));
  var readout = document.querySelector(".bj-graph-readout");
  var inner = plot.querySelector(".bj-plot-in");
  var picked = dots.length - 1;

  function pick(index) {
    index = Math.max(0, Math.min(dots.length - 1, index));
    picked = index;
    dots.forEach(function (dot, at) {
      dot.classList.toggle("is-picked", at === index);
    });
    var dot = dots[index];
    var parts = dot.dataset.at.split(" ");
    readout.textContent = "";
    var strong = document.createElement("strong");
    strong.textContent = dot.dataset.pct + "%";
    readout.appendChild(strong);
    readout.appendChild(
      document.createTextNode(" ב" + parts[0] + " בשעה " + parts[1])
    );
  }

  function nearest(clientX) {
    var box = inner.getBoundingClientRect();
    var share = (clientX - box.left) / box.width;
    return Math.round(share * (dots.length - 1));
  }

  plot.addEventListener("pointerdown", function (event) {
    pick(nearest(event.clientX));
  });
  plot.addEventListener("pointermove", function (event) {
    if (event.pointerType === "mouse" || event.buttons) pick(nearest(event.clientX));
  });

  plot.addEventListener("keydown", function (event) {
    var step = { ArrowLeft: -1, ArrowRight: 1, Home: -dots.length, End: dots.length }[event.key];
    if (!step) return;
    event.preventDefault();
    pick(picked + step);
  });
})();
