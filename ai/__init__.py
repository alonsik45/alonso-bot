import logging
import re
import time
from collections import defaultdict, deque

from .openrouter import ask_openrouter, OpenRouterError
from .memory import get_history, add_exchange, reset_history
from .prompt import build_system_prompt

logger = logging.getLogger(__name__)

# Системный промпт собирается один раз при импорте модуля (персона + правила +
# BOT KNOWLEDGE + ROMA KNOWLEDGE не меняются на лету во время работы процесса).
_SYSTEM_PROMPT = build_system_prompt()

FALLBACK_ERROR_TEXT = (
    "У меня сейчас нейронная часть немного задумалась 😅 Попробуй ещё раз через минуту."
)

# ------------------------------------------------------------
# Распознавание «человек написал вопрос/идею/историю мне, а не Роме»
# ------------------------------------------------------------

INTENTS = ("question", "idea", "story", "chat")

# Модель ставит в начале ответа служебную метку [[INTENT:...]] — вырезаем её.
_INTENT_TAG = re.compile(r"\[\[\s*INTENT\s*:\s*([a-z]+)\s*\]\]", re.IGNORECASE)

# Запасной вариант, если модель забыла поставить метку (бесплатные модели иногда так делают).
_IDEA_HINT = re.compile(r"(предлагаю|предложение|хочу предложить|а что если|а давай|идея[:\s]|сделай(те)? .*стрим|реклам|сотрудничеств)", re.IGNORECASE)
_ROMA_HINT = re.compile(r"(\bром[аыеу]\b|\bалонсо\b|\bрома,)", re.IGNORECASE)


def _extract_intent(raw: str, user_text: str) -> tuple[str, str]:
    """Возвращает (текст_без_метки, intent). Intent — одно из INTENTS."""
    intent = None
    m = _INTENT_TAG.search(raw)
    if m:
        candidate = m.group(1).lower()
        if candidate in INTENTS:
            intent = candidate
    text = _INTENT_TAG.sub("", raw).strip()

    if intent is None:
        low = user_text.strip()
        if _IDEA_HINT.search(low):
            intent = "idea"
        elif low.endswith("?") and _ROMA_HINT.search(low) and len(low) > 25:
            intent = "question"
        else:
            intent = "chat"

    return text, intent


# ------------------------------------------------------------
# Лимит сообщений (нужен для мини-аппа: модели бесплатные, без лимита их быстро выбьют)
# ------------------------------------------------------------

_rate_log: dict = defaultdict(deque)


def check_rate_limit(key, limit: int = 20, window_sec: int = 3600) -> bool:
    """True, если пользователю ещё можно писать; иначе False. Учитывает попытку."""
    now = time.monotonic()
    log = _rate_log[key]
    while log and now - log[0] > window_sec:
        log.popleft()
    if len(log) >= limit:
        return False
    log.append(now)
    return True


# ------------------------------------------------------------
# Главные точки входа
# ------------------------------------------------------------

async def ask_alons_ex(user_id, user_text: str) -> tuple[str, str]:
    """Отправляет сообщение Алонсу. Возвращает (ответ, intent), где intent —
    'question' / 'idea' / 'story' / 'chat'. При любой ошибке OpenRouter возвращает
    дружелюбный текст и intent='chat' — обычные функции бота продолжают работать."""
    history = get_history(user_id)
    messages = history + [{"role": "user", "content": user_text}]

    try:
        raw = await ask_openrouter(_SYSTEM_PROMPT, messages)
    except OpenRouterError:
        return FALLBACK_ERROR_TEXT, "chat"

    answer, intent = _extract_intent(raw, user_text)
    if not answer:
        return FALLBACK_ERROR_TEXT, "chat"

    add_exchange(user_id, user_text, answer)
    return answer, intent


async def ask_alons(user_id, user_text: str) -> str:
    """Совместимость со старым кодом: только текст ответа."""
    answer, _ = await ask_alons_ex(user_id, user_text)
    return answer
