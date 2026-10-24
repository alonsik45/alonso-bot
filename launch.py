"""Конструктор постов для канала: /launch.

Как пользоваться (любому пользователю, в личке с ботом):
  /launch → «Выбрать канал» → «➕ Новый пост».
Бот спросит по шагам: 1) сам пост (текст / фото / видео / гиф), 2) кнопки-ссылки под постом,
3) когда опубликовать. Если в тексте есть {timer}, бот спросит ещё, до какого момента считать:
после публикации он сам будет подставлять вместо {timer} время до конца (например «Осталось: {timer}»), а в нужный момент напишет «время пришло 🔥».
Постов можно запланировать сколько угодно — они лежат в «📋 Мои посты».

Условия: бот должен быть АДМИНОМ канала с правами «Публикация сообщений» и «Редактирование сообщений
других админов» (закреплять — по желанию). А сам пользователь — владельцем или админом этого канала с правом
публикации: бот это проверяет, так что чужие каналы через него не опубликуешь.

Кто что видит: у каждого пользователя свой канал и свой список постов, чужие не видны никому.
• Админы бота (ADMIN_CHAT_ID): посты сохраняются в базу (файл) и переживают перезапуск.
• Обычные пользователи: базы нет — посты живут только в памяти, пока бот работает, а после
  публикации исчезают из списка. После перезапуска бота их запланированные посты пропадают.

Хранение (только админы): посты лежат в JSON-файле (LAUNCH_DATA_PATH, по умолчанию data/launch_posts.json) и подхватываются
после перезапуска бота. ВАЖНО: на хостинге с временной файловой системой (например, Render без Disk) файл
пропадает при деплое — тогда нужен постоянный диск или хранение через GitHubStorage.
"""
import html
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, RetryAfter, TelegramError
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
DATA_PATH = os.getenv("LAUNCH_DATA_PATH", "data/launch_posts.json")

TIMER_TAG = "{timer}"                 # это место в тексте заменится на «Осталось …»
TIMER_DONE_TEXT = "время пришло 🔥"    # что появится, когда таймер дошёл до нуля
LATE_GRACE = 6 * 3600                  # если бот был выключен и опоздал больше, чем на это — пост не выходит сам
MAX_TEXT = 4096
MAX_CAPTION = 1024

_DEFAULT_CHAT = os.getenv("LAUNCH_CHANNEL_ID") or None   # канал по умолчанию — только для админов бота
_USERS = {}           # user_id -> {"chat_id", "chat_title", "posts": [...]} — у каждого своё, чужое не видно
MAX_ACTIVE_USER = 10  # сколько постов одновременно может ждать/идти у обычного пользователя
_DRAFTS = {}          # user_id -> черновик поста (пока он его собирает)
_BACKOFF = {}         # chat_id -> unix-время, до которого Telegram просил не править сообщения
_WAITING = None       # waiting_users бота (общий словарь)
_ADMIN_IDS = None     # функция, возвращающая список id админов

STATUS_ICON = {
    "scheduled": "⏳", "publishing": "📤", "live": "⏱",
    "done": "✅", "error": "❌", "missed": "⚠️",
}
STATUS_NAME = {
    "scheduled": "ждёт своего времени", "publishing": "публикуется", "live": "опубликован, идёт таймер",
    "done": "опубликован", "error": "ошибка публикации", "missed": "пропущен (бот был выключен)",
}


# ---------------------------------------------------------------- хранение

def _load():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return
    except Exception:
        logger.exception("Не удалось прочитать %s", DATA_PATH)
        return
    users = data.get("users")
    if users is None and "posts" in data:      # старый формат (один общий список) → отдаём первому админу
        admins = _ADMIN_IDS()
        users = {str(admins[0]): {"chat_id": data.get("chat_id"), "chat_title": data.get("chat_title"),
                                  "posts": data.get("posts", [])}} if admins else {}
    for key, st in (users or {}).items():
        try:
            uid = int(key)
        except ValueError:
            continue
        posts = st.get("posts", [])
        for p in posts:
            p.setdefault("owner", uid)
            if p.get("status") == "publishing" and not p.get("msg_id"):
                p["status"] = "scheduled"     # бот упал посреди публикации — пробуем ещё раз
        _USERS[uid] = {"chat_id": st.get("chat_id") or _DEFAULT_CHAT,
                       "chat_title": st.get("chat_title"), "posts": posts}


def _save():
    """На диск пишем только данные админов бота. Посты обычных пользователей живут в памяти и в файл не попадают."""
    try:
        data = {"users": {str(uid): st for uid, st in _USERS.items() if _is_admin(uid)}}
        folder = os.path.dirname(DATA_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = DATA_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DATA_PATH)
    except Exception:
        logger.exception("Не удалось сохранить %s", DATA_PATH)


def _u(uid: int) -> dict:
    """Личное состояние пользователя (канал и посты). У каждого оно своё."""
    st = _USERS.get(uid)
    if st is None:
        st = {"chat_id": _DEFAULT_CHAT if _is_admin(uid) else None, "chat_title": None, "posts": []}
        _USERS[uid] = st
    return st


def _find(uid: int, post_id: str):
    """Ищем пост только среди постов самого пользователя — чужие недоступны даже по подделанной кнопке."""
    for p in _u(uid)["posts"]:
        if p["id"] == post_id:
            return p
    return None


async def _user_can_post(bot, chat_id, uid: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, uid)
    except TelegramError:
        return False
    if m.status == "creator":
        return True
    return m.status == "administrator" and bool(getattr(m, "can_post_messages", False))


# ---------------------------------------------------------------- время

def _fmt_dt(ts: float) -> str:
    return datetime.fromtimestamp(ts, MSK).strftime("%d.%m %H:%M")


def _fmt_left(sec: float) -> str:
    sec = max(0, int(sec))
    if sec >= 86400:
        days, rest = divmod(sec, 86400)
        return f"{days} дн {rest // 3600} ч {(rest % 3600) // 60:02d} мин"
    if sec >= 3600:
        minutes = sec // 60
        return f"{minutes // 60} ч {minutes % 60:02d} мин"
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _interval(sec: float) -> int:
    """Как часто менять пост с таймером. Telegram режет слишком частые правки, поэтому по секундам — только в конце."""
    if sec > 3600:
        return 60
    if sec > 600:
        return 30
    if sec > 60:
        return 10
    return 3


def parse_when(text: str, now: datetime = None):
    """«сейчас», «21:00», «25.10 21:00», «25.10.2026 21:00», «+30м», «+2ч», «+1д» → datetime (МСК) или None."""
    now = now or datetime.now(MSK)
    t = (text or "").strip().lower()
    if t in ("сейчас", "now", "0"):
        return now

    m = re.fullmatch(r"(?:\+|через\s+)\s*(\d+)\s*([а-яa-z]*)", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit.startswith("ч") or unit.startswith("h"):
            return now + timedelta(hours=n)
        if unit.startswith("д") or unit.startswith("d"):
            return now + timedelta(days=n)
        if unit.startswith("с") and not unit.startswith("со"):
            return now + timedelta(seconds=n)
        return now + timedelta(minutes=n)

    m = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\s+(\d{1,2})[:.](\d{2})", t)
    if m:
        day, month, year, hour, minute = m.groups()
        year = int(year) if year else now.year
        if year < 100:
            year += 2000
        try:
            return datetime(year, int(month), int(day), int(hour), int(minute), tzinfo=MSK)
        except ValueError:
            return None

    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", t)
    if m:
        try:
            dt = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        except ValueError:
            return None
        if dt <= now:
            dt += timedelta(days=1)
        return dt
    return None


# ---------------------------------------------------------------- кнопки под постом

def _norm_url(url: str) -> str:
    url = url.strip()
    if url.startswith("@"):
        return "https://t.me/" + url[1:]
    if url.lower().startswith(("http://", "https://", "tg://")):
        return url
    if re.match(r"^t\.me/", url, re.I):
        return "https://" + url
    if "." in url and " " not in url:
        return "https://" + url
    raise ValueError(f"Не похоже на ссылку: {url}")


def parse_buttons(text: str):
    """Строки вида «Текст | ссылка» → [[текст, url], ...]. Бросает ValueError с понятным текстом."""
    rows = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            raise ValueError(f"В строке нет « | »: {line}")
        label, url = (x.strip() for x in line.rsplit("|", 1))
        if not label:
            raise ValueError(f"Пустой текст кнопки: {line}")
        rows.append([label[:64], _norm_url(url)])
    if len(rows) > 8:
        raise ValueError("Многовато — максимум 8 кнопок.")
    return rows


def _post_kb(p: dict):
    if not p.get("buttons"):
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, url=u)] for t, u in p["buttons"]])


# ---------------------------------------------------------------- отправка / правка

def _render(p: dict, now: float) -> str:
    text = p.get("text") or ""
    if TIMER_TAG in text and p.get("countdown_to"):
        rem = p["countdown_to"] - now
        left = TIMER_DONE_TEXT if rem <= 0 else _fmt_left(rem)
        text = text.replace(TIMER_TAG, html.escape(left))
    return text


async def _send(bot, chat_id, p: dict, text: str):
    kw = dict(chat_id=chat_id, parse_mode="HTML", reply_markup=_post_kb(p))
    mt = p.get("media_type")
    if mt == "photo":
        return await bot.send_photo(photo=p["file_id"], caption=text or None, **kw)
    if mt == "video":
        return await bot.send_video(video=p["file_id"], caption=text or None, **kw)
    if mt == "animation":
        return await bot.send_animation(animation=p["file_id"], caption=text or None, **kw)
    return await bot.send_message(text=text, **kw)


async def _edit(bot, p: dict, text: str):
    kw = dict(chat_id=p["chat_id"], message_id=p["msg_id"], parse_mode="HTML", reply_markup=_post_kb(p))
    if p.get("media_type"):
        await bot.edit_message_caption(caption=text, **kw)
    else:
        await bot.edit_message_text(text=text, **kw)


async def _notify_owner(bot, p: dict, text: str):
    try:
        await bot.send_message(chat_id=p["owner"], text=text)
    except Exception:
        logger.warning("Не удалось написать пользователю %s", p.get("owner"))


def _snippet(p: dict, n: int = 32) -> str:
    plain = html.unescape(re.sub(r"<[^>]+>", "", p.get("text") or "")).replace("\n", " ").strip()
    if not plain:
        plain = {"photo": "фото", "video": "видео", "animation": "гиф"}.get(p.get("media_type"), "без текста")
    return plain[:n] + ("…" if len(plain) > n else "")


async def _publish(bot, p: dict) -> bool:
    if p["status"] not in ("scheduled", "error", "missed"):
        return False
    p["status"] = "publishing"            # сразу, чтобы параллельный вызов не опубликовал дубль
    now = time.time()
    if not _is_admin(p["owner"]) and not await _user_can_post(bot, p["chat_id"], p["owner"]):
        p["status"] = "error"
        p["error"] = "у тебя больше нет прав публиковать в этом канале"
        _save()
        await _notify_owner(bot, p, f"❌ Пост «{_snippet(p)}» не опубликован: {p['error']}.")
        return False
    try:
        sent = await _send(bot, p["chat_id"], p, _render(p, now))
    except Exception as e:
        logger.exception("Не удалось опубликовать пост %s", p["id"])
        p["status"] = "error"
        p["error"] = str(e)[:200]
        _save()
        await _notify_owner(bot, p, f"❌ Не получилось опубликовать пост «{_snippet(p)}»: {e}\n\nОткрой /launch → «Мои посты».")
        return False

    p["msg_id"] = sent.message_id
    p["last_edit"] = now
    p["last_text"] = _render(p, now)
    p.pop("error", None)
    counting = bool(p.get("countdown_to")) and TIMER_TAG in (p.get("text") or "") and p["countdown_to"] > now
    p["status"] = "live" if counting else "done"
    _save()
    if p.get("pin"):
        try:
            await bot.pin_chat_message(chat_id=p["chat_id"], message_id=sent.message_id, disable_notification=True)
        except Exception:
            pass   # нет права закреплять — не страшно
    await _notify_owner(bot, p, f"✅ Пост «{_snippet(p)}» опубликован в «{p.get('chat_title') or p['chat_id']}»")
    return True


async def _update_timer(bot, p: dict, now: float):
    remaining = p["countdown_to"] - now
    final = remaining <= 0
    chat = p["chat_id"]
    if not final and (now < _BACKOFF.get(chat, 0) or now - p.get("last_edit", 0) < _interval(remaining)):
        return
    text = _render(p, now)
    if text == p.get("last_text"):
        if final:
            p["status"] = "done"
            _save()
        return
    try:
        await _edit(bot, p, text)
    except RetryAfter as e:
        _BACKOFF[chat] = now + float(e.retry_after) + 1
        logger.warning("Telegram просит подождать %s с — пауза в правках", e.retry_after)
        return
    except BadRequest as e:
        low = str(e).lower()
        if "not modified" in low:
            pass
        elif "not found" in low or "can't be edited" in low or "message to edit" in low:
            p["status"] = "done"        # пост удалили в канале — править нечего
            _save()
            return
        else:
            logger.warning("Не удалось обновить таймер поста %s: %s", p["id"], e)
            p["last_edit"] = now
            if final:
                p["status"] = "done"
                _save()
            return
    except TelegramError as e:
        logger.warning("Ошибка Telegram при обновлении таймера: %s", e)
        p["last_edit"] = now
        return
    p["last_edit"] = now
    p["last_text"] = text
    if final:
        p["status"] = "done"
        _save()


async def _tick(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()
    for uid, st in list(_USERS.items()):
        for p in list(st["posts"]):
            try:
                if p["status"] == "scheduled" and now >= p["publish_at"]:
                    if now - p["publish_at"] > LATE_GRACE:
                        p["status"] = "missed"
                        _save()
                        await _notify_owner(
                            context.bot, p,
                            f"⚠️ Пост «{_snippet(p)}» не вышел вовремя ({_fmt_dt(p['publish_at'])} МСК) — бот был выключен. "
                            "Открой /launch → «Мои посты», чтобы опубликовать вручную.",
                        )
                        continue
                    await _publish(context.bot, p)
                elif p["status"] == "live":
                    await _update_timer(context.bot, p, now)
            except Exception:
                logger.exception("Ошибка в планировщике постов (%s)", p.get("id"))
        if not _is_admin(uid):      # у обычных пользователей истории нет: вышедшие посты сразу убираем
            st["posts"] = [p for p in st["posts"] if p["status"] != "done"]


# ---------------------------------------------------------------- экраны

def _is_admin(user_id: int) -> bool:
    return user_id in _ADMIN_IDS()


def _panel_view(uid: int):
    st = _u(uid)
    posts = st["posts"]
    waiting = [p for p in posts if p["status"] == "scheduled"]
    live = [p for p in posts if p["status"] == "live"]
    lines = ["📅 КОНСТРУКТОР ПОСТОВ", ""]
    if not st["chat_id"]:
        lines.append("Сначала выбери канал. Бот должен быть админом канала, и ты тоже — с правом публикации.")
    else:
        lines.append(f"Канал: {st['chat_title'] or st['chat_id']}")
        lines.append(f"Запланировано: {len(waiting)} · идёт таймер: {len(live)}")
        for p in sorted(waiting, key=lambda x: x["publish_at"])[:3]:
            lines.append(f"  ⏳ {_fmt_dt(p['publish_at'])} — {_snippet(p, 28)}")
    if not _is_admin(uid):
        lines += ["", "ℹ️ Посты видишь только ты. Они хранятся, пока бот работает: после его перезапуска "
                      "запланированное пропадёт, а вышедшие посты из списка убираются сами."]
    kb = []
    if st["chat_id"]:
        kb.append([InlineKeyboardButton("➕ Новый пост", callback_data="launch_new")])
        kb.append([InlineKeyboardButton(f"📋 Мои посты ({len(posts)})", callback_data="launch_list")])
    kb.append([InlineKeyboardButton("📺 Выбрать канал" if not st["chat_id"] else "📺 Другой канал",
                                    callback_data="launch_choose")])
    return "\n".join(lines), InlineKeyboardMarkup(kb)


def _list_view(uid: int):
    posts = _u(uid)["posts"]
    if not posts:
        return "📋 Постов пока нет.", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Новый пост", callback_data="launch_new")],
            [InlineKeyboardButton("◀️ Назад", callback_data="launch_panel")]])
    active = sorted([p for p in posts if p["status"] in ("scheduled", "publishing", "live", "error", "missed")],
                    key=lambda x: x["publish_at"])
    finished = sorted([p for p in posts if p["status"] == "done"], key=lambda x: -x["publish_at"])
    kb = []
    for p in (active + finished)[:25]:
        icon = STATUS_ICON.get(p["status"], "•")
        kb.append([InlineKeyboardButton(f"{icon} {_fmt_dt(p['publish_at'])} · {_snippet(p, 26)}",
                                        callback_data=f"launch_p:{p['id']}")])
    tail = []
    if finished:
        tail.append(InlineKeyboardButton("🧹 Убрать опубликованные", callback_data="launch_clear"))
    tail.append(InlineKeyboardButton("◀️ Назад", callback_data="launch_panel"))
    kb.append(tail)
    return "📋 МОИ ПОСТЫ\n⏳ ждёт · ⏱ идёт таймер · ✅ вышел · ❌ ошибка", InlineKeyboardMarkup(kb)


def _card_view(p: dict):
    lines = [
        f"📝 «{_snippet(p, 40)}»",
        f"Статус: {STATUS_ICON.get(p['status'], '')} {STATUS_NAME.get(p['status'], p['status'])}",
        f"Выход: {_fmt_dt(p['publish_at'])} МСК",
    ]
    if p.get("countdown_to"):
        lines.append(f"Таймер до: {_fmt_dt(p['countdown_to'])} МСК")
    lines.append(f"Кнопок: {len(p.get('buttons') or [])} · закрепить: {'да' if p.get('pin') else 'нет'}")
    if p.get("error"):
        lines.append(f"Ошибка: {p['error']}")
    kb = [[InlineKeyboardButton("👁 Показать", callback_data=f"launch_prev:{p['id']}")]]
    if p["status"] in ("scheduled", "error", "missed"):
        kb.append([InlineKeyboardButton("📤 Опубликовать сейчас", callback_data=f"launch_now:{p['id']}"),
                   InlineKeyboardButton("🕒 Время", callback_data=f"launch_time:{p['id']}")])
    kb.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"launch_del:{p['id']}")])
    kb.append([InlineKeyboardButton("◀️ К списку", callback_data="launch_list")])
    return "\n".join(lines), InlineKeyboardMarkup(kb)


# ---------------------------------------------------------------- мастер «новый пост»

_CANCEL_ROW = [InlineKeyboardButton("✖️ Отмена", callback_data="launch_cancel")]

PROMPTS = {
    "content": (
        "📝 Шаг 1/3 — пришли сам пост.\n\n"
        "Текст, либо фото / видео / гифку с подписью. Оформление (жирный, курсив, ссылки) сохранится.\n\n"
        "⏱ Хочешь живой таймер — впиши в текст {timer}, например «Осталось: {timer}». Бот сам подставит время и будет обновлять."
    ),
    "buttons": (
        "🔘 Шаг 2/3 — кнопки под постом.\n\n"
        "По одной на строку, в формате:\nТекст кнопки | ссылка\n\n"
        "Например:\n🃏 Играть | https://t.me/alonsochbot\n📢 Канал | @alonsoroma\n\n"
        "Кнопки встанут друг под другом."
    ),
    "when": (
        "🕒 Шаг 3/3 — когда опубликовать (время МСК).\n\n"
        "Примеры:\n• сейчас\n• 21:00 — сегодня (или завтра, если время прошло)\n• 25.10 21:00\n• +30м, +2ч, +1д"
    ),
    "countdown": (
        "⏱ До какого момента считать таймер (МСК)?\n\n"
        "Тот же формат: 00:00, 25.10 21:00, +3ч. В этот момент вместо {timer} появится «" + TIMER_DONE_TEXT + "»."
    ),
    "edit_time": "🕒 Пришли новое время публикации (МСК): 21:00, 25.10 21:00, +2ч …",
}


def _prompt_kb(step: str):
    if step == "buttons":
        return InlineKeyboardMarkup([[InlineKeyboardButton("Без кнопок", callback_data="launch_nobtn")], _CANCEL_ROW])
    if step == "when":
        return InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Сейчас", callback_data="launch_whennow")], _CANCEL_ROW])
    return InlineKeyboardMarkup([_CANCEL_ROW])


async def _ask(message, uid: int, d: dict):
    _WAITING[uid] = "launch_input"
    await message.reply_text(PROMPTS[d["step"]], reply_markup=_prompt_kb(d["step"]))


def _summary(d: dict) -> str:
    lines = ["📋 Проверь — копия поста выше.", "",
             f"Канал: {d.get('chat_title') or d['chat_id']}",
             f"Выйдет: {'сразу' if d['publish_at'] <= time.time() + 30 else _fmt_dt(d['publish_at']) + ' МСК'}"]
    if d.get("countdown_to"):
        lines.append(f"Таймер до: {_fmt_dt(d['countdown_to'])} МСК")
    lines.append(f"Кнопок: {len(d['buttons'])}")
    return "\n".join(lines)


def _confirm_kb(d: dict):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Запланировать", callback_data="launch_confirm")],
        [InlineKeyboardButton(f"📌 Закрепить: {'да' if d['pin'] else 'нет'}", callback_data="launch_pin")],
        _CANCEL_ROW,
    ])


async def _show_confirm(bot, message, uid: int, d: dict):
    try:
        await _send(bot, message.chat_id, d, _render(d, time.time()))
    except TelegramError as e:
        d["step"] = "content"
        await message.reply_text(f"❌ Telegram не принял такой пост: {e}\n\nПришли пост заново.")
        await _ask(message, uid, d)
        return
    d["step"] = "confirm"
    _WAITING.pop(uid, None)
    await message.reply_text(_summary(d), reply_markup=_confirm_kb(d))


async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str = ""):
    """Сюда бот отдаёт сообщения админа, пока тот что-то вводит (action = 'launch_channel' / 'launch_input')."""
    if action == "launch_channel":
        await handle_channel_input(update, context, text)
        return

    msg = update.message
    uid = update.effective_user.id
    d = _DRAFTS.get(uid)
    if not d:
        await msg.reply_text("Черновик потерялся. Открой /launch и начни заново.")
        return
    step = d["step"]

    if step == "content":
        mt, fid = None, None
        if msg.photo:
            mt, fid, body, plain = "photo", msg.photo[-1].file_id, msg.caption_html or "", msg.caption or ""
        elif msg.video:
            mt, fid, body, plain = "video", msg.video.file_id, msg.caption_html or "", msg.caption or ""
        elif msg.animation:
            mt, fid, body, plain = "animation", msg.animation.file_id, msg.caption_html or "", msg.caption or ""
        elif msg.text:
            body, plain = msg.text_html, msg.text
        else:
            await msg.reply_text("Нужен текст, фото, видео или гиф. Пришли ещё раз 👇")
            _WAITING[uid] = "launch_input"
            return
        limit = MAX_CAPTION if mt else MAX_TEXT
        if len(plain) > limit:
            await msg.reply_text(f"Слишком длинно: {len(plain)} символов, максимум {limit}"
                                 f"{' для подписи к медиа' if mt else ''}. Сократи и пришли ещё раз.")
            _WAITING[uid] = "launch_input"
            return
        if not mt and not plain.strip():
            await msg.reply_text("Пустой пост. Пришли текст 👇")
            _WAITING[uid] = "launch_input"
            return
        d.update(media_type=mt, file_id=fid, text=body)
        d["step"] = "buttons"
        await _ask(msg, uid, d)
        return

    if step == "buttons":
        try:
            d["buttons"] = parse_buttons(text)
        except ValueError as e:
            await msg.reply_text(f"❌ {e}\n\nПопробуй ещё раз в формате «Текст | ссылка».")
            _WAITING[uid] = "launch_input"
            return
        d["step"] = "when"
        await _ask(msg, uid, d)
        return

    if step in ("when", "countdown", "edit_time"):
        dt = parse_when(text)
        if dt is None:
            await msg.reply_text("Не понял время 🤔 Примеры: 21:00 · 25.10 21:00 · +30м · +2ч · сейчас")
            _WAITING[uid] = "launch_input"
            return
        ts = dt.timestamp()
        if ts < time.time() - 60:
            await msg.reply_text(f"Это время уже прошло ({_fmt_dt(ts)} МСК). Пришли другое.")
            _WAITING[uid] = "launch_input"
            return

        if step == "when":
            d["publish_at"] = ts
            if TIMER_TAG in (d.get("text") or ""):
                d["step"] = "countdown"
                await _ask(msg, uid, d)
            else:
                await _show_confirm(context.bot, msg, uid, d)
            return

        if step == "countdown":
            if ts <= d["publish_at"]:
                await msg.reply_text("Таймер должен заканчиваться позже, чем пост выходит. Пришли другое время.")
                _WAITING[uid] = "launch_input"
                return
            d["countdown_to"] = ts
            await _show_confirm(context.bot, msg, uid, d)
            return

        # edit_time — меняем время у уже запланированного поста
        p = _find(uid, d["post_id"])
        _DRAFTS.pop(uid, None)
        if p is None:
            await msg.reply_text("Пост не найден — возможно, его удалили.")
            return
        if p.get("countdown_to") and p["countdown_to"] <= ts:
            await msg.reply_text("Таймер этого поста заканчивается раньше нового времени выхода. "
                                 "Удали пост и создай заново с другим временем.")
            return
        p["publish_at"] = ts
        if p["status"] in ("error", "missed"):
            p["status"] = "scheduled"
        _save()
        text_c, kb = _card_view(p)
        await msg.reply_text("✅ Время обновлено.\n\n" + text_c, reply_markup=kb)
        return


async def handle_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = ""):
    """Пользователь прислал @username канала или переслал пост из него."""
    msg = update.message
    uid = update.effective_user.id

    chat_ref = None
    origin = getattr(msg, "forward_origin", None)
    if origin is not None and getattr(origin, "chat", None) is not None:
        chat_ref = origin.chat.id
    elif getattr(msg, "forward_from_chat", None) is not None:
        chat_ref = msg.forward_from_chat.id
    else:
        t = (text or "").strip()
        if t.startswith("@"):
            chat_ref = t
        elif t.lstrip("-").isdigit():
            chat_ref = int(t)

    if chat_ref is None:
        _WAITING[uid] = "launch_channel"
        await msg.reply_text("Пришли @username канала (например @alonsoroma) или перешли сюда любой пост из канала.")
        return

    try:
        chat = await context.bot.get_chat(chat_ref)
        member = await context.bot.get_chat_member(chat.id, context.bot.id)
    except TelegramError as e:
        _WAITING[uid] = "launch_channel"
        await msg.reply_text(
            f"❌ Не получилось открыть канал: {e}\n\nПроверь, что бот добавлен в канал админом, и пришли ещё раз."
        )
        return

    if chat.type != "channel":
        _WAITING[uid] = "launch_channel"
        await msg.reply_text("Это не канал. Пришли @username именно канала или пост из него.")
        return

    can_post = getattr(member, "can_post_messages", False)
    can_edit = getattr(member, "can_edit_messages", False)
    if member.status != "administrator" or not (can_post and can_edit):
        _WAITING[uid] = "launch_channel"
        await msg.reply_text(
            "❌ У бота недостаточно прав в этом канале.\n\n"
            "Открой канал → Управление каналом → Администраторы → бот и включи:\n"
            "• Публикация сообщений\n• Редактирование сообщений других админов\n"
            "(по желанию ещё «Закрепление сообщений»).\n\nПотом пришли канал ещё раз."
        )
        return

    # Обычный пользователь может выбрать только канал, где он сам владелец или админ с правом публикации.
    if not _is_admin(uid) and not await _user_can_post(context.bot, chat.id, uid):
        _WAITING[uid] = "launch_channel"
        await msg.reply_text(
            "❌ Ты не админ этого канала (или у тебя нет права «Публикация сообщений»), "
            "поэтому публиковать в нём через бота нельзя.\n\nПришли свой канал."
        )
        return

    st = _u(uid)
    st["chat_id"] = chat.id
    st["chat_title"] = chat.title
    _save()
    text_p, kb = _panel_view(uid)
    await msg.reply_text(f"✅ Канал выбран: {chat.title}\n\n" + text_p, reply_markup=kb)


# ---------------------------------------------------------------- команда и кнопки

async def launch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user is None:
        return
    uid = update.effective_user.id
    _DRAFTS.pop(uid, None)
    _WAITING.pop(uid, None)
    text, kb = _panel_view(uid)
    await update.message.reply_text(text, reply_markup=kb)


async def launch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    action, _, arg = query.data.partition(":")
    st = _u(uid)

    async def show(text, kb):
        try:
            await query.edit_message_text(text, reply_markup=kb)
        except BadRequest:
            pass   # «сообщение не изменилось»

    if action == "launch_panel":
        await query.answer()
        _DRAFTS.pop(uid, None)
        _WAITING.pop(uid, None)
        await show(*_panel_view(uid))
        return

    if action == "launch_choose":
        await query.answer()
        _WAITING[uid] = "launch_channel"
        await query.message.reply_text(
            "📺 Пришли @username канала (например @alonsoroma) или перешли сюда любой пост из канала.\n\n"
            "Бот должен быть админом канала с правами «Публикация сообщений» и «Редактирование сообщений»."
        )
        return

    if action == "launch_list":
        await query.answer()
        await show(*_list_view(uid))
        return

    if action == "launch_clear":
        await query.answer("Убрал")
        st["posts"] = [p for p in st["posts"] if p["status"] != "done"]
        _save()
        await show(*_list_view(uid))
        return

    if action == "launch_new":
        if not st["chat_id"]:
            await query.answer("Сначала выбери канал", show_alert=True)
            return
        active = sum(1 for p in st["posts"] if p["status"] in ("scheduled", "publishing", "live", "error", "missed"))
        if not _is_admin(uid) and active >= MAX_ACTIVE_USER:
            await query.answer(f"Можно держать не больше {MAX_ACTIVE_USER} постов одновременно", show_alert=True)
            return
        await query.answer()
        d = {"step": "content", "buttons": [], "pin": False,
             "chat_id": st["chat_id"], "chat_title": st["chat_title"]}
        _DRAFTS[uid] = d
        await _ask(query.message, uid, d)
        return

    if action == "launch_cancel":
        await query.answer("Отменено")
        _DRAFTS.pop(uid, None)
        _WAITING.pop(uid, None)
        await show(*_panel_view(uid))
        return

    if action == "launch_nobtn":
        d = _DRAFTS.get(uid)
        if not d or d["step"] != "buttons":
            await query.answer("Это уже неактуально", show_alert=True)
            return
        await query.answer()
        d["buttons"] = []
        d["step"] = "when"
        await _ask(query.message, uid, d)
        return

    if action == "launch_whennow":
        d = _DRAFTS.get(uid)
        if not d or d["step"] != "when":
            await query.answer("Это уже неактуально", show_alert=True)
            return
        await query.answer()
        d["publish_at"] = time.time()
        if TIMER_TAG in (d.get("text") or ""):
            d["step"] = "countdown"
            await _ask(query.message, uid, d)
        else:
            await _show_confirm(context.bot, query.message, uid, d)
        return

    if action == "launch_pin":
        d = _DRAFTS.get(uid)
        if not d or d["step"] != "confirm":
            await query.answer("Это уже неактуально", show_alert=True)
            return
        d["pin"] = not d["pin"]
        await query.answer()
        await show(_summary(d), _confirm_kb(d))
        return

    if action == "launch_confirm":
        d = _DRAFTS.get(uid)
        if not d or d["step"] != "confirm":
            await query.answer("Это уже неактуально", show_alert=True)
            return
        _DRAFTS.pop(uid, None)
        p = {
            "id": uuid.uuid4().hex[:8], "status": "scheduled", "owner": uid,
            "chat_id": d["chat_id"], "chat_title": d.get("chat_title"),
            "media_type": d.get("media_type"), "file_id": d.get("file_id"),
            "text": d.get("text") or "", "buttons": d["buttons"], "pin": d["pin"],
            "publish_at": d["publish_at"], "countdown_to": d.get("countdown_to"),
            "msg_id": None, "last_edit": 0, "last_text": "",
        }
        st["posts"].append(p)
        _save()
        when = "сразу" if p["publish_at"] <= time.time() + 30 else f"{_fmt_dt(p['publish_at'])} МСК"
        await query.answer("Запланировано ✅")
        text_p, kb = _panel_view(uid)
        await show(f"✅ Пост запланирован: выйдет {when}.\n\n" + text_p, kb)
        return

    # --- действия с конкретным постом ---
    p = _find(uid, arg) if arg else None
    if action in ("launch_p", "launch_prev", "launch_now", "launch_time", "launch_del", "launch_delyes") and p is None:
        await query.answer("Пост не найден", show_alert=True)
        await show(*_list_view(uid))
        return

    if action == "launch_p":
        await query.answer()
        await show(*_card_view(p))
        return

    if action == "launch_prev":
        await query.answer()
        try:
            await _send(context.bot, query.message.chat_id, p, _render(p, time.time()))
        except TelegramError as e:
            await query.message.reply_text(f"❌ Не получилось показать: {e}")
        return

    if action == "launch_now":
        await query.answer("Публикую…")
        await _publish(context.bot, p)
        await show(*_card_view(p))
        return

    if action == "launch_time":
        await query.answer()
        _DRAFTS[uid] = {"step": "edit_time", "post_id": p["id"]}
        await _ask(query.message, uid, _DRAFTS[uid])
        return

    if action == "launch_del":
        await query.answer()
        extra = ("\n\nТаймер остановится, но сам пост в канале останется." if p["status"] == "live"
                 else "\n\nИз канала пост не удаляется." if p["status"] == "done" else "")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Да, удалить", callback_data=f"launch_delyes:{p['id']}")],
                                   [InlineKeyboardButton("◀️ Нет", callback_data=f"launch_p:{p['id']}")]])
        await show(f"Удалить «{_snippet(p, 40)}» из конструктора?{extra}", kb)
        return

    if action == "launch_delyes":
        await query.answer("Удалено")
        st["posts"] = [x for x in st["posts"] if x["id"] != p["id"]]
        _save()
        await show(*_list_view(uid))
        return


def register(app, admin_ids_getter, waiting_users):
    """Подключает /launch, кнопки и планировщик. Вызывается из main() бота."""
    global _WAITING, _ADMIN_IDS
    _WAITING = waiting_users
    _ADMIN_IDS = admin_ids_getter
    _load()
    app.add_handler(CommandHandler("launch", launch_command))
    app.add_handler(CallbackQueryHandler(launch_callback, pattern="^launch_"))
    if app.job_queue is not None:
        app.job_queue.run_repeating(_tick, interval=1, first=2, name="launch_tick")
    else:
        logger.warning("JobQueue недоступен — запланированные посты (/launch) выходить сами не будут")
    logger.info("Конструктор постов (/launch) подключён для всех, сохранённых админских постов: %d",
                sum(len(st["posts"]) for st in _USERS.values()))
