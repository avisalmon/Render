// improv: draws the chord guide's keyboard and words. Browser only, and only text goes in, never
// markup. The keys are the same ones the live keyboard draws; this only colours them by role.
(function () {
  "use strict";
  const Keys = window.ImprovKeyboardView;
  const Guide = window.ImprovChordGuide;
  const ROLES = ["im-g-scale", "im-g-p1", "im-g-p2", "im-g-p3"];

  function draw(host) {
    return Keys.draw(host, Guide.FIRST, Guide.LAST);
  }

  // guide is what ImprovChordGuide.guideFor returns, or null to clear.
  function show(keys, guide) {
    for (const key of keys.values()) {
      key.classList.remove(...ROLES);
      key.textContent = "";
    }
    if (!guide) return;
    for (const [note, info] of guide.keys) {
      const key = keys.get(note);
      if (!key) continue;
      key.classList.add("im-g-" + info.role);
      if (info.label) {
        const tag = document.createElement("span");
        tag.className = "im-key-step";
        tag.textContent = info.label;
        key.appendChild(tag);
      }
    }
  }

  window.ImprovChordGuideView = { draw, show };
})();
