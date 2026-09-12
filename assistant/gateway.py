"""Chat completions via Groq (official ``groq`` SDK).

Create a free key at https://console.groq.com/keys and set ``GROQ_API_KEY``
in your environment (or ``.env``). If no key is configured we fall back to a
helpful rule-based reply so the assistant remains usable in development
without credentials.
"""
import logging
import re

from django.conf import settings
from groq import Groq, GroqError

logger = logging.getLogger("localfix.assistant")

SYSTEM_PROMPT = (
    "You are the LocalFix Assistant, a friendly helper for a local home-services "
    "marketplace. LocalFix connects customers with vetted local professionals "
    "(electricians, plumbers, carpenters, cleaners, painters, and more). Help "
    "users describe their problem, pick the right service category, understand "
    "how booking, payment, reviews, and complaints work, and give practical, "
    "safety-conscious home-maintenance advice. Keep answers concise. "
    "When matching professionals are provided, summarise why they fit and invite "
    "the user to tap Select & book, then give a date, time, and address. "
    "Never invent specific provider names, prices, or availability."
)


_MD_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),   # **bold**
    (re.compile(r"__(.+?)__"), r"\1"),          # __bold__
    (re.compile(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])"), r"\1"),  # *italic*
    (re.compile(r"`{1,3}([^`]*)`{1,3}"), r"\1"),  # inline & fenced code
    (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""),  # headings
    (re.compile(r"^\s*[-*+]\s+", re.MULTILINE), "• "),  # bullets
    (re.compile(r"\[(.+?)\]\((.+?)\)"), r"\1"),  # links -> text
    (re.compile(r"^\|.*\|\s*$", re.MULTILINE), ""),  # table rows
    (re.compile(r"\n{3,}"), "\n\n"),  # collapse gaps left by removed tables
]


def _plain_text(text):
    """Strip markdown so chat bubbles stay readable plain text."""
    for pattern, repl in _MD_PATTERNS:
        text = pattern.sub(repl, text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _fallback_reply(user_message, provider_context=""):
    if provider_context:
        return (
            "Here are approved LocalFix professionals who match what you described. "
            "Pick one, then add the date, time, and job address to send a booking request."
        )
    return (
        "I'm the LocalFix assistant. Tell me what needs fixing (for example a leaking "
        "tap, a broken socket, or a room that needs painting) and I'll suggest a few "
        "matching professionals you can book with your preferred date and time."
    )


def chat_completion(messages, extra_system=""):
    """Return the assistant's reply text for a list of {role, content} messages."""
    api_key = settings.GROQ_API_KEY
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    if not api_key:
        logger.info("GROQ_API_KEY not set; using rule-based fallback.")
        return _fallback_reply(last_user, extra_system)

    system = SYSTEM_PROMPT
    if extra_system:
        system = f"{SYSTEM_PROMPT}\n\n{extra_system}"

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=settings.LOCALFIX_AI_MODEL,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=0.4,
            max_tokens=800,
        )
        return _plain_text(resp.choices[0].message.content or "")
    except (GroqError, IndexError, AttributeError) as exc:
        logger.warning("Groq request failed: %s", exc)
        return _fallback_reply(last_user, extra_system)
