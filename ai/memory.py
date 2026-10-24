from collections import defaultdict, deque

# Сколько сообщений (реплик пользователя + Алонса вместе) хранить на одного пользователя.
# Не персистится на диск/GitHub — при рестарте бота история чата с Алонсом обнуляется,
# это ожидаемо для лёгкого контекста диалога (см. ТЗ п.22).
MAX_HISTORY_MESSAGES = 10

_conversations: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY_MESSAGES))


def get_history(user_id: int) -> list[dict]:
    """Возвращает историю диалога пользователя с Алонсом в формате для OpenRouter API."""
    return list(_conversations[user_id])


def add_exchange(user_id: int, user_text: str, assistant_text: str) -> None:
    """Добавляет пару (сообщение пользователя, ответ Алонса) в историю."""
    history = _conversations[user_id]
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": assistant_text})


def reset_history(user_id: int) -> None:
    """Очищает историю диалога (например, при возврате в главное меню)."""
    _conversations.pop(user_id, None)
