// improv: which audio outputs the player can send the band to. Pure: the device list is handed
// in, so it runs under Node in the tests and on the page with navigator.mediaDevices.
//
// Browsers keep an output's name hidden until the site has a microphone permission, and the
// page never asks for one, so a name may be empty; those outputs are numbered instead.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovOutput = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const DEFAULT_LABEL = "System default";
  const VIRTUAL = ["default", "communications"];

  const isOutput = (d) => d && d.kind === "audiooutput";
  const nameOf = (d) => String(d.label || "").trim();

  // Chrome lists the system default as its own entry, "Default - Speakers"; its name is the
  // useful part, so it labels the first choice instead of being listed twice.
  function defaultLabel(devices) {
    const own = (devices || []).find((d) => isOutput(d) && d.deviceId === "default" && nameOf(d));
    if (!own) return DEFAULT_LABEL;
    const name = nameOf(own).replace(/^default\s*-\s*/i, "");
    return name ? `${DEFAULT_LABEL}: ${name}` : DEFAULT_LABEL;
  }

  function choices(devices) {
    const list = [{ id: "", label: defaultLabel(devices) }];
    let n = 0;
    for (const d of devices || []) {
      if (!isOutput(d) || VIRTUAL.includes(d.deviceId)) continue;
      n += 1;
      list.push({ id: d.deviceId, label: nameOf(d) || `Output ${n}` });
    }
    return list;
  }

  function hasNames(devices) {
    return (devices || []).some((d) => isOutput(d) && nameOf(d));
  }

  function stillThere(list, id) {
    return id === "" || list.some((c) => c.id === id);
  }

  // Chrome and Edge can send an AudioContext to a chosen output; Safari and Firefox cannot.
  function supported(contextPrototype, mediaDevices) {
    return Boolean(
      contextPrototype && typeof contextPrototype.setSinkId === "function" &&
      mediaDevices && typeof mediaDevices.enumerateDevices === "function"
    );
  }

  return { choices, hasNames, stillThere, supported, DEFAULT_LABEL };
});
