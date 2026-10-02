/* The learning screen's videos: a card is a link to YouTube, and pressing it
   swaps the card for the player in place.

   Until then the page has asked YouTube for nothing but a preview picture, and
   with this script missing the card is still a working link. Opening in a new
   tab with a modifier key held is left to the browser.

   The frame carries its own referrer policy. Django sends none to another
   origin by default, and YouTube refuses to play inside a frame that arrives
   without one. */

(function () {
  "use strict";

  document.addEventListener("click", function (event) {
    var link = event.target.closest(".bj-clip-play");
    if (!link) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button) return;

    var card = link.closest(".bj-clip");
    if (!card || !card.dataset.embed) return;
    event.preventDefault();

    var frame = document.createElement("iframe");
    frame.src = card.dataset.embed;
    frame.title = card.dataset.title || "";
    frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    frame.setAttribute("allowfullscreen", "");
    frame.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
    frame.className = "bj-clip-frame";

    var box = document.createElement("div");
    box.className = "bj-clip-player";
    box.appendChild(frame);

    link.replaceWith(box);
    frame.focus();
  });
})();
