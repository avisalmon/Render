"""memz's one door to the site's AI (Rule 12.1.1).

Two features now want a language model: AI player seats (`ai_players.py`,
SPR-Z.8) and caption starters (`ideas.py`, SPR-W.5). Rule 12.1.1 says
cross-app reach is "rare, deliberate and named" — which a second file
importing `app.ai_chat` directly starts to erode, and a third would
settle. So the reach lives here, once, and memz's own modules import from
memz.

The indirection is one line, and it earns it twice over: `moderation.py`
is the same shape for `app.safety`, so the encapsulation test can go on
naming exactly two adapters however many features use them.

The inner import is deliberately inside the function, not at module
scope. A module-level `from app.ai_chat import call_openai` binds the
function object once, and every test that swaps `app.ai_chat.call_openai`
to simulate an outage would then be swapping a name nothing reads.
"""


def call_openai(messages, system_prompt=None):
    """The site's shared OpenAI wrapper: stub mode when `OPENAI_API_KEY`
    is unset, and errors caught inside it. Callers still guard their own
    use of the result — an AI feature must never be why a round hangs."""
    from app.ai_chat import call_openai as _call_openai

    return _call_openai(messages, system_prompt=system_prompt)
