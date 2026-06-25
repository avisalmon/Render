// In-lesson runnable Python cells. A ```python-run fenced block (rendered as
// <pre><code class="language-python-run">) becomes a real code editor (CodeMirror:
// syntax highlighting, line numbers, auto-indent) + Run + output. Python runs in
// the browser via Pyodide (WebAssembly) - no server compute. The code auto-saves
// to the site so it reloads on return.

const PYODIDE_VER = "v0.26.4";
const CM_VER = "5.65.16";
let _pyodide = null;
let _cm = null;

function _script(src) {
  return new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = src; s.onload = res; s.onerror = () => rej(new Error("load " + src));
    document.head.appendChild(s);
  });
}
function _css(href) {
  const l = document.createElement("link");
  l.rel = "stylesheet"; l.href = href; document.head.appendChild(l);
}

function loadCodeMirror() {
  if (_cm) return _cm;
  _cm = (async () => {
    const b = `https://cdn.jsdelivr.net/npm/codemirror@${CM_VER}/`;
    _css(b + "lib/codemirror.css");
    await _script(b + "lib/codemirror.js");
    await _script(b + "mode/python/python.js");
    try {
      await _script(b + "addon/edit/matchbrackets.js");
      await _script(b + "addon/edit/closebrackets.js");
    } catch (e) { /* niceties only */ }
  })();
  return _cm;
}

function loadPyodideOnce() {
  if (_pyodide) return _pyodide;
  _pyodide = (async () => {
    if (!window.loadPyodide) {
      await _script(`https://cdn.jsdelivr.net/pyodide/${PYODIDE_VER}/full/pyodide.js`);
    }
    return window.loadPyodide({ indexURL: `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VER}/full/` });
  })();
  return _pyodide;
}

// Run user code with stdout/stderr captured and input() wired to a browser prompt.
const WRAPPER = `
import sys, io, builtins
from js import window as __win
def __inp(p=""):
    r = __win.prompt(p)
    return "" if r is None else str(r)
builtins.input = __inp
__buf = io.StringIO()
__o, __e = sys.stdout, sys.stderr
sys.stdout = sys.stderr = __buf
try:
    exec(__USER_CODE__, {})
except SystemExit:
    pass
except Exception:
    import traceback; traceback.print_exc()
finally:
    sys.stdout, sys.stderr = __o, __e
__RESULT__ = __buf.getvalue()
`;

async function runCode(code, outEl, runBtn) {
  runBtn.disabled = true;
  outEl.hidden = false;
  outEl.textContent = "טוען סביבת פייתון בדפדפן… (בפעם הראשונה זה כמה שניות)";
  try {
    const py = await loadPyodideOnce();
    py.globals.set("__USER_CODE__", code);
    await py.runPythonAsync(WRAPPER);
    const out = py.globals.get("__RESULT__");
    outEl.textContent = (out && out.length) ? out : "(אין פלט)";
  } catch (err) {
    outEl.textContent = "שגיאה: " + (err && err.message ? err.message : err);
  } finally {
    runBtn.disabled = false;
  }
}

export async function initPyRunners(opts) {
  opts = opts || {};
  const blocks = Array.prototype.slice.call(
    document.querySelectorAll("pre > code.language-python-run"));
  if (!blocks.length) return;
  await loadCodeMirror();

  blocks.forEach((codeEl, i) => {
    const pre = codeEl.parentElement;
    const cellKey = "py" + i;
    const original = codeEl.textContent.replace(/\n$/, "");
    const start = (opts.saved && opts.saved[cellKey] != null) ? opts.saved[cellKey] : original;

    const wrap = document.createElement("div");
    wrap.className = "pyrun";
    wrap.innerHTML =
      '<div class="pyrun-host"></div>' +
      '<div class="pyrun-bar">' +
        '<span class="pyrun-point" aria-hidden="true">👈</span>' +
        '<button type="button" class="btn btn-sm btn-primary pyrun-run pyrun-cta"><i class="bi bi-play-fill"></i> הריצו</button>' +
        '<button type="button" class="btn btn-sm btn-link pyrun-reset">איפוס</button>' +
        '<span class="pyrun-status"></span>' +
        '<span class="pyrun-hint">Ctrl+Enter להרצה</span>' +
      '</div>' +
      '<pre class="pyrun-out" hidden></pre>';
    const host = wrap.querySelector(".pyrun-host");
    const runBtn = wrap.querySelector(".pyrun-run");
    const resetBtn = wrap.querySelector(".pyrun-reset");
    const status = wrap.querySelector(".pyrun-status");
    const out = wrap.querySelector(".pyrun-out");
    pre.replaceWith(wrap);

    const cm = window.CodeMirror(host, {
      value: start,
      mode: "python",
      lineNumbers: true,
      indentUnit: 4,
      tabSize: 4,
      lineWrapping: true,
      viewportMargin: Infinity,   // auto-height to content (no inner scroll)
      direction: "ltr",
      matchBrackets: true,
      autoCloseBrackets: true,
      extraKeys: { "Ctrl-Enter": () => go() },
    });

    // Run + drop the "click me" emphasis once the student engages.
    function go() {
      wrap.classList.add("pyrun-used");
      runCode(cm.getValue(), out, runBtn);
    }

    let timer = null;
    function save() {
      if (!opts.saveUrl) return;
      const body = new URLSearchParams({ cell_key: cellKey, code: cm.getValue() });
      fetch(opts.saveUrl, {
        method: "POST",
        headers: { "X-CSRFToken": opts.csrf || "", "Content-Type": "application/x-www-form-urlencoded" },
        body,
      }).then((r) => r.json()).then((d) => {
        if (d && d.ok) { status.textContent = "נשמר ✓"; setTimeout(() => { status.textContent = ""; }, 2000); }
      }).catch(() => {});
    }
    cm.on("change", () => { clearTimeout(timer); timer = setTimeout(save, 1200); });
    cm.on("blur", save);
    runBtn.addEventListener("click", go);
    resetBtn.addEventListener("click", () => { cm.setValue(original); save(); out.hidden = true; });
  });
}
