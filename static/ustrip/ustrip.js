/* ustrip's REST layer (building_an_app.md Rule 6): every write a page makes
 * goes through the DRF API at /ustrip/api/... via fetch, and the page
 * updates itself from the JSON response instead of reloading. One tiny
 * helper, no framework — plus a pointer-based sortable for the itinerary's
 * drag-and-drop (spec §4.1), written by hand because HTML5 drag events do
 * not fire for touch on the phones this app is for. */
(function () {
  /* Spec §0a.1: a control that has fired a request is disabled until it comes
   * back, so a second tap on hotel wifi cannot post a second journal entry.
   *
   * Rather than make every call site remember, a capture-phase submit listener
   * notes which button is submitting; the request() that the page's own handler
   * fires a moment later picks it up. Explicit `busy: el` covers buttons that
   * are not form submits. The note is cleared on the next task so a handler
   * that bails out early (failed validation) never leaves it armed for
   * whatever request happens next. */
  var pendingSubmitter = null;

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || !form.querySelector) return;
    pendingSubmitter = form.querySelector("button[type=submit], button:not([type])");
    setTimeout(function () { pendingSubmitter = null; }, 0);
  }, true);

  /* hold(el) -> release(). Safe to nest: only the outermost hold re-enables,
   * so a caller that holds a button across an async resize *and* passes the
   * same button to request() does not get it re-enabled half way through. */
  function hold(control) {
    if (!control) return function () {};
    var depth = (control._ustripHolds || 0) + 1;
    control._ustripHolds = depth;
    control.disabled = true;
    control.classList.add("is-busy");
    var released = false;
    return function () {
      if (released) return;
      released = true;
      control._ustripHolds = Math.max(0, (control._ustripHolds || 1) - 1);
      if (!control._ustripHolds) {
        control.disabled = false;
        control.classList.remove("is-busy");
      }
    };
  }

  function request(url, { method, json, formData, busy } = {}) {
    var opts = { method: method || (formData || json !== undefined ? "POST" : "GET") };
    opts.headers = { "X-CSRFToken": document.body.dataset.csrf };
    if (formData) {
      opts.body = formData;
    } else if (json !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(json);
    }
    var release = hold(busy || pendingSubmitter);
    pendingSubmitter = null;
    return fetch(url, opts).then(async (res) => {
      let data = {};
      try {
        data = await res.json();
      } catch (e) {
        /* empty/non-JSON body (e.g. a 204 from DELETE) — leave data as {} */
      }
      if (!res.ok) {
        var message = data.detail || data.error || firstFieldError(data) || "Something went wrong";
        throw Object.assign(new Error(message), { data: data, status: res.status });
      }
      return data;
    }).finally(release);
  }

  function firstFieldError(data) {
    // DRF validation errors come back as {field: ["message", ...]}.
    for (var key in data) {
      if (Array.isArray(data[key]) && data[key].length) return data[key][0];
    }
    return null;
  }

  function el(html) {
    const wrap = document.createElement("div");
    wrap.innerHTML = html.trim();
    return wrap.firstElementChild;
  }

  /* sortable(containers, { handle, onDrop })
   *
   * Rows are the direct children of a container that carry data-item-id.
   * Press on an element matching `handle` (default [data-drag-handle]),
   * move, release. While moving, the row itself becomes a floating ghost
   * under the finger and a dashed placeholder marks where it will land —
   * in any of the given containers, so a drag between two days on the
   * list page is the same gesture as a drag within one. On release the
   * row is put where the placeholder was and onDrop gets:
   *   { row, container, fromContainer, ids }   (ids = the target's new order)
   * Pointer events cover mouse, pen and touch alike; the handle needs
   * `touch-action: none` (ustrip.css) so the page does not scroll instead. */
  function sortable(containers, options) {
    var handleSelector = (options && options.handle) || "[data-drag-handle]";
    var onDrop = (options && options.onDrop) || function () {};
    var state = null;

    function rowAt(x, y) {
      var under = document.elementFromPoint(x, y);
      if (!under) return null;
      var row = under.closest("[data-item-id]");
      if (row && containers.indexOf(row.parentElement) !== -1 && row !== state.placeholder) return row;
      var container = under.closest("[data-sortable]");
      return container && containers.indexOf(container) !== -1 ? container : null;
    }

    function onMove(e) {
      if (!state) return;
      e.preventDefault();
      state.ghost.style.transform = "translate(" + (e.clientX - state.offsetX) + "px," + (e.clientY - state.offsetY) + "px)";
      // Nudge the page when dragging near the top or bottom edge.
      if (e.clientY < 70) window.scrollBy(0, -10);
      else if (e.clientY > window.innerHeight - 70) window.scrollBy(0, 10);

      var target = rowAt(e.clientX, e.clientY);
      if (!target) return;
      if (target.hasAttribute("data-sortable")) {
        if (!target.querySelector("[data-item-id]") || target.lastElementChild === state.placeholder) {
          target.appendChild(state.placeholder);
        } else {
          var last = target.querySelector("[data-item-id]:last-of-type");
          if (last && e.clientY > last.getBoundingClientRect().bottom) target.appendChild(state.placeholder);
        }
        return;
      }
      var box = target.getBoundingClientRect();
      var before = e.clientY < box.top + box.height / 2;
      target.parentElement.insertBefore(state.placeholder, before ? target : target.nextSibling);
    }

    function onUp(e) {
      if (!state) return;
      var s = state;
      state = null;
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
      s.ghost.remove();
      s.placeholder.replaceWith(s.row);
      s.row.classList.remove("dragging");
      var container = s.row.parentElement;
      var ids = Array.prototype.map.call(container.querySelectorAll("[data-item-id]"), function (r) {
        return Number(r.dataset.itemId);
      });
      var moved = container !== s.fromContainer || ids.join() !== s.startIds.join();
      if (moved) onDrop({ row: s.row, container: container, fromContainer: s.fromContainer, ids: ids });
    }

    containers.forEach(function (container) {
      container.setAttribute("data-sortable", "");
      container.addEventListener("pointerdown", function (e) {
        var handle = e.target.closest(handleSelector);
        if (!handle) return;
        var row = handle.closest("[data-item-id]");
        if (!row || row.parentElement !== container) return;
        e.preventDefault();
        var box = row.getBoundingClientRect();
        var ghost = row.cloneNode(true);
        ghost.classList.add("drag-ghost");
        ghost.style.width = box.width + "px";
        ghost.style.transform = "translate(" + box.left + "px," + box.top + "px)";
        var placeholder = document.createElement("div");
        placeholder.className = "drag-placeholder";
        placeholder.style.height = box.height + "px";
        row.classList.add("dragging");
        row.replaceWith(placeholder);
        document.body.appendChild(ghost);
        state = {
          row: row, ghost: ghost, placeholder: placeholder, fromContainer: container,
          offsetX: e.clientX - box.left, offsetY: e.clientY - box.top,
          startIds: Array.prototype.map.call(container.querySelectorAll("[data-item-id]"), function (r) {
            return Number(r.dataset.itemId);
          }),
        };
        document.addEventListener("pointermove", onMove, { passive: false });
        document.addEventListener("pointerup", onUp);
        document.addEventListener("pointercancel", onUp);
      });
    });
  }

  /* shrinkPhotos(formData, fields) -> Promise<FormData>
   *
   * Spec §0a.3: a phone photo is 3-8MB and Render's disk is 1GB with the
   * SQLite database on it. Downscale in the browser before upload: long edge
   * to MAX_EDGE, JPEG at QUALITY. A 4000x3000 12MP shot lands around 300KB,
   * which is still more than the phone-sized screens that will look at it.
   *
   * Anything that isn't an image, or that fails to decode, is passed through
   * untouched — a broken resize must never cost the family the photo. */
  var MAX_EDGE = 1600;
  var QUALITY = 0.82;

  function shrinkFile(file) {
    if (!file || !file.type || file.type.indexOf("image/") !== 0) return Promise.resolve(file);
    if (file.type === "image/gif") return Promise.resolve(file); // would lose the animation
    return createImageBitmap(file)
      .then(function (bitmap) {
        var scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
        if (scale === 1 && file.size < 1024 * 1024) {
          bitmap.close && bitmap.close();
          return file;
        }
        var canvas = document.createElement("canvas");
        canvas.width = Math.round(bitmap.width * scale);
        canvas.height = Math.round(bitmap.height * scale);
        canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        bitmap.close && bitmap.close();
        return new Promise(function (resolve) {
          canvas.toBlob(function (blob) {
            if (!blob || blob.size >= file.size) return resolve(file); // no win, keep the original
            resolve(new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }));
          }, "image/jpeg", QUALITY);
        });
      })
      .catch(function () { return file; });
  }

  function shrinkPhotos(formData, fields) {
    var names = fields || ["photo"];
    var jobs = names.map(function (name) {
      var file = formData.get(name);
      if (!(file instanceof File) || !file.size) return null;
      return shrinkFile(file).then(function (shrunk) { formData.set(name, shrunk); });
    }).filter(Boolean);
    return Promise.all(jobs).then(function () { return formData; });
  }

  /* 90 -> "1h 30m", 45 -> "45m" — the JS twin of the duration_human template filter. */
  function minutes(n) {
    n = Number(n) || 0;
    if (n <= 0) return "";
    var h = Math.floor(n / 60), m = n % 60;
    if (h && m) return h + "h " + m + "m";
    return h ? h + "h" : m + "m";
  }

  window.ustrip = {
    request: request, el: el, sortable: sortable, minutes: minutes,
    shrinkPhotos: shrinkPhotos, shrinkFile: shrinkFile, hold: hold,
  };
})();
