// In-lesson runnable Python cells. A ```python-run fenced block becomes a real
// code editor (CodeMirror) + Run + output, running in the browser via Pyodide
// (WebAssembly) - no server compute. The code auto-saves to the site.
// An optional ```python-check block right after it (hidden from the student) holds
// the mission's tests; the "בדקו" button runs the student's code against them and
// records a pass (which can gate the certificate).

const PYODIDE_VER = "v0.26.4";
const CM_VER = "5.65.16";
let _pyodide = null;
let _pyReady = false;   // true once Pyodide finished loading (gates the linter)
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
    _css(b + "addon/lint/lint.css");
    _css(b + "addon/hint/show-hint.css");
    await _script(b + "lib/codemirror.js");
    await _script(b + "mode/python/python.js");
    try {
      await _script(b + "addon/edit/matchbrackets.js");
      await _script(b + "addon/edit/closebrackets.js");
      await _script(b + "addon/lint/lint.js");          // syntax-error markers
      await _script(b + "addon/hint/show-hint.js");      // autocomplete popup
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
    const py = await window.loadPyodide({ indexURL: `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VER}/full/` });
    _pyReady = true;
    return py;
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
__ERRORED__ = False
try:
    exec(__USER_CODE__, {})
except SystemExit:
    pass
except Exception:
    __ERRORED__ = True
    import traceback; traceback.print_exc()
finally:
    sys.stdout, sys.stderr = __o, __e
__RESULT__ = __buf.getvalue()
`;

// Check mode: gives the test a run_student(inputs) helper that runs the student's
// code fresh with input() fed from `inputs` and returns its captured stdout.
const CHECK_WRAPPER = `
import sys, io, builtins
__student = __USER_CODE__
def run_student(inputs=None):
    seq = iter(list(inputs or []))
    def _inp(prompt=""):
        try: return str(next(seq))
        except StopIteration: return ""
    buf = io.StringIO()
    o, e, oi = sys.stdout, sys.stderr, builtins.input
    sys.stdout = sys.stderr = buf
    builtins.input = _inp
    try:
        exec(__student, {})
    finally:
        sys.stdout, sys.stderr, builtins.input = o, e, oi
    return buf.getvalue()
def student_ns():
    # Exec the student's code once and hand back its namespace, so a check can
    # call the functions they defined (e.g. student_ns()["find_primes"](10, 50)).
    ns = {}
    o, e, oi = sys.stdout, sys.stderr, builtins.input
    sys.stdout = sys.stderr = io.StringIO()
    builtins.input = lambda prompt="": ""
    try:
        exec(__student, ns)
    finally:
        sys.stdout, sys.stderr, builtins.input = o, e, oi
    return ns
__CHECK_OK__ = True
__CHECK_KIND__ = ""
__CHECK_MSG__ = ""
try:
    exec(__CHECK_CODE__, {"run_student": run_student, "student_ns": student_ns})
except AssertionError:
    __CHECK_OK__ = False
    __CHECK_KIND__ = "assert"   # mission not met - shown as a friendly message
except Exception as __ex:
    __CHECK_OK__ = False
    __CHECK_KIND__ = "error"    # the student's code crashed - show the real error
    __CHECK_MSG__ = type(__ex).__name__ + ": " + str(__ex)
`;

async function runCode(code, outEl, runBtn) {
  runBtn.disabled = true;
  outEl.className = "pyrun-out";
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

// Run once and report {output, errored} - used by the Check flow to compile-check
// and capture a sample output before sending to the LLM coach.
async function captureRun(code) {
  const py = await loadPyodideOnce();
  py.globals.set("__USER_CODE__", code);
  await py.runPythonAsync(WRAPPER);
  return { output: py.globals.get("__RESULT__") || "", errored: !!py.globals.get("__ERRORED__") };
}

// Let the lesson page know a practice cell was solved (drives the next-lesson gate).
function firePass(cellKey) {
  try { document.dispatchEvent(new CustomEvent("pyrun:pass", { detail: { cellKey: cellKey } })); } catch (e) {}
}

// Syntax checking: compile() the code in Pyodide (no execution) and turn any
// SyntaxError into a CodeMirror lint annotation. Returns [] until Pyodide is
// loaded, so it never forces the big download just to lint.
const LINT_WRAPPER = `
import json as __json
__lint = None
try:
    compile(__LINT_SRC__, "<cell>", "exec")
except SyntaxError as __e:
    __lint = __json.dumps({"msg": __e.msg or "syntax error", "line": __e.lineno or 1, "col": __e.offset or 1})
except Exception:
    __lint = None
__lint
`;

async function pyLint(code) {
  if (!_pyReady || !code.trim()) return [];
  try {
    const py = await loadPyodideOnce();
    py.globals.set("__LINT_SRC__", code);
    const res = await py.runPythonAsync(LINT_WRAPPER);
    if (!res) return [];
    const e = JSON.parse(res);
    const ln = Math.max(0, (e.line || 1) - 1);
    const col = Math.max(0, (e.col || 1) - 1);
    return [{
      message: "שגיאת תחביר: " + (e.msg || ""),
      severity: "error",
      from: window.CodeMirror.Pos(ln, col),
      to: window.CodeMirror.Pos(ln, col + 1),
    }];
  } catch (e) { return []; }
}

// Autocomplete: Python keywords + common builtins/methods + identifiers already
// typed in this cell, filtered by the word under the cursor.
const PY_WORDS = (
  "and as assert async await break class continue def del elif else except finally " +
  "for from global if import in is lambda nonlocal not or pass raise return try while " +
  "with yield True False None print input int float str bool list dict set tuple len " +
  "range abs min max sum sorted reversed enumerate zip map filter round type isinstance " +
  "open format help dir id repr ord chr any all append pop insert remove keys values " +
  "items split join strip lower upper replace startswith endswith find index count"
).split(" ");

function pythonHint(cm) {
  const cur = cm.getCursor();
  const line = cm.getLine(cur.line);
  let start = cur.ch;
  while (start && /[\w$]/.test(line.charAt(start - 1))) start--;
  const word = line.slice(start, cur.ch);
  const lower = word.toLowerCase();
  const docWords = {};
  const re = /[A-Za-z_][\w]*/g; let m;
  const text = cm.getValue();
  while ((m = re.exec(text))) { docWords[m[0]] = 1; }
  const seen = {}; const out = [];
  PY_WORDS.concat(Object.keys(docWords)).forEach(function (w) {
    if (seen[w] || w === word) return;
    if (word && w.toLowerCase().lastIndexOf(lower, 0) !== 0) return;
    seen[w] = 1; out.push(w);
  });
  out.sort();
  return {
    list: out.slice(0, 40),
    from: window.CodeMirror.Pos(cur.line, start),
    to: window.CodeMirror.Pos(cur.line, cur.ch),
  };
}

// Deterministic check: runs the hidden ```python-check assertions against the
// student's code and returns {ok, kind} - the AUTHORITATIVE pass/fail (no LLM,
// so it never mis-grades correct code). kind is "" / "error".
async function runCheckBool(code, checkCode) {
  const py = await loadPyodideOnce();
  py.globals.set("__USER_CODE__", code);
  py.globals.set("__CHECK_CODE__", checkCode);
  await py.runPythonAsync(CHECK_WRAPPER);
  return { ok: !!py.globals.get("__CHECK_OK__"), kind: py.globals.get("__CHECK_KIND__") || "" };
}

export async function initPyRunners(opts) {
  opts = opts || {};
  const blocks = Array.prototype.slice.call(
    document.querySelectorAll("pre > code.language-python-run"));
  if (!blocks.length) return;

  // Pull out the hidden check blocks (paired by order with the run cells).
  const checkEls = Array.prototype.slice.call(
    document.querySelectorAll("pre > code.language-python-check"));
  const checkCodes = checkEls.map((c) => c.textContent.replace(/\n$/, ""));
  checkEls.forEach((c) => { c.parentElement.style.display = "none"; });

  // Hidden coach-spec blocks signal an LLM-graded cell (the spec itself lives
  // server-side; we only need to know the cell has one). Paired by order.
  const coachEls = Array.prototype.slice.call(
    document.querySelectorAll("pre > code.language-coach"));
  coachEls.forEach((c) => { c.parentElement.style.display = "none"; });

  const passedSet = new Set(opts.passed || []);
  await loadCodeMirror();

  blocks.forEach((codeEl, i) => {
    const pre = codeEl.parentElement;
    const cellKey = "py" + i;
    const original = codeEl.textContent.replace(/\n$/, "");
    const start = (opts.saved && opts.saved[cellKey] != null) ? opts.saved[cellKey] : original;
    const checkCode = checkCodes[i] || "";
    const hasCoach = !!coachEls[i];

    const wrap = document.createElement("div");
    wrap.className = "pyrun";
    wrap.innerHTML =
      '<div class="pyrun-host"></div>' +
      '<div class="pyrun-bar">' +
        '<span class="pyrun-point" aria-hidden="true">👈</span>' +
        '<button type="button" class="btn btn-sm btn-primary pyrun-run pyrun-cta"><i class="bi bi-play-fill"></i> הריצו</button>' +
        ((checkCode || hasCoach) ? '<button type="button" class="btn btn-sm btn-success pyrun-check"><i class="bi bi-check2-circle"></i> בדקו</button>' : '') +
        '<button type="button" class="btn btn-sm btn-link pyrun-reset">איפוס</button>' +
        '<span class="pyrun-status"></span>' +
        '<span class="pyrun-badge"' + (passedSet.has(cellKey) ? '' : ' hidden') + '>✓ הושלם</span>' +
        '<span class="pyrun-hint">Ctrl+Enter להרצה</span>' +
      '</div>' +
      '<pre class="pyrun-out" hidden></pre>';
    const host = wrap.querySelector(".pyrun-host");
    const runBtn = wrap.querySelector(".pyrun-run");
    const checkBtn = wrap.querySelector(".pyrun-check");
    const resetBtn = wrap.querySelector(".pyrun-reset");
    const status = wrap.querySelector(".pyrun-status");
    const badge = wrap.querySelector(".pyrun-badge");
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
      gutters: ["CodeMirror-lint-markers", "CodeMirror-linenumbers"],
      lint: {
        async: true,
        delay: 600,
        getAnnotations: function (text, cb) { pyLint(text).then(cb); },
      },
      extraKeys: {
        "Ctrl-Enter": () => go(),
        "Ctrl-Space": (c) => c.showHint({ hint: pythonHint, completeSingle: false }),
      },
    });

    // Load Pyodide on first focus so syntax-checking turns on (and the first run
    // is instant); re-lint once it's ready.
    cm.on("focus", function () {
      loadPyodideOnce().then(function () { try { cm.performLint(); } catch (e) {} });
    });
    // Gentle autocomplete: suggest as a word is typed (never auto-inserts).
    cm.on("inputRead", function (c, ch) {
      if (c.state.completionActive || !ch.text) return;
      if (/[A-Za-z_]$/.test(ch.text[0] || "")) {
        const cur = c.getCursor(); const ln = c.getLine(cur.line); let s = cur.ch;
        while (s && /[\w$]/.test(ln.charAt(s - 1))) s--;
        if (cur.ch - s >= 2) c.showHint({ hint: pythonHint, completeSingle: false });
      }
    });

    function go() {
      wrap.classList.add("pyrun-used");
      runCode(cm.getValue(), out, runBtn);
    }

    let timer = null;
    function save(passed) {
      if (!opts.saveUrl) return;
      const params = { cell_key: cellKey, code: cm.getValue() };
      if (passed) { params.passed = "1"; }
      fetch(opts.saveUrl, {
        method: "POST",
        headers: { "X-CSRFToken": opts.csrf || "", "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(params),
      }).then((r) => r.json()).then((d) => {
        if (d && d.ok && !passed) { status.textContent = "נשמר ✓"; setTimeout(() => { status.textContent = ""; }, 2000); }
      }).catch(() => {});
    }
    cm.on("change", () => { clearTimeout(timer); timer = setTimeout(save, 1200); });
    cm.on("blur", () => save());
    runBtn.addEventListener("click", go);
    resetBtn.addEventListener("click", () => { cm.setValue(original); save(); out.hidden = true; });

    // Ask the server-side LLM coach for feedback. hintOnly=true -> a teaching hint
    // for an already-known wrong answer; otherwise the LLM also judges pass/fail.
    async function callCoach(output, hintOnly) {
      const body = { cell_key: cellKey, code: cm.getValue(), output: output };
      if (hintOnly) { body.hint_only = "1"; }
      try {
        const r = await fetch(opts.coachUrl, {
          method: "POST",
          headers: { "X-CSRFToken": opts.csrf || "", "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams(body),
        });
        return await r.json();
      } catch (e) { return null; }
    }

    if (checkBtn) {
      checkBtn.addEventListener("click", async () => {
        wrap.classList.add("pyrun-used");
        checkBtn.disabled = true;
        out.className = "pyrun-out"; out.hidden = false; out.textContent = "מריץ ובודק…";
        let cap;
        try { cap = await captureRun(cm.getValue()); }
        catch (e) { out.className = "pyrun-out pyrun-fail"; out.textContent = "שגיאה בהרצה."; checkBtn.disabled = false; return; }
        // Only grade code that ran with no errors (compiles + runs clean).
        if (cap.errored) {
          out.className = "pyrun-out pyrun-fail";
          out.textContent = "✗ הקוד נתקל בשגיאה:\n" + cap.output;
          checkBtn.disabled = false; return;
        }

        if (checkCode) {
          // Authoritative path: the deterministic check decides pass/fail; the LLM
          // only coaches (so correct code is never wrongly rejected).
          let res;
          try { res = await runCheckBool(cm.getValue(), checkCode); }
          catch (e) { res = { ok: false, kind: "error" }; }
          if (res.ok) {
            out.className = "pyrun-out pyrun-ok";
            out.textContent = "✓ כל הכבוד! המשימה הושלמה בהצלחה.";
            badge.hidden = false; save(true); firePass(cellKey);
          } else {
            out.className = "pyrun-out pyrun-fail";
            out.textContent = "✗ עדיין לא. מנסח לכם רמז…";
            let hint = "";
            if (hasCoach && opts.coachUrl) {
              const d = await callCoach(cap.output, true);
              if (d && d.ok) { hint = d.comment || ""; }
            }
            out.textContent = "✗ " + (hint || "עדיין לא — בדקו שוב את התנאים ונסו שנית.");
          }
          checkBtn.disabled = false; return;
        }

        // No deterministic check (open-ended mission): let the LLM judge + coach.
        if (hasCoach && opts.coachUrl) {
          const d = await callCoach(cap.output, false);
          if (d && d.ok && d.available) {
            out.className = "pyrun-out " + (d.passed ? "pyrun-ok" : "pyrun-fail");
            out.textContent = (d.passed ? "✓ " : "✗ ") + (d.comment || (d.passed ? "כל הכבוד!" : "עדיין לא, נסו שוב."));
            if (d.passed) { badge.hidden = false; firePass(cellKey); }  // recorded server-side
            checkBtn.disabled = false; return;
          }
        }
        out.className = "pyrun-out"; out.textContent = cap.output || "(אין פלט)";
        checkBtn.disabled = false;
      });
    }
  });
}
