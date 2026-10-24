"""JSON that is safe inside a <script> tag (security review, 2026-10-24).

json.dumps leaves "<", ">" and "&" as they are, so a book called
"</script><img onerror=...>" would close the script block and run in every
viewer's browser. The three characters are written as JSON escapes instead,
which every JSON parser reads back unchanged.
"""

import json

_ESCAPES = {ord("<"): "\\u003c", ord(">"): "\\u003e", ord("&"): "\\u0026"}


def script_json(value, **kwargs):
    kwargs.setdefault("ensure_ascii", False)
    return json.dumps(value, **kwargs).translate(_ESCAPES)
