"""
Игра «Ситуации» для Telegram-бота (python-telegram-bot 21+).

Только обычный чат с ботом (Mini App не затрагивается).
Админ: /go — открыть набор и панель управления, /sgo — остановить игру.
Все: кнопка «🎭 Ситуации» в меню (вход в комнату), /vybor — голосование.

Подключение в bot.py (см. README в конце файла):
    import situations
    situations.register(app, admin_ids, lambda: all_users)

ВАЖНО: это ОСНОВА. Состояние хранится в памяти (при перезапуске бота игра
сбрасывается), банк ситуаций — константа BANK.
"""
import asyncio
import logging
import random
import time
from collections import Counter

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.ext.filters import MessageFilter

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Настройки
# ------------------------------------------------------------------
BANK = [
    "Самый нелепый способ познакомиться",
    "Как выкрутиться из неловкой ситуации",
    "Первое свидание, на которое пришли не те люди",
    "Вы застряли в лифте, и один из вас что-то скрывает",
    "Собеседование на должность, которой не существует",
    "Объясняете инопланетянину, что такое «пятница»",
    "Вас приняли за знаменитостей в кафе",
    "Ограбление банка, но грабители забыли план",
    "Самая нелепая причина опоздания — объясняете учителю",
    "Реклама самого ненужного товара в мире",
    "День рождения, на который не пришёл ни один гость",
    "Вы отправили не тому человеку голосовое — разруливаете",
    "Ссора из-за последнего куска пиццы как в драме про королей",
    "Экскурсия по самому скучному музею города",
    "Объясняете маме, что такое стрим",
    "Первый день на необитаемом острове — делите роли",
    "Продаёте воздух очень недоверчивому покупателю",
    "Телепорт сломался, и вы очутились в чужой квартире",
    "Самый странный закон, который вы только что придумали",
    "Рассказываете, как на самом деле прошли выходные",
]
MODE_NAMES = {
    "manual": "Вручную",
    "random": "Случайная",
    "suggest": "Идеи игроков",
    "vote": "Голосование",
}
TIME_OPTIONS = (5, 7, 10)
MAX_SUGGESTION_LEN = 200

ADMINS: set = set()
_get_all_users = lambda: []
_app = None


# ------------------------------------------------------------------
# Состояние игры
# ------------------------------------------------------------------
class Game:
    def __init__(self):
        self.phase = "lobby"  # lobby|picking|ready|work|moderation|voting|finished
        self.team_size = 2
        self.sit_mode = "random"
        self.work_minutes = 7
        self.players = {}      # uid -> имя
        self.lobby_msgs = {}   # uid -> message_id
        self.last_count = -1
        self.panels = {}       # admin uid -> message_id
        self.teams = {}        # tid -> {"members": [uid], "sub": dict|None, "kept": bool|None}
        self.user_team = {}    # uid -> tid
        self.situation = None
        self.sit_options = []  # варианты для ручного выбора / голосования
        self.suggestions = {}  # uid -> текст
        self.sit_votes = {}    # uid -> индекс варианта
        self.work_ends = 0.0
        self.pending = {}      # uid -> 'submit' | 'suggest' | 'manual'
        self.in_chat = set()   # uid, которые сейчас пишут в чат команды
        self.order = []        # tid в порядке показа при голосовании
        self.votes = {}        # voter uid -> tid
        self.voters = set()    # все, кто открывал ответы


G = None


def _b(text, data):
    return InlineKeyboardButton(text, callback_data=data)


def _kb(*rows):
    return InlineKeyboardMarkup([list(r) for r in rows])


def _short(text, n=60):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _name(user):
    return user.first_name or (f"@{user.username}" if user.username else str(user.id))


def _names(g, members):
    return ", ".join(g.players.get(u, str(u)) for u in members)


def _cancel_jobs():
    jq = _app.job_queue if _app else None
    if not jq:
        return
    for n in ("sit_work_end", "sit_work_warn"):
        for j in jq.get_jobs_by_name(n):
            j.schedule_removal()


def _active_kind(uid):
    """Что сейчас ждёт игра от пользователя (для фильтра сообщений)."""
    g = G
    if g is None:
        return None
    k = g.pending.get(uid)
    if k == "submit" and g.phase == "work":
        return k
    if k == "suggest" and g.phase == "picking" and g.sit_mode == "suggest":
        return k
    if k == "manual" and uid in ADMINS and g.phase == "picking" and g.sit_mode == "manual":
        return k
    if uid in g.in_chat and g.phase == "work":
        return "chat"
    return None


class _SitActive(MessageFilter):
    def filter(self, message):
        return bool(message.from_user) and _active_kind(message.from_user.id) is not None


# ------------------------------------------------------------------
# Разбивка на команды
# ------------------------------------------------------------------
def make_teams(uids, size):
    uids = list(uids)
    random.shuffle(uids)
    groups = [uids[i:i + size] for i in range(0, len(uids), size)]
    if len(groups) > 1 and len(groups[-1]) == 1:
        lone = groups.pop()[0]
        if size == 2:
            groups[-1].append(lone)            # будет тройка
        else:
            groups.append([groups[-1].pop(), lone])  # [3,3,1] -> [3,2,2]
    return groups


# ------------------------------------------------------------------
# Тексты и клавиатуры
# ------------------------------------------------------------------
def _lobby_text(g):
    return (
        "🎭 Игра «Ситуации»\n\n"
        "✅ Ты в комнате! Ждём, пока админ закроет набор.\n"
        f"👥 Сейчас в комнате: {len(g.players)}\n\n"
        "Как играем: вас случайно разобьют на пары/тройки, дадут ситуацию, "
        "вы вместе придумаете и сдадите сценку, а потом все голосуют за лучшую."
    )


def _lobby_kb():
    return _kb([_b("🚪 Выйти из комнаты", "sit_leave")])


def _panel(g):
    P = len(g.players)
    if g.phase == "lobby":
        mk = lambda ok, s: ("✅ " if ok else "") + s
        text = (
            "🎭 «Ситуации» — набор открыт\n\n"
            f"👥 В комнате: {P}\n"
            f"⚙️ Команды: по {g.team_size}\n"
            f"🎯 Выбор ситуации: {MODE_NAMES[g.sit_mode]}\n"
            f"⏱ Время на сценку: {g.work_minutes} мин"
        )
        kb = _kb(
            [_b(mk(g.team_size == 2, "Пары"), "sit_a_size_2"), _b(mk(g.team_size == 3, "Тройки"), "sit_a_size_3")],
            [_b(mk(g.sit_mode == "manual", "Вручную"), "sit_a_mode_manual"),
             _b(mk(g.sit_mode == "random", "Случайная"), "sit_a_mode_random")],
            [_b(mk(g.sit_mode == "suggest", "Идеи игроков"), "sit_a_mode_suggest"),
             _b(mk(g.sit_mode == "vote", "Голосование"), "sit_a_mode_vote")],
            [_b(mk(g.work_minutes == m, f"{m} мин"), f"sit_a_time_{m}") for m in TIME_OPTIONS],
            [_b("📢 Оповестить всех", "sit_a_notify")],
            [_b("▶️ Закрыть набор и раздать команды", "sit_a_close")],
            [_b("⛔ Остановить игру", "sit_a_stop")],
        )
        return text, kb

    stop = [_b("⛔ Остановить игру", "sit_a_stop")]
    if g.phase == "picking":
        if g.sit_mode == "manual":
            lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(g.sit_options))
            nums = [_b(str(i + 1), f"sit_a_pick_{i}") for i in range(len(g.sit_options))]
            return (
                f"🎯 Команд: {len(g.teams)}. Выбери ситуацию:\n\n{lines}",
                _kb(nums[:3], nums[3:], [_b("🔄 Другие", "sit_a_reroll"), _b("✍️ Своя", "sit_a_own")], stop),
            )
        if g.sit_mode == "suggest":
            lines = "\n".join(f"• {_short(t, 80)}" for t in list(g.suggestions.values())[-15:])
            return (
                f"💡 Игроки присылают ситуации: {len(g.suggestions)}\n\n{lines}",
                _kb([_b("✅ Закрыть сбор и выбрать случайную", "sit_a_endsugg")], stop),
            )
        if g.sit_mode == "vote":
            cnt = Counter(g.sit_votes.values())
            lines = "\n".join(f"{i + 1}. {s} — {cnt.get(i, 0)}" for i, s in enumerate(g.sit_options))
            return (
                f"🗳 Игроки выбирают ситуацию (проголосовало {len(g.sit_votes)}/{P}):\n\n{lines}",
                _kb([_b("✅ Закончить голосование", "sit_a_endsvote")], stop),
            )
    if g.phase == "ready":
        return (
            f"✅ Ситуация выбрана:\n«{g.situation}»\n\nКоманд: {len(g.teams)} · Таймер: {g.work_minutes} мин",
            _kb([_b("▶️ Запустить работу команд", "sit_a_begin")], [_b("🔄 Выбрать другую", "sit_a_reroll")], stop),
        )
    if g.phase == "work":
        left = max(0, int((g.work_ends - time.time()) / 60) + 1)
        done = sum(1 for t in g.teams.values() if t["sub"])
        return (
            f"⏱ Команды работают над ситуацией:\n«{g.situation}»\n\n"
            f"Осталось ≈{left} мин · Сдали: {done}/{len(g.teams)}",
            _kb([_b("⏹ Завершить досрочно", "sit_a_endwork")], stop),
        )
    if g.phase == "moderation":
        subs = [t for t in g.teams.values() if t["sub"]]
        kept = sum(1 for t in subs if t["kept"] is True)
        un = sum(1 for t in subs if t["kept"] is None)
        return (
            f"🧹 Модерация ответов\n\nСдали: {len(subs)}/{len(g.teams)}\n"
            f"✅ Оставлено: {kept} · ❌ Убрано: {len(subs) - kept - un} · не отмечено: {un}\n\n"
            "Отметь ответы в сообщениях выше (непомеченные в голосование не попадут).",
            _kb([_b("🗳 Начать голосование", "sit_a_startvote")], stop),
        )
    if g.phase == "voting":
        cnt = Counter(g.votes.values())
        lines = "\n".join(f"Ответ {i + 1}: {cnt.get(t, 0)}" for i, t in enumerate(g.order))
        return (
            f"🗳 Идёт голосование\nПроголосовало: {len(g.votes)} (смотрели: {len(g.voters)})\n\n{lines}",
            _kb([_b("🏁 Завершить голосование", "sit_a_endvote")], stop),
        )
    return "🏁 Игра завершена. /go — новый раунд.", None


async def _refresh_panels(bot):
    g = G
    if not g:
        return
    text, kb = _panel(g)
    for uid, mid in list(g.panels.items()):
        try:
            await bot.edit_message_text(text, chat_id=uid, message_id=mid, reply_markup=kb)
        except TelegramError:
            pass


async def _send_panel(bot, uid):
    g = G
    text, kb = _panel(g)
    m = await bot.send_message(uid, text, reply_markup=kb)
    g.panels[uid] = m.message_id


async def _safe_send(bot, uid, text, kb=None):
    try:
        return await bot.send_message(uid, text, reply_markup=kb)
    except TelegramError:
        return None


async def _send_sub(bot, chat_id, sub, header, kb=None):
    """Показать сданный ответ (текст или любое медиа)."""
    if sub["kind"] == "text":
        return await bot.send_message(chat_id, f"{header}\n\n{sub['text']}", reply_markup=kb)
    cap = header + (f"\n\n{sub['caption']}" if sub.get("caption") else "")
    try:
        return await bot.copy_message(chat_id, sub["chat_id"], sub["message_id"], caption=cap[:1024], reply_markup=kb)
    except TelegramError:
        await bot.send_message(chat_id, header)
        return await bot.copy_message(chat_id, sub["chat_id"], sub["message_id"], reply_markup=kb)


# ------------------------------------------------------------------
# Команды админа
# ------------------------------------------------------------------
async def go_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global G
    uid = update.effective_user.id
    if uid not in ADMINS:
        await update.message.reply_text("❌ Эта команда только для админов!")
        return
    if G and G.phase != "finished":
        await update.message.reply_text("🎭 Игра уже идёт. Остановить: /sgo")
        await _send_panel(context.bot, uid)
        return
    _cancel_jobs()
    G = Game()
    await _send_panel(context.bot, uid)


async def sgo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("❌ Эта команда только для админов!")
        return
    if G is None:
        await update.message.reply_text("Игра «Ситуации» сейчас не запущена.")
        return
    await _stop_game(context.bot)
    await update.message.reply_text("⛔ Игра «Ситуации» остановлена.")


async def _stop_game(bot):
    global G
    g, G = G, None
    _cancel_jobs()
    if g and g.phase != "finished":
        for uid in list(g.players):
            await _safe_send(bot, uid, "⛔ Игра «Ситуации» остановлена админом.")


# ------------------------------------------------------------------
# Комната (набор игроков)
# ------------------------------------------------------------------
async def _join(bot, uid, name):
    g = G
    g.players[uid] = name
    old = g.lobby_msgs.get(uid)
    if old:
        try:
            await bot.edit_message_text(_lobby_text(g), chat_id=uid, message_id=old, reply_markup=_lobby_kb())
            return
        except TelegramError:
            pass
    m = await bot.send_message(uid, _lobby_text(g), reply_markup=_lobby_kb())
    g.lobby_msgs[uid] = m.message_id


async def _lobby_tick(context: ContextTypes.DEFAULT_TYPE):
    """Раз в 5 секунд обновляет счётчик игроков, если он изменился."""
    g = G
    if not g or g.phase != "lobby" or len(g.players) == g.last_count:
        return
    g.last_count = len(g.players)
    await _refresh_panels(context.bot)
    for uid, mid in list(g.lobby_msgs.items()):
        if uid not in g.players:
            continue
        try:
            await context.bot.edit_message_text(_lobby_text(g), chat_id=uid, message_id=mid, reply_markup=_lobby_kb())
        except TelegramError:
            pass
        await asyncio.sleep(0.04)


async def _menu_entry(update, context):
    q = update.callback_query
    user = q.from_user
    if q.message.chat.type != "private":
        await q.answer(f"Игра — в личке с ботом: @{context.bot.username}", show_alert=True)
        return
    await q.answer()
    g = G
    if g is None or g.phase == "finished":
        await context.bot.send_message(user.id, "🎭 Сейчас игра «Ситуации» не идёт. Следи за анонсами 👀")
        return
    if g.phase == "lobby":
        await _join(context.bot, user.id, _name(user))
        return
    if g.phase == "voting":
        await context.bot.send_message(user.id, _invite_text(g), reply_markup=_kb([_b("🗳 Смотреть ответы и голосовать", "sit_watch")]))
        return
    if user.id in g.user_team:
        await context.bot.send_message(user.id, "🎭 Игра идёт, ты в команде. Загляни в сообщения выше 👆")
    else:
        await context.bot.send_message(user.id, "🎭 Набор уже закрыт. Когда начнётся голосование — жми /vybor и голосуй за лучших!")


# ------------------------------------------------------------------
# Раздача команд и выбор ситуации
# ------------------------------------------------------------------
async def _close_lobby(bot):
    g = G
    if len(g.players) < 2:
        return "Нужно хотя бы 2 игрока"
    groups = make_teams(list(g.players), g.team_size)
    g.teams = {i + 1: {"members": m, "sub": None, "kept": None} for i, m in enumerate(groups)}
    g.user_team = {u: tid for tid, t in g.teams.items() for u in t["members"]}
    g.phase = "picking"
    for uid in g.players:
        t = g.teams[g.user_team[uid]]
        await _safe_send(bot, uid, f"👥 Команды сформированы!\nТвоя команда: {_names(g, t['members'])}\n\nСейчас выбираем ситуацию…")
    await _start_picking(bot)
    return None


async def _start_picking(bot):
    g = G
    g.pending.clear()
    g.suggestions.clear()
    g.sit_votes.clear()
    if g.sit_mode == "random":
        g.situation = random.choice(BANK)
        g.phase = "ready"
    elif g.sit_mode == "manual":
        g.sit_options = random.sample(BANK, min(6, len(BANK)))
    elif g.sit_mode == "suggest":
        for uid in g.players:
            g.pending[uid] = "suggest"
            await _safe_send(bot, uid, "💡 Пришли свою идею ситуации ОДНИМ текстовым сообщением (например: «самый нелепый способ познакомиться»). Бот выберет случайную из присланных.")
    elif g.sit_mode == "vote":
        g.sit_options = random.sample(BANK, min(5, len(BANK)))
        lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(g.sit_options))
        kb = _kb([_b(str(i + 1), f"sit_ov_{i}") for i in range(len(g.sit_options))])
        for uid in g.players:
            await _safe_send(bot, uid, f"🗳 Выбираем ситуацию! Голосуй:\n\n{lines}", kb)
    await _refresh_panels(bot)


def _finish_suggest():
    g = G
    pool = list(g.suggestions.values()) or BANK
    g.situation = random.choice(pool)
    g.pending = {u: k for u, k in g.pending.items() if k != "suggest"}
    g.phase = "ready"


def _finish_vote():
    g = G
    cnt = Counter(g.sit_votes.values())
    if cnt:
        top = max(cnt.values())
        i = random.choice([k for k, v in cnt.items() if v == top])
    else:
        i = random.randrange(len(g.sit_options))
    g.situation = g.sit_options[i]
    g.phase = "ready"


# ------------------------------------------------------------------
# Работа команд
# ------------------------------------------------------------------
def _work_kb():
    return _kb([_b("💬 Войти в чат команды", "sit_chat_on")], [_b("✅ Сдать ответ", "sit_submit")])


async def _begin_work(bot):
    g = G
    g.phase = "work"
    g.work_ends = time.time() + g.work_minutes * 60
    jq = _app.job_queue
    if jq:
        jq.run_once(_work_end_job, g.work_minutes * 60, name="sit_work_end")
        if g.work_minutes > 1:
            jq.run_once(_work_warn_job, (g.work_minutes - 1) * 60, name="sit_work_warn")
    for tid, t in g.teams.items():
        text = (
            f"🎭 СИТУАЦИЯ:\n«{g.situation}»\n\n"
            f"👥 Команда: {_names(g, t['members'])}\n⏱ Время: {g.work_minutes} мин\n\n"
            "1️⃣ Нажми «Войти в чат команды» — всё, что ты пишешь боту (текст, фото, видео, голосовые, кружки, стикеры), увидят напарники, как в обычной беседе.\n"
            "2️⃣ Когда итог готов — «Сдать ответ» и отправь его одним сообщением (текст, видео, гс — что угодно). Сдать можно заново, пока идёт время."
        )
        for uid in t["members"]:
            await _safe_send(bot, uid, text, _work_kb())
    await _refresh_panels(bot)


async def _work_warn_job(context: ContextTypes.DEFAULT_TYPE):
    g = G
    if g and g.phase == "work":
        for uid in g.user_team:
            await _safe_send(context.bot, uid, "⏰ Осталась 1 минута! Не забудь сдать ответ.")


async def _work_end_job(context: ContextTypes.DEFAULT_TYPE):
    if G and G.phase == "work":
        await _end_work(context.bot)


async def _end_work(bot):
    g = G
    _cancel_jobs()
    g.phase = "moderation"
    g.in_chat.clear()
    g.pending.clear()
    for uid in g.user_team:
        t = g.teams[g.user_team[uid]]
        txt = "⏹ Время вышло! Ответ " + ("принят ✅" if t["sub"] else "не сдан 😕") + ". Ждём голосования."
        await _safe_send(bot, uid, txt)
    for admin in g.panels:
        no = [tid for tid, t in g.teams.items() if not t["sub"]]
        if no:
            await _safe_send(bot, admin, "Не сдали: " + "; ".join(f"#{t} ({_names(g, g.teams[t]['members'])})" for t in no))
        for tid, t in g.teams.items():
            if t["sub"]:
                try:
                    await _send_sub(bot, admin, t["sub"], f"Команда #{tid}: {_names(g, t['members'])}", _mod_kb(tid, None))
                except TelegramError:
                    logger.exception("Не удалось показать ответ команды %s админу", tid)
    await _refresh_panels(bot)


def _mod_kb(tid, kept):
    return _kb([
        _b("✅ Оставить" + (" ✔" if kept is True else ""), f"sit_a_m_{tid}_1"),
        _b("❌ Убрать" + (" ✔" if kept is False else ""), f"sit_a_m_{tid}_0"),
    ])


async def _copy_with_label(bot, to, msg, name):
    cap_types = msg.photo or msg.video or msg.voice or msg.audio or msg.document or msg.animation
    if msg.text:
        await bot.send_message(to, f"👤 {name}: {msg.text}")
    elif cap_types:
        cap = f"👤 {name}" + (f": {msg.caption}" if msg.caption else "")
        await bot.copy_message(to, msg.chat_id, msg.message_id, caption=cap[:1024])
    else:  # кружки, стикеры и т.п. — без подписи, поэтому отдельной строкой
        await bot.send_message(to, f"👤 {name}:")
        await bot.copy_message(to, msg.chat_id, msg.message_id)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единая точка для сообщений игроков: чат команды, сдача ответа, идеи, ручная ситуация."""
    msg = update.effective_message
    uid = update.effective_user.id
    g = G
    kind = _active_kind(uid)
    if g is None or kind is None:
        return
    bot = context.bot

    if kind == "manual":
        if not msg.text:
            await msg.reply_text("Нужен текст ситуации.")
            return
        g.pending.pop(uid, None)
        g.situation = msg.text.strip()[:MAX_SUGGESTION_LEN]
        g.phase = "ready"
        await _refresh_panels(bot)
        return

    if kind == "suggest":
        if not msg.text:
            await msg.reply_text("Пришли идею текстом 🙂")
            return
        g.suggestions[uid] = msg.text.strip()[:MAX_SUGGESTION_LEN]
        g.pending.pop(uid, None)
        await msg.reply_text("✅ Идея принята!")
        await _refresh_panels(bot)
        return

    tid = g.user_team.get(uid)
    if tid is None:
        return
    team = g.teams[tid]

    if kind == "submit":
        g.pending.pop(uid, None)
        sub = {
            "kind": "text" if msg.text else "media",
            "text": msg.text,
            "caption": msg.caption,
            "chat_id": msg.chat_id,
            "message_id": msg.message_id,
            "by": g.players.get(uid, str(uid)),
        }
        team["sub"] = sub
        await msg.reply_text("✅ Ответ сдан! Можно пересдать кнопкой «Сдать ответ», пока идёт время.")
        for m in team["members"]:
            if m != uid:
                await _safe_send(bot, m, f"✅ {sub['by']} сдал(а) ответ команды.")
        await _refresh_panels(bot)
        return

    # kind == "chat": пересылаем остальным членам команды
    name = g.players.get(uid, str(uid))
    for m in team["members"]:
        if m != uid:
            try:
                await _copy_with_label(bot, m, msg, name)
            except TelegramError:
                logger.exception("Не удалось переслать сообщение %s -> %s", uid, m)


# ------------------------------------------------------------------
# Голосование за ответы
# ------------------------------------------------------------------
def _invite_text(g):
    return (
        "🗳 ГОЛОСОВАНИЕ — игра «Ситуации»\n\n"
        f"Тема: «{g.situation}»\n\n"
        "Команды придумали свои сценки на эту тему. Листай ответы кнопками ◀️ ▶️ "
        "и жми «Голосовать» под тем, который понравился больше всего. "
        "Голос можно поменять, пока голосование открыто. За свою команду голосовать нельзя."
    )


def _viewer_kb(g, uid, idx):
    n = len(g.order)
    tid = g.order[idx]
    mine = g.votes.get(uid) == tid
    return _kb(
        [_b("◀️", f"sit_v_{(idx - 1) % n}"), _b(f"{idx + 1}/{n}", "sit_noop"), _b("▶️", f"sit_v_{(idx + 1) % n}")],
        [_b("✅ Твой голос здесь" if mine else "🗳 Голосовать за этот ответ", f"sit_vote_{tid}")],
    )


async def _show_answer(bot, uid, idx):
    g = G
    tid = g.order[idx]
    await _send_sub(bot, uid, g.teams[tid]["sub"], f"Ответ №{idx + 1}", _viewer_kb(g, uid, idx))


async def vybor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text(f"🗳 Голосование — в личке с ботом: https://t.me/{context.bot.username}")
        return
    g = G
    if not g or g.phase != "voting":
        await update.message.reply_text("🗳 Сейчас голосования нет. Следи за стримом 👀")
        return
    await update.message.reply_text(_invite_text(g), reply_markup=_kb([_b("🗳 Смотреть ответы и голосовать", "sit_watch")]))


async def _start_voting(bot):
    g = G
    g.order = [tid for tid, t in g.teams.items() if t["sub"] and t["kept"] is True]
    random.shuffle(g.order)
    g.votes.clear()
    g.voters.clear()
    g.phase = "voting"
    kb = _kb([_b("🗳 Смотреть ответы и голосовать", "sit_watch")])
    for uid in g.players:
        await _safe_send(bot, uid, _invite_text(g), kb)
    await _refresh_panels(bot)


async def _finish_voting(bot):
    g = G
    g.phase = "finished"
    cnt = Counter(g.votes.values())
    ranking = sorted(g.order, key=lambda t: -cnt.get(t, 0))
    top = cnt.get(ranking[0], 0) if ranking else 0
    winners = [t for t in ranking if cnt.get(t, 0) == top]
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, t in enumerate(ranking):
        mark = "🏆" if t in winners and top > 0 else (medals[i] if i < 3 else "▫️")
        lines.append(f"{mark} Команда {_names(g, g.teams[t]['members'])} — голосов: {cnt.get(t, 0)}")
    text = f"🏁 Итоги «Ситуаций»\nТема: «{g.situation}»\n\n" + "\n".join(lines)
    if top == 0:
        text += "\n\nГолосов не было 🤷"
    recipients = set(g.players) | g.voters | set(g.panels)
    for uid in recipients:
        await _safe_send(bot, uid, text)
        if top > 0:
            for t in winners:
                try:
                    await _send_sub(bot, uid, g.teams[t]["sub"], f"🏆 Победитель: {_names(g, g.teams[t]['members'])}")
                except TelegramError:
                    pass
    await _refresh_panels(bot)


# ------------------------------------------------------------------
# Единый обработчик кнопок
# ------------------------------------------------------------------
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    bot = context.bot
    g = G

    if data == "sit_noop":
        await q.answer()
        return
    if data == "sit_menu":
        await _menu_entry(update, context)
        return

    # ---------------- админ ----------------
    if data.startswith("sit_a_"):
        if uid not in ADMINS:
            await q.answer("Только для админа", show_alert=True)
            return
        if g is None:
            await q.answer("Игра не запущена. /go — запустить", show_alert=True)
            return
        a = data[len("sit_a_"):]

        if a == "stop":
            await q.answer("Игра остановлена")
            await _stop_game(bot)
            try:
                await q.message.edit_text("⛔ Игра «Ситуации» остановлена. /go — новая игра.")
            except TelegramError:
                pass
            return

        if a.startswith(("size_", "mode_", "time_")) and g.phase == "lobby":
            kind, val = a.split("_", 1)
            if kind == "size":
                g.team_size = int(val)
            elif kind == "mode":
                g.sit_mode = val
            else:
                g.work_minutes = int(val)
            await q.answer()
        elif a == "notify" and g.phase == "lobby":
            kb = _kb([_b("🎭 Войти в комнату", "sit_menu")])
            sent = 0
            for u in list(_get_all_users()):
                if u in g.players:
                    continue
                if await _safe_send(bot, u, "🎭 Начинается игра «Ситуации»! Заходи в комнату 👇", kb):
                    sent += 1
                await asyncio.sleep(0.05)
            await q.answer(f"Отправлено: {sent}", show_alert=True)
        elif a == "close" and g.phase == "lobby":
            await q.answer()
            err = await _close_lobby(bot)
            if err:
                await q.answer(err, show_alert=True)
        elif a.startswith("pick_") and g.phase == "picking" and g.sit_mode == "manual":
            i = int(a[5:])
            if 0 <= i < len(g.sit_options):
                g.situation = g.sit_options[i]
                g.phase = "ready"
            await q.answer()
        elif a == "own" and g.phase == "picking" and g.sit_mode == "manual":
            g.pending[uid] = "manual"
            await q.answer()
            await _safe_send(bot, uid, "✍️ Напиши текст ситуации одним сообщением.")
        elif a == "reroll" and g.phase in ("picking", "ready"):
            if g.sit_mode == "manual":
                g.phase = "picking"
                g.sit_options = random.sample(BANK, min(6, len(BANK)))
            else:
                g.situation = random.choice(list(g.suggestions.values()) or BANK)
                g.phase = "ready"
            await q.answer()
        elif a == "endsugg" and g.phase == "picking" and g.sit_mode == "suggest":
            _finish_suggest()
            await q.answer()
        elif a == "endsvote" and g.phase == "picking" and g.sit_mode == "vote":
            _finish_vote()
            await q.answer()
        elif a == "begin" and g.phase == "ready":
            await q.answer("Работа началась")
            await _begin_work(bot)
            return
        elif a == "endwork" and g.phase == "work":
            await q.answer()
            await _end_work(bot)
            return
        elif a.startswith("m_") and g.phase == "moderation":
            _, tid, flag = a.split("_")
            t = g.teams.get(int(tid))
            if t and t["sub"]:
                t["kept"] = flag == "1"
                try:
                    await q.message.edit_reply_markup(_mod_kb(int(tid), t["kept"]))
                except TelegramError:
                    pass
            await q.answer()
        elif a == "startvote" and g.phase == "moderation":
            kept = [t for t in g.teams.values() if t["sub"] and t["kept"] is True]
            if len(kept) < 2:
                await q.answer("Нужно оставить минимум 2 ответа", show_alert=True)
                return
            await q.answer("Голосование запущено")
            await _start_voting(bot)
            return
        elif a == "endvote" and g.phase == "voting":
            await q.answer()
            await _finish_voting(bot)
            return
        else:
            await q.answer("Сейчас это недоступно")
            return
        await _refresh_panels(bot)
        return

    # ---------------- игроки ----------------
    if g is None:
        await q.answer("Игра уже закончилась", show_alert=True)
        return

    if data == "sit_leave":
        if g.phase == "lobby":
            g.players.pop(uid, None)
            g.lobby_msgs.pop(uid, None)
            await q.answer("Ты вышел из комнаты")
            try:
                await q.message.edit_text("🚪 Ты вышел из комнаты. Вернуться можно через меню бота.")
            except TelegramError:
                pass
        else:
            await q.answer("Набор уже закрыт", show_alert=True)
        return

    if data.startswith("sit_ov_") and g.phase == "picking" and g.sit_mode == "vote" and uid in g.players:
        i = int(data[7:])
        if 0 <= i < len(g.sit_options):
            g.sit_votes[uid] = i
            await q.answer(f"Голос за вариант {i + 1} принят")
            await _refresh_panels(bot)
        return

    if data == "sit_chat_on":
        if g.phase != "work" or uid not in g.user_team:
            await q.answer("Чат сейчас недоступен", show_alert=True)
            return
        g.in_chat.add(uid)
        await q.answer()
        await _safe_send(bot, uid, "💬 Ты в чате команды. Пиши, отправляй фото, видео, гс — всё придёт напарникам.", _kb([_b("🚪 Выйти из чата", "sit_chat_off")]))
        for m in g.teams[g.user_team[uid]]["members"]:
            if m != uid:
                await _safe_send(bot, m, f"💬 {g.players.get(uid)} зашёл(ла) в чат команды.")
        return

    if data == "sit_chat_off":
        g.in_chat.discard(uid)
        await q.answer("Ты вышел из чата")
        return

    if data == "sit_submit":
        if g.phase != "work" or uid not in g.user_team:
            await q.answer("Сдача ответов сейчас закрыта", show_alert=True)
            return
        g.pending[uid] = "submit"
        await q.answer()
        await _safe_send(bot, uid, "📨 Отправь итог ОДНИМ сообщением: текст, фото, видео, гс или кружок.", _kb([_b("↩️ Отмена", "sit_submit_cancel")]))
        return

    if data == "sit_submit_cancel":
        if g.pending.get(uid) == "submit":
            g.pending.pop(uid, None)
        await q.answer("Отменено")
        return

    if data == "sit_watch":
        if g.phase != "voting" or not g.order:
            await q.answer("Голосование не идёт", show_alert=True)
            return
        g.voters.add(uid)
        await q.answer()
        await _show_answer(bot, uid, 0)
        return

    if data.startswith("sit_v_"):
        if g.phase != "voting" or not g.order:
            await q.answer("Голосование уже закончилось", show_alert=True)
            return
        idx = int(data[6:]) % len(g.order)
        await q.answer()
        try:
            await q.message.delete()
        except TelegramError:
            pass
        await _show_answer(bot, uid, idx)
        return

    if data.startswith("sit_vote_"):
        if g.phase != "voting":
            await q.answer("Голосование уже закончилось", show_alert=True)
            return
        tid = int(data[9:])
        if tid not in g.order:
            await q.answer()
            return
        if uid in g.teams[tid]["members"]:
            await q.answer("За свою команду голосовать нельзя 🙂", show_alert=True)
            return
        g.votes[uid] = tid
        g.voters.add(uid)
        await q.answer("✅ Голос засчитан")
        try:
            await q.message.edit_reply_markup(_viewer_kb(g, uid, g.order.index(tid)))
        except TelegramError:
            pass
        await _refresh_panels(bot)
        return

    await q.answer()


# ------------------------------------------------------------------
# Подключение
# ------------------------------------------------------------------
def register(app, admin_ids, get_all_users=None):
    """Вызвать в main() ДО регистрации общих MessageHandler (receive_message)."""
    global ADMINS, _get_all_users, _app
    ADMINS = set(int(a) for a in admin_ids)
    if get_all_users:
        _get_all_users = get_all_users
    _app = app
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("go", go_command, filters=private))
    app.add_handler(CommandHandler("sgo", sgo_command, filters=private))
    app.add_handler(CommandHandler("vybor", vybor_command))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^sit_"))
    app.add_handler(MessageHandler(private & filters.UpdateType.MESSAGE & ~filters.COMMAND & _SitActive(), on_message))
    if app.job_queue:
        app.job_queue.run_repeating(_lobby_tick, interval=5, first=5)
    else:
        logger.warning("JobQueue недоступен — таймеры игры «Ситуации» работать не будут")
