import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Бесплатный уровень OpenRouter регулярно меняет состав доступных ":free" моделей —
# конкретные ID периодически исчезают из каталога (напрямую наблюдалось: список,
# актуальный в начале августа 2026, частично устарел уже через 3 недели).
#
# "openrouter/free" — официальный роутер, который сам подбирает бесплатную модель —
# помогает от ротации каталога, НО он непредсказуем: может подобрать модель, которая
# вообще не предназначена для диалога (например, классификатор безопасности вроде
# Llama Guard, или "думающая" reasoning-модель, которая иногда выдаёт сырой ход
# рассуждений вместо чистого ответа).
#
# Поэтому основные модели — конкретные, проверенные диалоговые; "openrouter/free"
# стоит последним в списке как крайний резерв, а не первым выбором.
#
# Список читается из OPENROUTER_MODELS (через запятую) — можно поменять через
# переменную окружения в Render без правки кода. Актуальный живой список:
# https://openrouter.ai/collections/free-models
_DEFAULT_MODELS = [
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-26b-a4b-it:free",
    "openrouter/free",
]

_models_env = os.getenv("OPENROUTER_MODELS")
OPENROUTER_MODELS = (
    [m.strip() for m in _models_env.split(",") if m.strip()]
    if _models_env
    else _DEFAULT_MODELS
)

# Необязательно, но OpenRouter рекомендует указывать источник для статистики/рейтинга.
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "https://t.me/alonsochbot")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "Alons Bot")

_REQUEST_TIMEOUT = 30.0

# Некоторые модели умеют "думать" перед ответом (chain-of-thought). У OpenRouter есть
# единый параметр reasoning.exclude=true, который просит провайдера не включать эти
# рассуждения в текст ответа — используем его всегда. Но не все провайдеры его
# соблюдают на 100% (особенность конкретных бесплатных моделей), поэтому дополнительно
# распознаём и вырезаем такие рассуждения на своей стороне (см. ниже).
_REASONING_CONFIG = {"exclude": True}

# Если модель всё же обернула рассуждения в теги — вырезаем сам блок,
# оставляя то, что осталось (обычно это и есть настоящий ответ).
_THINK_TAG_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Признаки того, что (после вырезания тегов) текст всё равно является служебным
# выводом, а не обычным ответом: либо вердикт классификатора безопасности
# (Llama Guard и подобные), либо сырой нетегированный ход рассуждений модели.
_INVALID_OUTPUT_PATTERN = re.compile(
    r"(user safety\s*:|response safety\s*:|task:\s*check if there is unsafe content"
    r"|here'?s a thinking process|internal monologue|let me think step by step"
    r"|formulate response|final output construction)",
    re.IGNORECASE,
)


class OpenRouterError(Exception):
    """Ошибка при обращении к OpenRouter API (таймаут, сеть, некорректный ответ и т.д.)."""


def _clean_response_text(raw_text: str) -> str:
    """Вырезает блоки <think>...</think>, если модель их всё-таки вернула,
    и возвращает то, что осталось (обычно — настоящий ответ)."""
    cleaned = _THINK_TAG_PATTERN.sub("", raw_text).strip()
    return cleaned if cleaned else raw_text.strip()


def _is_invalid_output(text: str) -> bool:
    """True, если текст похож на служебный вывод модели (вердикт классификатора
    безопасности или сырой ход рассуждений), а не на обычный диалоговый ответ."""
    return bool(_INVALID_OUTPUT_PATTERN.search(text))


async def ask_openrouter(system_prompt: str, messages: list[dict]) -> str:
    """Отправляет запрос в OpenRouter chat completions и возвращает текст ответа.

    messages — список {"role": "user"/"assistant", "content": str} (история диалога,
    без system-сообщения — оно передаётся отдельно через system_prompt).

    Перебирает модели из OPENROUTER_MODELS по очереди сама (не полагаясь на
    встроенный "models"-фолбэк OpenRouter, который переключает модель только
    при ошибке запроса, но не при "плохом" содержимом ответа). Если модель
    вернула пустой текст, вывод классификатора безопасности или сырой ход
    рассуждений вместо ответа — пробует следующую модель из списка.

    Поднимает OpenRouterError только если ВСЕ модели из списка не сработали —
    вызывающий код (bot.py) должен поймать её и показать пользователю дружелюбное
    сообщение, не роняя бота.
    """
    if not OPENROUTER_API_KEY:
        raise OpenRouterError("OPENROUTER_API_KEY не задан")

    base_messages = [{"role": "system", "content": system_prompt}] + messages
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_APP_TITLE,
    }

    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        for model in OPENROUTER_MODELS:
            payload = {
                "model": model,
                "messages": base_messages,
                "temperature": 0.7,
                "max_tokens": 600,
                "reasoning": _REASONING_CONFIG,
            }
            try:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                raw_text = data["choices"][0]["message"]["content"].strip()

                if not raw_text:
                    logger.warning(f"OpenRouter: модель {model} вернула пустой ответ, пробуем следующую")
                    continue

                text = _clean_response_text(raw_text)

                if _is_invalid_output(text):
                    logger.warning(
                        f"OpenRouter: модель {model} вернула служебный вывод "
                        f"вместо ответа ({text[:100]!r}), пробуем следующую"
                    )
                    continue

                return text

            except httpx.TimeoutException as e:
                logger.warning(f"OpenRouter: таймаут у модели {model}, пробуем следующую")
                last_error = e
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"OpenRouter: {model} вернула {e.response.status_code}: "
                    f"{e.response.text[:200]}, пробуем следующую"
                )
                last_error = e
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(f"OpenRouter: некорректный формат ответа от {model}, пробуем следующую")
                last_error = e

    logger.error("OpenRouter: ни одна модель из списка не дала пригодный ответ")
    raise OpenRouterError("all_models_failed") from last_error
