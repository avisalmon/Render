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

  var KNOWN = ["accelerometer", "linear-accelerometer", "gyroscope", "magnetometer"];
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

    if (!isKnown(name) || !anyAvailable()) {
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

  window.sensorlab = window.sensorlab || {};
  window.sensorlab.sensors = {
    probe: probe,
    record: record,
    openCount: openCount,
    known: KNOWN.slice()
  };
})(window);
