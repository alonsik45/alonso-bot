"""Запуск «Карточек»: тизер с живым таймером в канале и автоматический анонс в 00:00 (МСК).

Как пользоваться (админу, в личке с ботом):
  /launch → «Выбрать канал» (пришли @username канала или перешли из него любой пост) → «Запустить таймер».
Бот опубликует тизер без кнопки, будет обновлять в нём таймер, а в 00:00 опубликует анонс с кнопкой «Играть в карточки».

Условия: бот должен быть АДМИНОМ канала с правами «Публикация сообщений» и «Редактирование сообщений
других админов» (закреплять сообщения — по желанию).

Важно: состояние хранится в памяти. Если бот перезапустится или будет деплой, пока идёт таймер,
таймер остановится — тогда в панели /launch есть кнопка «Опубликовать анонс сейчас».
"""
import html
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, RetryAfter, TelegramError
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
BOT_LINK = "https://t.me/alonsochbot"

TEASER = (
    "⏳ <b>Сегодня в 00:00 вас ждёт кое-что интересное 🔥</b>\n\n"
    "Мы делали это с душой для тех, кто подписан на меня здесь ✨\n\n"
    "Подсказка: компетишн 👀\n\n"
    "⏱ Осталось: <b>{left}</b>"
)

TEASER_DONE = (
    "🔥 <b>ВРЕМЯ ПРИШЛО!</b>\n\n"
    "ALONSO GAME уже запущена! Анонс — ниже 👇"
)

ANNOUNCE = (
    "🔥 <b>ALONSO GAME ЗАПУЩЕНА! 🔥</b>\n"
    "Карточки, конкурс, дуэли, призы от Ромы. Сейчас всё по порядку 👇\n\n"

    "🚀 <b>КАК ЗАЙТИ</b>\n"
    "1. Открываешь бота @alonsochbot\n"
    "2. Жмёшь кнопку приложения слева возле строки для текста\n"
    "3. Внизу в меню светится фиолетовая кнопка «Игра», жми её 🎴\n\n"

    "🎁 <b>ПРОМОКОД НА СТАРТ</b>\n"
    "Вводи ALONSOTG и получай свои первые 100 🪙. Это 5 карточек! "
    "Работает один раз на человека. Вводи в игре, во вкладке «Открыть» ⚡\n\n"

    "🏆 <b>КОНКУРС «СОБЕРИ ВСЮ КОЛЛЕКЦИЮ»</b>\n"
    "Всего 30 карточек, у каждой своя редкость. Собираешь все 30 — "
    "попадаешь в рулетку на главный приз.\n"
    "Приз пока секрет 🤫\n"
    "Кто собрал раньше, у того выше шанс в рулетке. Но выиграть может "
    "любой, кто собрал всё.\n"
    "Тем, кто соберёт коллекцию, Рома запишет личное видео 🎬\n\n"

    "🪙 <b>ГДЕ БРАТЬ МОНЕТЫ</b>\n"
    "• Заходи каждый день за ежедневным бонусом: от 30 до 90 🪙. "
    "Чем длиннее серия, тем больше. Пропустил день — серия обнулилась.\n"
    "• Вопросы, идеи, предложения и «Что было дальше?» в боте тоже "
    "дают монеты — до 40 🪙 в сутки.\n"
    "• Промокоды: следи за моими соцсетями, все есть в закрепе.\n"
    "• Приглашай друзей (ниже).\n\n"
    "Одна карточка стоит 20 🪙.\n\n"

    "🎴 <b>ЧТО С НИМИ ДЕЛАТЬ</b>\n"
    "• <b>Обмен:</b> лишние дубликаты меняешь на карточку редкостью выше. "
    "Не повезёт — вернётся одна карточка той же редкости. "
    "Единственную копию отдать нельзя.\n"
    "• <b>PvP:</b> ставишь карточку против соперника той же редкости, "
    "шанс 50 на 50. Победил — забрал карточку соперника. Проиграл — "
    "потерял свою. С ботом доступно до 5 дуэлей в день, а ещё можно "
    "вызвать друга.\n"
    "• <b>Награды от Ромы:</b> отдаёшь карточки (любые, у каждой редкости "
    "своя цена) и забираешь приветствие, кружок, поздравление или ответ "
    "на твой вопрос в видео!\n\n"

    "👥 <b>ПРИГЛАШАЙ ДРУЗЕЙ</b>\n"
    "Во вкладке «Друзья» берёшь свою ссылку и кидаешь корешам.\n"
    "• Друг получает 100 🪙 сразу.\n"
    "• Ты получаешь монеты за каждого друга, и чем больше друзей, "
    "тем щедрее награда.\n"
    "• За 3, 5, 10 и 25 друзей дают бонусные карточки (до легендарных!).\n"
    "Друг должен быть новичком: пока не заходил в «Игру». "
    "Награда за приглашения идёт максимум за 5 друзей в сутки.\n\n"

    "⭐ <b>ДОНАТ ЗВЁЗДАМИ</b>\n"
    "Играть можно и бесплатно. Хочешь быстрее — покупай за звёзды Telegram:\n"
    "• 1 карточка: 5 ⭐\n"
    "• Редкий пак (4 карточки): 49 ⭐\n"
    "• Мега-пак (11 карточек): 199 ⭐\n"
    "• Легендарная карта: 599 ⭐\n"
    "• Две легендарные: 999 ⭐\n"
    "Лимитов на покупки нет.\n\n"

    "Заходи, собирай коллекцию и забирай приз 🔥\n"
    "@alonsochbot"
)

BUTTON_TEXT = "🃏 Играть в карточки"

# --- состояние (в памяти) ---
_S = {
    "chat_id": os.getenv("LAUNCH_CHANNEL_ID") or None,
    "chat_title": None,
    "msg_id": None,
    "target": None,
    "running": False,
    "announced": False,
    "last_edit": 0.0,
    "last_text": "",
    "backoff_until": 0.0,
    "job": None,
}
_WAITING = None
_ADMIN_IDS = None


def _next_midnight(now: datetime = None) -> datetime:
    now = now or datetime.now(MSK)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _fmt_left(sec: float) -> str:
    sec = max(0, int(sec))
    if sec >= 3600:
        minutes = sec // 60
        return f"{minutes // 60} ч {minutes % 60:02d} мин"
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _interval(sec: float) -> int:
    """Как часто менять тизер. Telegram ограничивает слишком частые правки."""
    if sec > 3600:
        return 60
    if sec > 600:
        return 30
    if sec > 60:
        return 10
    return 3


def _teaser_text(sec: float) -> str:
    return TEASER.format(left=html.escape(_fmt_left(sec)))


def _post_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(BUTTON_TEXT, url=BOT_LINK)]]
    )


def _is_admin(user_id: int) -> bool:
    return user_id in _ADMIN_IDS()


# ---------------------------------------------------------------- панель админа

def _panel_view():
    s = _S
    if s["running"]:
        left = _fmt_left(s["target"].timestamp() - time.time())
        text = (
            "🚀 ЗАПУСК КАРТОЧЕК\n\n"
            f"Канал: {s['chat_title'] or s['chat_id']}\n"
            f"Таймер идёт, до анонса: {left}\n"
            f"Анонс выйдет сам в {s['target'].strftime('%d.%m %H:%M')} МСК.\n\n"
            "⚠️ Если бот перезапустится, таймер остановится — тогда нажми «Опубликовать анонс сейчас»."
        )
        kb = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="launch_panel")],
            [InlineKeyboardButton("📣 Опубликовать анонс сейчас", callback_data="launch_now")],
            [InlineKeyboardButton("🛑 Остановить таймер", callback_data="launch_stop")],
        ]
        return text, InlineKeyboardMarkup(kb)

    if s["announced"]:
        text = (
            "🚀 ЗАПУСК КАРТОЧЕК\n\n"
            f"✅ Анонс уже опубликован в канале «{s['chat_title'] or s['chat_id']}»."
        )
        return text, InlineKeyboardMarkup(
            [[InlineKeyboardButton("📺 Выбрать другой канал", callback_data="launch_choose")]]
        )

    if not s["chat_id"]:
        text = (
            "🚀 ЗАПУСК КАРТОЧЕК\n\n"
            "Сначала выбери канал. Бот должен быть админом канала с правами на публикацию "
            "и редактирование сообщений."
        )
        kb = [
            [InlineKeyboardButton("📺 Выбрать канал", callback_data="launch_choose")],
            [InlineKeyboardButton("👁 Предпросмотр постов", callback_data="launch_preview")],
        ]
        return text, InlineKeyboardMarkup(kb)

    target = _next_midnight()
    text = (
        "🚀 ЗАПУСК КАРТОЧЕК\n\n"
        f"Канал: {s['chat_title'] or s['chat_id']}\n"
        f"Анонс выйдет в {target.strftime('%d.%m %H:%M')} МСК.\n\n"
        "Жми «Запустить таймер»: бот опубликует тизер без кнопки, будет менять время до анонса "
        "и в полночь сам выложит большой пост с кнопкой игры."
    )
    kb = [
        [InlineKeyboardButton("🚀 Запустить таймер", callback_data="launch_start")],
        [InlineKeyboardButton("👁 Предпросмотр постов", callback_data="launch_preview")],
        [InlineKeyboardButton("📣 Опубликовать анонс сейчас", callback_data="launch_now")],
        [InlineKeyboardButton("📺 Другой канал", callback_data="launch_choose")],
    ]
    return text, InlineKeyboardMarkup(kb)


async def launch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not _is_admin(update.effective_user.id):
        return
    text, kb = _panel_view()
    await update.message.reply_text(text, reply_markup=kb)


async def handle_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = ""):
    """Админ прислал @username канала или переслал пост из него."""
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
        await msg.reply_text(
            "Пришли @username канала (например @alonsoroma) или перешли сюда любой пост из канала."
        )
        return

    try:
        chat = await context.bot.get_chat(chat_ref)
        member = await context.bot.get_chat_member(chat.id, context.bot.id)
    except TelegramError as e:
        _WAITING[uid] = "launch_channel"
        await msg.reply_text(
            f"❌ Не получилось открыть канал: {e}\n\n"
            "Проверь, что бот добавлен в канал админом, и пришли ещё раз."
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

    _S["chat_id"] = chat.id
    _S["chat_title"] = chat.title
    text, kb = _panel_view()
    await msg.reply_text(f"✅ Канал выбран: {chat.title}\n\n" + text, reply_markup=kb)


# ---------------------------------------------------------------- таймер

async def _tick(context: ContextTypes.DEFAULT_TYPE):
    s = _S
    if not s["running"] or s["target"] is None:
        return
    now = time.time()
    remaining = s["target"].timestamp() - now
    if remaining <= 0:
        await _announce(context.bot)
        return
    if now < s["backoff_until"] or now - s["last_edit"] < _interval(remaining):
        return
    text = _teaser_text(remaining)
    if text == s["last_text"]:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=s["chat_id"],
            message_id=s["msg_id"],
            text=text,
            parse_mode="HTML",
        )
    except RetryAfter as e:
        s["backoff_until"] = now + float(e.retry_after) + 1
        logger.warning("Telegram просит подождать %s с — пауза в правках тизера", e.retry_after)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            logger.warning("Не удалось обновить тизер: %s", e)
    except TelegramError as e:
        logger.warning("Ошибка Telegram при обновлении тизера: %s", e)
    else:
        s["last_edit"] = now
        s["last_text"] = text


async def _notify_admins(bot, text: str):
    for admin in _ADMIN_IDS():
        try:
            await bot.send_message(chat_id=admin, text=text)
        except Exception:
            logger.exception("Не удалось написать админу %s", admin)


def _stop_job():
    job = _S.get("job")
    if job is not None:
        try:
            job.schedule_removal()
        except Exception:
            pass
    _S["job"] = None
    _S["running"] = False


async def _announce(bot) -> bool:
    """Публикует большой анонс (один раз). Возвращает True, если вышло."""
    s = _S
    if s["announced"]:
        return False
    s["announced"] = True
    _stop_job()
    try:
        sent = await bot.send_message(
            chat_id=s["chat_id"],
            text=ANNOUNCE,
            parse_mode="HTML",
            reply_markup=_post_kb(),
            disable_web_page_preview=True,
        )
    except Exception as e:
        s["announced"] = False
        logger.exception("Не удалось опубликовать анонс")
        await _notify_admins(
            bot,
            f"❌ Не удалось опубликовать анонс в канале: {e}\n\n"
            "Открой /launch и нажми «Опубликовать анонс сейчас».",
        )
        return False

    if s["msg_id"]:
        try:
            await bot.edit_message_text(
                chat_id=s["chat_id"],
                message_id=s["msg_id"],
                text=TEASER_DONE,
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("Не удалось обновить тизер после анонса")
        try:
            await bot.unpin_chat_message(chat_id=s["chat_id"], message_id=s["msg_id"])
        except Exception:
            pass

    try:
        await bot.pin_chat_message(
            chat_id=s["chat_id"],
            message_id=sent.message_id,
            disable_notification=True,
        )
    except Exception:
        pass

    await _notify_admins(
        bot,
        f"✅ Анонс опубликован в канале «{s['chat_title'] or s['chat_id']}» 🎉",
    )
    return True


# ---------------------------------------------------------------- кнопки

async def launch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Только для админов", show_alert=True)
        return
    data = query.data
    s = _S

    async def show_panel():
        text, kb = _panel_view()
        try:
            await query.edit_message_text(text, reply_markup=kb)
        except BadRequest:
            pass

    if data == "launch_panel":
        await query.answer()
        await show_panel()
        return

    if data == "launch_choose":
        await query.answer()
        _WAITING[query.from_user.id] = "launch_channel"
        await query.message.reply_text(
            "📺 Пришли @username канала (например @alonsoroma) или перешли сюда любой пост из канала.\n\n"
            "Бот должен быть админом канала с правами «Публикация сообщений» и «Редактирование сообщений»."
        )
        return

    if data == "launch_preview":
        await query.answer()
        await query.message.reply_text(
            _teaser_text(5 * 3600 + 23 * 60),
            parse_mode="HTML",
        )
        await query.message.reply_text(
            ANNOUNCE,
            parse_mode="HTML",
            reply_markup=_post_kb(),
            disable_web_page_preview=True,
        )
        return

    if data == "launch_start":
        if s["running"]:
            await query.answer("Таймер уже идёт", show_alert=True)
            return
        if not s["chat_id"]:
            await query.answer("Сначала выбери канал", show_alert=True)
            return
        if context.application.job_queue is None:
            await query.answer("JobQueue недоступен — таймер не запустить", show_alert=True)
            return
        s["announced"] = False
        s["target"] = _next_midnight()
        remaining = s["target"].timestamp() - time.time()
        try:
            sent = await context.bot.send_message(
                chat_id=s["chat_id"],
                text=_teaser_text(remaining),
                parse_mode="HTML",
            )
        except TelegramError as e:
            await query.answer()
            await query.message.reply_text(
                f"❌ Не получилось опубликовать тизер: {e}\n\nПроверь права бота в канале."
            )
            return
        s["msg_id"] = sent.message_id
        s["last_edit"] = time.time()
        s["last_text"] = _teaser_text(remaining)
        s["backoff_until"] = 0.0
        s["running"] = True
        try:
            await context.bot.pin_chat_message(
                chat_id=s["chat_id"],
                message_id=sent.message_id,
                disable_notification=True,
            )
        except Exception:
            pass
        s["job"] = context.application.job_queue.run_repeating(
            _tick, interval=1, first=1, name="launch_tick"
        )
        await query.answer("🚀 Таймер запущен!")
        await show_panel()
        return

    if data == "launch_stop":
        await query.answer("Таймер остановлен")
        _stop_job()
        await show_panel()
        return

    if data == "launch_now":
        if not s["chat_id"]:
            await query.answer("Сначала выбери канал", show_alert=True)
            return
        await query.answer("Публикую…")
        if s["running"]:
            _stop_job()
        s["announced"] = False
        await _announce(context.bot)
        await show_panel()
        return


def register(app, admin_ids_getter, waiting_users):
    """Подключает /launch и кнопки. Вызывается из main() бота."""
    global _WAITING, _ADMIN_IDS
    _WAITING = waiting_users
    _ADMIN_IDS = admin_ids_getter
    app.add_handler(CommandHandler("launch", launch_command))
    app.add_handler(CallbackQueryHandler(launch_callback, pattern="^launch_"))
    logger.info("Запуск карточек (/launch) подключён")
