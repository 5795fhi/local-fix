"""Thin client for the Vercel AI Gateway (OpenAI-compatible chat completions).

The gateway exposes an OpenAI-style `/chat/completions` endpoint. On Vercel the
`AI_GATEWAY_API_KEY` is injected automatically; locally set it in your `.env`.
If no key is configured we fall back to a helpful rule-based reply so the
assistant remains usable in development without credentials.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger("localfix.assistant")

SYSTEM_PROMPT = (
    "You are the LocalFix Assistant, a friendly helper for a local home-services "
    "marketplace. LocalFix connects customers with vetted local professionals "
    "(electricians, plumbers, carpenters, cleaners, painters, and more). Help "
    "users describe their problem, pick the right service category, understand "
    "how booking, payment, reviews, and complaints work, and give practical, "
    "safety-conscious home-maintenance advice. Keep answers concise and never "
    "invent specific provider names, prices, or availability."
)

_CATEGORY_HINTS = {
    "leak": "plumbing", "pipe": "plumbing", "tap": "plumbing", "drain": "plumbing",
    "toilet": "plumbing", "water": "plumbing",
    "light": "electrical", "wiring": "electrical", "socket": "electrical",
    "power": "electrical", "switch": "electrical", "fuse": "electrical",
    "wood": "carpentry", "door": "carpentry", "furniture": "carpentry",
    "cabinet": "carpentry", "shelf": "carpentry",
    "clean": "cleaning", "dust": "cleaning", "tidy": "cleaning",
    "paint": "painting", "wall": "painting",
    "ac": "hvac", "heating": "hvac", "cooling": "hvac", "air": "hvac",
}


def _fallback_reply(user_message):
    text = user_message.lower()
    for keyword, category in _CATEGORY_HINTS.items():
        if keyword in text:
            return (
                f"It sounds like you need help with {category}. On LocalFix you can "
                f"browse approved {category} professionals under Services, send a "
                "booking request with your preferred time, and pay securely once the "
                "job is complete. Would you like tips before booking?"
            )
    return (
        "I'm the LocalFix assistant. Tell me what needs fixing (for example a leaking "
        "tap, a broken socket, or a room that needs painting) and I'll point you to "
        "the right service category and explain how booking works."
    )


def chat_completion(messages):
    """Return the assistant's reply text for a list of {role, content} messages."""
    api_key = settings.AI_GATEWAY_API_KEY
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    if not api_key:
        logger.info("AI_GATEWAY_API_KEY not set; using rule-based fallback.")
        return _fallback_reply(last_user)

    payload = {
        "model": settings.LOCALFIX_AI_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        "temperature": 0.4,
        "max_tokens": 500,
    }
    try:
        resp = requests.post(
            f"{settings.AI_GATEWAY_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        logger.warning("AI Gateway request failed: %s", exc)
        return _fallback_reply(last_user)
