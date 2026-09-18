/* SensorLab — the sensor layer (SL-C1, spec §4.1, §9.3).
 *
 * One way to open a sensor, read it, and stop it. No lab talks to
 * `devicemotion` or `new Accelerometer` directly; a test enforces that.
 *
 * Three things the spike on a real phone taught, which this module exists
 * to encode so no lab has to remember them:
 *
 * 1. THE RATE IS MEASURED, NEVER DECLARED. The spec assumed 200 Hz; the
 *    device delivered ~63. A lab asks for a rate, the device gives what it
 *    gives, and the recording stores what actually arrived. A recording
 *    that stores the requested figure is storing a wish.
 *
 * 2. "AVAILABLE" AND "WORKING" ARE DIFFERENT CLAIMS. On a desktop with no
 *    accelerometer, `DeviceMotionEvent` reports available and then fires
 *    nothing, forever. So `probe()` returns three states — present, absent,
 *    and present-but-silent — because only the third looks like success.
 *
 * 3. TWO APIS, ONE SHAPE. The Generic Sensor API is the only route past
 *    ~60 Hz; `devicemotion` is the fallback that works everywhere. Readings
 *    come out identical either way, so analysis never branches on source.
 *
 * TEST SEAM, stated rather than hidden: the `window.__slFake*` globals
 * below let a browser test stand in a fake source. This is deliberate. The
 * silent-sensor case cannot be reproduced on a device where the sensor
 * works, and no CI machine has an accelerometer at all — so without a seam
 * the most important behaviour here would be the least tested. The seam is
 * inert unless a test sets it.
 */
(function (window) {
  "use strict";

  /* Motion sensors, which this module reads directly. */
  var MOTION = ["accelerometer", "linear-accelerometer", "gyroscope", "magnetometer"];

  /* Media devices, whose PRESENCE is knowable without reading anything:
     enumerateDevices() reports kinds with empty labels and no permission.
     Knowing the hardware is there is not knowing it works, which is why
     these resolve to "present" rather than "working" — see probe(). */
  var MEDIA = {camera: "videoinput", microphone: "audioinput"};

  var KNOWN = MOTION.concat(Object.keys(MEDIA));
  var openSensors = 0;

  function now() {
    return window.performance && window.performance.now ? window.performance.now() : Date.now();
  }

  function reading(t, x, y, z) {
    var vx = x || 0, vy = y || 0, vz = z || 0;
    return {t: t, x: vx, y: vy, z: vz, magnitude: Math.sqrt(vx * vx + vy * vy + vz * vz)};
  }

  // ---------------------------------------------------------- sources

  /* A source is: {name, start(onReading), stop()}. Nothing above this line
     knows which API is underneath. */

  function fakeSource(name) {
    var fake = window.__slFakeMotion;
    if (!fake) return null;
    var timer = null;
    return {
      name: name,
      start: function (onReading) {
        if (!fake.fires) return;                    // present, and silent
        var hz = fake.hz || 50;
        var mag = fake.magnitude === undefined ? 9.81 : fake.magnitude;
        timer = window.setInterval(function () {
          onReading(reading(now(), 0, 0, mag));
        }, 1000 / hz);
      },
      stop: function () { if (timer) window.clearInterval(timer); timer = null; }
    };
  }

  function genericAvailable() {
    return window.__slFakeGeneric === true || typeof window.Accelerometer !== "undefined";
  }

  function genericSource(requestHz) {
    var fake = fakeSource("generic");
    if (fake) return fake;                          // test seam
    var sensor = null;
    return {
      name: "generic",
      start: function (onReading) {
        sensor = new window.Accelerometer({frequency: requestHz || 60});
        sensor.addEventListener("reading", function () {
          onReading(reading(now(), sensor.x, sensor.y, sensor.z));
        });
        sensor.start();
      },
      stop: function () { if (sensor) { try { sensor.stop(); } catch (e) { /* already gone */ } } sensor = null; }
    };
  }

  function motionAvailable() {
    return !!window.__slFakeMotion || typeof window.DeviceMotionEvent !== "undefined";
  }

  function motionSource() {
    var fake = fakeSource("devicemotion");
    if (fake) return fake;                          // test seam
    var handler = null;
    return {
      name: "devicemotion",
      start: function (onReading) {
        handler = function (e) {
          var a = e.accelerationIncludingGravity || {};
          if (a.x === null || a.x === undefined) return;
          onReading(reading(now(), a.x, a.y, a.z));
        };
        window.addEventListener("devicemotion", handler);
      },
      stop: function () {
        if (handler) window.removeEventListener("devicemotion", handler);
        handler = null;
      }
    };
  }

  /* Generic first, deliberately: §4.1 measured devicemotion at ~63 Hz, and
     the Generic Sensor API is the only route to more when a lab needs it.
     The module chooses; the lab does not. */
  function sourceFor(requestHz) {
    var forced = window.__slForceSource;
    if (forced === "devicemotion") return motionSource();
    if (forced === "generic") return genericSource(requestHz);
    if (genericAvailable()) return genericSource(requestHz);
    if (motionAvailable()) return motionSource();
    return null;
  }

  function isKnown(name) {
    return KNOWN.indexOf(name) !== -1;
  }

  /* Is the hardware there? Answered without opening anything, so it costs
     the person nothing and reveals nothing. */
  function mediaPresent(name) {
    var kind = MEDIA[name];
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
      return Promise.resolve(false);
    }
    return navigator.mediaDevices.enumerateDevices().then(function (devices) {
      return devices.some(function (d) { return d.kind === kind; });
    }).catch(function () { return false; });
  }

  function anyAvailable() {
    return genericAvailable() || motionAvailable();
  }

  // ------------------------------------------------------------- api

  /**
   * What this device will actually do for this sensor.
   *
   * Resolves {available, working, state}, where state is one of
   * "absent" | "silent" | "working". The middle one is the whole point:
   * an interface that exists and never delivers is not a sensor.
   */
  function probe(name, options) {
    var settings = options || {};
    var timeoutMs = settings.timeoutMs || 1200;

    if (!isKnown(name)) {
      return Promise.resolve({available: false, working: false, state: "absent", source: null});
    }

    /* A camera or microphone. Its presence is a fact we can check; whether
       it *works* needs permission and an open stream, which this call does
       not do. So the honest answer is "present" — neither "working" (we
       have not looked) nor "absent" (it is right there). Calling it absent
       was a real bug: the screen told a machine with a camera that it had
       none. */
    if (MEDIA[name]) {
      return mediaPresent(name).then(function (there) {
        return {
          available: there,
          working: false,
          state: there ? "present" : "absent",
          source: there ? "media-devices" : null
        };
      });
    }

    if (!anyAvailable()) {
      return Promise.resolve({available: false, working: false, state: "absent", source: null});
    }

    var source = sourceFor(settings.requestHz);
    if (!source) {
      return Promise.resolve({available: false, working: false, state: "absent", source: null});
    }

    return new Promise(function (resolve) {
      var settled = false;
      openSensors += 1;

      function finish(working) {
        if (settled) return;
        settled = true;
        try { source.stop(); } finally { openSensors -= 1; }
        resolve({
          available: true,
          working: working,
          state: working ? "working" : "silent",
          source: source.name
        });
      }

      try {
        source.start(function () { finish(true); });
      } catch (err) {
        return finish(false);
      }
      window.setTimeout(function () { finish(false); }, timeoutMs);
    });
  }

  /**
   * Record for a while, and report what actually arrived.
   *
   * Resolves {samples, source, requestedHz, achievedHz, durationMs}. Both
   * rates are kept on purpose: the difference between them is a fact about
   * this device, and §4.1 exists because that difference was 3x.
   */
  function record(name, options) {
    var settings = options || {};
    var ms = settings.ms || 1000;
    var requestedHz = settings.requestHz || 60;
    var source = sourceFor(requestedHz);

    if (!source) {
      return Promise.resolve({
        samples: [], source: null, requestedHz: requestedHz, achievedHz: 0, durationMs: 0
      });
    }

    return new Promise(function (resolve) {
      var samples = [];
      openSensors += 1;
      var startedAt = now();

      source.start(function (r) { samples.push(r); });

      window.setTimeout(function () {
        try { source.stop(); } finally { openSensors -= 1; }
        var elapsed = now() - startedAt;
        // Measured from the samples themselves where there are enough of
        // them, so a slow start does not flatter the figure.
        var span = samples.length > 1 ? samples[samples.length - 1].t - samples[0].t : elapsed;
        var achieved = span > 0 ? ((samples.length - 1) * 1000) / span : 0;
        resolve({
          samples: samples,
          source: source.name,
          requestedHz: requestedHz,
          achievedHz: Math.round(achieved * 10) / 10,
          durationMs: Math.round(elapsed)
        });
      }, ms);
    });
  }

  function openCount() {
    return openSensors;
  }

  // ------------------------------------------------------- consent (C2)

  /* The gate this app imposes on itself.
   *
   * On Android the browser asks nothing: a page may read the accelerometer
   * the moment it loads, which the spike confirmed and which is precisely
   * the exposure spec §2 names. So the refusal below is not the platform's
   * — it is ours, and it has to bite before a single reading is taken, or
   * it is decoration and the data was already collected by the time anyone
   * saw a dialog. A test asserts exactly that.
   */

  var consented = {};

  function hasConsent(name) {
    return consented[name] === true;
  }

  function grant(name) {
    consented[name] = true;
    // Recorded server-side too, so it survives this browser and can be
    // withdrawn from the sensors screen. A failure here must not pretend
    // the person did not agree in front of us.
    return fetch("/sensorlab/api/sensor-consent/", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
      body: JSON.stringify({sensor: name})
    }).catch(function () { /* the local grant stands for this session */ })
      .then(function () { return true; });
  }

  function csrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
  }

  function loadConsent() {
    return fetch("/sensorlab/api/sensor-consent/", {headers: {Accept: "application/json"}})
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (state) {
        Object.keys(state || {}).forEach(function (name) {
          if (state[name] && state[name].granted) consented[name] = true;
        });
        return consented;
      })
      .catch(function () { return consented; });
  }

  /**
   * Read a sensor, but only with permission.
   *
   * Resolves one of:
   *   {state: "absent"}        — this device has no such sensor
   *   {state: "silent"}        — the interface is there and answers nothing
   *   {state: "needs-consent"} — nothing was read; ask, then call again
   *   {state: "ok", ...run}    — the recording, shaped as record() returns
   *
   * The three refusals are kept apart because a student deserves the true
   * sentence: "your phone does not have this" and "your phone has it and it
   * is not answering" are not the same problem (spec §1 — no degradation
   * tier, so the refusal has to carry the reason).
   */
  function request(name, options) {
    var settings = options || {};
    if (!isKnown(name)) {
      return Promise.resolve({state: "absent", samples: []});
    }
    if (!hasConsent(name)) {
      return Promise.resolve({state: "needs-consent", samples: []});
    }
    return probe(name, {timeoutMs: settings.probeMs || 700}).then(function (verdict) {
      if (verdict.state !== "working") {
        return {state: verdict.state, samples: []};
      }
      return record(name, settings).then(function (run) {
        run.state = "ok";
        return run;
      });
    });
  }

  window.sensorlab = window.sensorlab || {};
  window.sensorlab.sensors = {
    probe: probe,
    record: record,
    request: request,
    grant: grant,
    hasConsent: hasConsent,
    loadConsent: loadConsent,
    openCount: openCount,
    known: KNOWN.slice(),
    // Test seam, as documented at the top of this file.
    __resetConsent: function () { consented = {}; }
  };
})(window);
