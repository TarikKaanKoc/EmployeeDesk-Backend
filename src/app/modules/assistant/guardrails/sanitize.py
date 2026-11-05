"""Make untrusted text safe to place in a prompt.

Removes what a hidden instruction hides behind: zero-width and
bidirectional control characters, HTML comments and tags, and anything
that looks like a chat-role marker. Length is capped so one attachment
cannot crowd out the system prompt.
"""

import re
import unicodedata

MAX_MESSAGE_CHARS = 4000
MAX_ATTACHMENT_CHARS = 6000

_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿­]")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_ROLE_MARKER = re.compile(
    r"(?:^|(?<=\s))(system|assistant|user|developer|tool)\s*:", re.I
)
_CONTROL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def clean(text: str, *, limit: int) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = _INVISIBLE.sub("", text)
    text = _HTML_COMMENT.sub(" ", text)
    text = _TAG.sub(" ", text)
    text = _CONTROL.sub(" ", text)
    text = _ROLE_MARKER.sub(lambda m: m.group(0).replace(":", " -"), text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text[:limit]


def wrap_untrusted(title: str, body: str) -> str:
    """The form in which an attachment reaches the model: labelled as data,
    fenced so its end is unambiguous, with the label itself not spoofable
    from inside (the fence string is not present in cleaned text)."""
    return (
        f'<untrusted_document title="{clean(title, limit=120)}">\n'
        f"{body}\n"
        f"</untrusted_document>"
    )
