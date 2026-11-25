"""
Игра «Ситуации» для Telegram-бота (python-telegram-bot 21+).

Только обычный чат с ботом (Mini App не затрагивается).
Админ:  /go — открыть набор и панель, /sgo — остановить игру,
        /sits — банк ситуаций, /addsit <текст> — добавить, /delsit <номера> — удалить.
Все:    кнопка «🎭 Ситуации» в меню (вход в комнату), /vybor — голосование.

Подключение в bot.py (см. вызов situations.register в main()):
    situations.register(app, admin_ids, lambda: all_users,
                        storage=github_storage, stat_hook=..., claim=..., busy=...)

Состояние игры хранится в памяти (при перезапуске бота раунд сбрасывается),
банк ситуаций — на GitHub (situations_bank.json).
"""
import asyncio
import logging
import math
import random
import time
from collections import Counter, deque

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
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
DEFAULT_BANK = [
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
BANK = list(DEFAULT_BANK)

BANK_FILE = "situations_bank.json"

MODE_NAMES = {
    "manual": "Вручную",
    "random": "Случайная",
    "suggest": "Идеи игроков",
    "vote": "Голосование",
}
TIME_OPTIONS = (7, 10, 15)
MAX_SUGGESTION_LEN = 800
MAX_MEDIA_BYTES = 20 * 1024 * 1024       # лимит на размер файла в чате/ответе
MAX_SUB_TEXT = 3800                       # текст ответа/реплики не длиннее (лимит TG 4096)
CHAT_FLOOD = (15, 10)                     # не больше 15 сообщений за 10 с в чате команды
CB_FLOOD = (8, 10)                        # не больше 8 нажатий листания за 10 с
SEND_BATCH = 20                           # сообщений одновременно (лимит TG ≈ 30/сек)
SEND_PAUSE = 1.05                         # пауза между пачками, сек
NOTIFY_COOLDOWN = 60                      # «Оповестить всех» — не чаще раза в минуту
TICK_EVERY = 3                            # период фонового тика, сек
SG_MAX_BUTTONS = 40                       # сколько идей показываем кнопками
CONTACT_COOLDOWN = 20                     # «Связь с админом» — не чаще раза в 20 сек на команду
VOTE_OPTIONS_MAX = 10                     # сколько идей максимум выносим на голосование игроков

ADMINS: set = set()
_get_all_users = lambda: []
_stat_hook = None          # callable({uid: {"sit_played": 1, "sit_wins": 1}})
_claim = lambda uid: True  # забрать пользователя у других режимов бота
_busy = lambda uid: False  # True, если пользователь сейчас в другом режиме бота
_storage = None
_app = None

_locks = {}
_tasks = set()
_hits = {}
_dirty_panels = False
_last_panel = 0.0
_last_lobby = 0.0


def _lk(name):
    """Ленивые asyncio.Lock (чтобы не привязываться к циклу событий при импорте)."""
    if name not in _locks:
        _locks[name] = asyncio.Lock()
    return _locks[name]


# ------------------------------------------------------------------
# Состояние игры
# ------------------------------------------------------------------
class Game:
    def __init__(self):
        self.phase = "lobby"  # lobby|picking|ready|work|moderation|voting|finished
        self.team_size = 2
        self.sit_mode = "random"
        self.work_minutes = 7
        self.round = 1
        self.players = {}      # uid -> имя (включая запас)
        self.lobby_msgs = {}   # uid -> message_id сообщения комнаты
        self.last_count = -1
        self.panels = {}       # admin uid -> message_id панели
        self.teams = {}        # tid -> {"members": [uid], "sub": dict|None, "kept": bool|None}
        self.user_team = {}    # uid -> tid (производное, см. rebuild)
        self.reserve = set()   # игроки «в запасе» (опоздавшие / замены)
        self.gone = set()      # заблокировали бота / вышли
        self.situation = None
        self.sit_options = []
        self.suggestions = {}  # uid -> текст
        self.sg_sel = set()    # выбранные идеи для переноса в банк (индексы)
        self.sit_votes = {}    # uid -> индекс варианта (режим «голосование»)
        self.work_ends = 0.0
        self.pending = {}      # uid -> 'submit' | 'suggest' | 'manual'
        self.in_chat = set()   # кто сейчас в чате команды
        self.order = []        # tid в порядке показа при голосовании
        self.votes = {}        # voter uid -> tid
        self.voters = set()    # все, кто открывал ответы
        self.stats_done = False
        self.last_notify = 0.0
        self.extended = False      # доп. время уже выдавалось
        self.voting_sit = False    # идёт голосование игроков за ситуацию
        self.sg_closed = False     # сбор идей закрыт, админ отбирает
        self.sg_off = set()        # uid авторов идей, убранных админом
        self.sg_pick = False       # режим «выбрать одну идею вручную»
        self.admin_chat = {}       # admin uid -> tid (с какой командой админ сейчас в чате)
        self.last_req = {}         # tid -> время последнего запроса «связь с админом»
        self.cards = {}            # "admin:tid" -> message_id карточки ответа у админа

    def rebuild(self):
        self.user_team = {u: tid for tid, t in self.teams.items() for u in t["members"]}


G = None


def _touch():
    """Пометить панели админов «грязными»: фоновый тик сам их обновит (без флуда правок)."""
    global _dirty_panels
    _dirty_panels = True


def _bank():
    return BANK if BANK else list(DEFAULT_BANK)


def _b(text, data):
    return InlineKeyboardButton(text, callback_data=data)


def _kb(*rows):
    rows = [list(r) for r in rows if r]          # пустые ряды Telegram не любит
    return InlineKeyboardMarkup(rows) if rows else None


def _short(text, n=60):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _name(user):
    return user.first_name or (f"@{user.username}" if user.username else str(user.id))


def _names(g, members):
    return ", ".join(g.players.get(u, str(u)) for u in members)


def _flood(uid, key, limit, window):
    """True, если пользователь превысил лимит действий (скользящее окно)."""
    now = time.monotonic()
    dq = _hits.setdefault((uid, key), deque())
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= limit:
        return True
    dq.append(now)
    return False


def _spawn(coro):
    """Фоновая задача (долгие рассылки не должны блокировать обработку апдейтов)."""
    t = asyncio.get_running_loop().create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return t


def _cancel_jobs():
    jq = _app.job_queue if _app else None
    if not jq:
        return
    for n in ("sit_work_end", "sit_work_warn"):
        for j in jq.get_jobs_by_name(n):
            j.schedule_removal()


# ------------------------------------------------------------------
# Отправка: устойчивая к блокировкам и лимитам Telegram
# ------------------------------------------------------------------
async def _on_blocked(bot, uid):
    """Пользователь заблокировал бота / чат недоступен — убираем его из игры."""
    g = G
    if not g or uid in ADMINS or uid in g.gone:
        return
    g.gone.add(uid)
    logger.info("Ситуации: пользователь %s недоступен — выбывает из игры", uid)
    if g.phase == "lobby":
        g.players.pop(uid, None)
        g.lobby_msgs.pop(uid, None)
        _touch()
        return
    if uid in g.players:
        await _remove_player(bot, uid, "бот недоступен (заблокирован)")


async def _send(bot, uid, text, kb=None):
    """send_message с повтором при RetryAfter; None — если не доставлено."""
    for _ in range(2):
        try:
            return await bot.send_message(uid, text, reply_markup=kb)
        except RetryAfter as e:
            await asyncio.sleep(float(e.retry_after) + 0.5)
        except Forbidden:
            await _on_blocked(bot, uid)
            return None
        except BadRequest as e:
            if "chat not found" in str(e).lower():
                await _on_blocked(bot, uid)
            else:
                logger.warning("send_message %s: %s", uid, e)
            return None
        except TelegramError as e:
            logger.warning("send_message %s: %s", uid, e)
            return None
    return None


async def _copy(bot, to, from_chat, mid, caption=None, kb=None):
    for _ in range(2):
        try:
            kw = {}
            if caption is not None:
                kw["caption"] = caption
            return await bot.copy_message(to, from_chat, mid, reply_markup=kb, **kw)
        except RetryAfter as e:
            await asyncio.sleep(float(e.retry_after) + 0.5)
        except Forbidden:
            await _on_blocked(bot, to)
            return None
        except TelegramError as e:
            logger.warning("copy_message %s->%s: %s", from_chat, to, e)
            return None
    return None


async def _edit(bot, chat_id, mid, text, kb=None):
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=mid, reply_markup=kb)
        return True
    except RetryAfter as e:
        await asyncio.sleep(float(e.retry_after) + 0.5)
        return False
    except BadRequest as e:
        return "not modified" in str(e).lower()
    except Forbidden:
        await _on_blocked(bot, chat_id)
        return False
    except TelegramError:
        return False


async def _paced(items, fn, per_batch=SEND_BATCH, pause=SEND_PAUSE):
    """Выполняет fn(item) пачками по per_batch с паузой — чтобы не упереться в лимиты Telegram."""
    for i in range(0, len(items), per_batch):
        chunk = items[i:i + per_batch]
        res = await asyncio.gather(*(fn(x) for x in chunk), return_exceptions=True)
        for r in res:
            if isinstance(r, Exception):
                logger.warning("Ситуации: ошибка рассылки: %r", r)
        if i + per_batch < len(items):
            await asyncio.sleep(pause)


async def _send_many(bot, uids, text, kb=None):
    """Рассылка одного текста пачками. text может быть строкой или функцией uid -> str."""
    g = G
    targets = [u for u in uids if not (g and u in g.gone)]

    async def one(u):
        await _send(bot, u, text(u) if callable(text) else text, kb)

    await _paced(targets, one)


async def _notify_admins(bot, text, kb=None):
    for a in list(ADMINS):
        await _send(bot, a, text, kb)


# ------------------------------------------------------------------
# Какие сообщения игры «ловят» (фильтр для MessageHandler)
# ------------------------------------------------------------------
def _active_kind(uid):
    """Что сейчас ждёт игра от пользователя. None — игра ничего не ждёт (или он занят другим режимом бота)."""
    g = G
    if g is None or _busy(uid):
        return None
    k = g.pending.get(uid)
    if k == "submit" and g.phase == "work":
        return "submit"
    if k == "suggest" and g.phase == "picking" and g.sit_mode == "suggest" and not g.sg_closed:
        return "suggest"
    if k == "manual" and uid in ADMINS and g.phase == "picking" and g.sit_mode == "manual":
        return "manual"
    if k and k.startswith("edit:") and uid in ADMINS and g.phase == "moderation":
        return "edit"
    if uid in ADMINS and uid in g.admin_chat and g.phase in ("work", "moderation"):
        return "achat"
    if uid in g.in_chat and uid in g.user_team and g.phase in ("work", "moderation"):
        return "chat"
    if g.phase == "work" and uid in g.user_team:
        return "hint"
    return None


class _SitActive(MessageFilter):
    def filter(self, message):
        return bool(message.from_user) and _active_kind(message.from_user.id) is not None


def _content_info(msg):
    """(тип, можно_ли_подпись, размер) или None для неподдерживаемых типов сообщений."""
    if msg.text:
        return "text", False, 0
    for attr, cap in (("photo", True), ("video", True), ("voice", True), ("audio", True),
                      ("document", True), ("animation", True), ("video_note", False), ("sticker", False)):
        v = getattr(msg, attr, None)
        if v:
            obj = v[-1] if attr == "photo" else v
            return attr, cap, (getattr(obj, "file_size", 0) or 0)
    return None


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
            groups[-1].append(lone)                  # будет тройка
        else:
            groups.append([groups[-1].pop(), lone])  # [3,3,1] -> [3,2,2]
    return groups


# ------------------------------------------------------------------
# Тексты и клавиатуры
# ------------------------------------------------------------------
def _lobby_text(g):
    return (
        "🎭 ИГРА «СИТУАЦИИ»\n\n"
        f"✅ Ты в комнате!   👥 Сейчас здесь: {len(g.players)}\n\n"
        "Как играем:\n"
        "1️⃣ Вас случайно делят на пары или тройки\n"
        "2️⃣ Все получают одну ситуацию\n"
        "3️⃣ В закрытом чате команды придумываете сценку: текст, фото, видео, гс, кружки — что угодно\n"
        "4️⃣ Сдаёте итог до конца таймера\n"
        "5️⃣ Админ проверяет ответы, и все голосуют за лучший 🏆\n\n"
        "Ждём, пока админ закроет набор…"
    )


def _lobby_kb():
    return _kb([_b("🚪 Выйти из комнаты", "sit_leave")])


def _work_kb():
    return _kb(
        [_b("💬 Войти в чат команды", "sit_chat_on")],
        [_b("✅ Сдать ответ", "sit_submit")],
        [_b("📞 Связь с админом", "sit_contact")],
        [_b("🚪 Покинуть игру", "sit_quit")],
    )


def _mod_player_kb():
    return _kb(
        [_b("💬 Войти в чат команды", "sit_chat_on")],
        [_b("📞 Связь с админом", "sit_contact")],
    )


def _team_intro(g, tid):
    t = g.teams[tid]
    return f"👥 Твоя команда (#{tid}): {_names(g, t['members'])}"


def _work_text(g, t):
    left = max(1, math.ceil((g.work_ends - time.time()) / 60)) if g.phase == "work" else g.work_minutes
    return (
        f"🎭 СИТУАЦИЯ\n«{g.situation}»\n\n"
        f"👥 Команда: {_names(g, t['members'])}\n⏱ Времени: ≈{left} мин\n\n"
        "1️⃣ «Войти в чат команды» — всё, что ты пишешь боту (текст, фото, видео, гс, кружки, стикеры), "
        "увидят напарники.\n"
        "2️⃣ Итог готов — «Сдать ответ» и отправь ОДНИМ сообщением. Пересдать можно, пока идёт время.\n"
        "3️⃣ Что-то не так? «Связь с админом»."
    )


def _ideas(g):
    """[(uid, text, kept)] в порядке поступления."""
    return [(u, t, u not in g.sg_off) for u, t in g.suggestions.items()]


def _kept_ideas(g):
    return [t for u, t, k in _ideas(g) if k]


def _extra_rows(g):
    rows = []
    if g.teams:
        rows.append([_b("👥 Составы команд", "sit_a_teams")])
    if g.suggestions and g.phase in ("ready", "finished"):
        rows.append([_b("💾 Оставленные идеи — в банк", "sit_a_sgbank")])
    return rows


def _panel(g):
    P = len(g.players)
    stop = [_b("⛔ Остановить игру", "sit_a_stop")]
    ex = _extra_rows(g)
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
            stop,
        )
        return text, kb

    if g.phase == "picking":
        if g.voting_sit:
            cnt = Counter(g.sit_votes.values())
            lines = "\n".join(f"{i + 1}. {_short(s, 90)} — {cnt.get(i, 0)}" for i, s in enumerate(g.sit_options))
            return (
                f"🗳 Игроки выбирают ситуацию (проголосовало {len(g.sit_votes)}/{P}):\n\n{lines}",
                _kb([_b("✅ Закончить голосование", "sit_a_endsvote")], *ex, stop),
            )
        if g.sit_mode == "manual":
            lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(g.sit_options))
            nums = [_b(str(i + 1), f"sit_a_pick_{i}") for i in range(len(g.sit_options))]
            return (
                f"🎯 Команд: {len(g.teams)}. Выбери ситуацию:\n\n{lines}",
                _kb(nums[:3], nums[3:], [_b("🔄 Другие", "sit_a_reroll"), _b("✍️ Своя", "sit_a_own")], *ex, stop),
            )
        if g.sit_mode == "suggest" and not g.sg_closed:
            lines = "\n".join(f"• {_short(t, 80)}" for t in list(g.suggestions.values())[-15:])
            return (
                f"💡 Игроки присылают ситуации: {len(g.suggestions)}\n\n{lines}",
                _kb([_b("✅ Закрыть сбор и отобрать идеи", "sit_a_endsugg")], *ex, stop),
            )
        if g.sit_mode == "suggest":
            ideas = _ideas(g)[:SG_MAX_BUTTONS]
            kept = sum(1 for _, _, k in _ideas(g) if k)
            lines = "\n".join(f"{'✅' if k else '❌'} {i + 1}. {_short(t, 70)}" for i, (_, t, k) in enumerate(ideas))
            if g.sg_pick:
                head = "👆 Нажми номер идеи, которую берём:"
                btns = [_b(str(i + 1), f"sit_a_sgp_{i}") for i, (_, _, k) in enumerate(ideas) if k]
                acts = [[_b("↩️ Назад к отбору", "sit_a_sgmanual")]]
            else:
                head = "Нажми на номер, чтобы убрать ❌ или вернуть ✅ идею."
                btns = [_b(("✅" if k else "❌") + str(i + 1), f"sit_a_sgx_{i}") for i, (_, _, k) in enumerate(ideas)]
                acts = [[_b("🎲 Случайная из оставшихся", "sit_a_sgrand")],
                        [_b("🗳 Голосование игроков", "sit_a_sgvote")],
                        [_b("👆 Выбрать вручную", "sit_a_sgmanual")],
                        [_b("💾 Оставленные — в банк", "sit_a_sgbank")]]
            grid = [btns[i:i + 5] for i in range(0, len(btns), 5)]
            more = f"\n…и ещё {len(g.suggestions) - SG_MAX_BUTTONS}" if len(g.suggestions) > SG_MAX_BUTTONS else ""
            empty = "\n\n⚠️ Идей нет — будет взята случайная из банка." if not g.suggestions else ""
            return (
                f"💡 Идеи игроков: всего {len(g.suggestions)}, оставлено {kept}\n\n{lines}{more}{empty}\n\n{head}",
                _kb(*grid, *acts, *ex, stop),
            )
    if g.phase == "ready":
        return (
            f"✅ Ситуация выбрана:\n«{g.situation}»\n\nКоманд: {len(g.teams)} · Таймер: {g.work_minutes} мин",
            _kb([_b("▶️ Запустить работу команд", "sit_a_begin")],
                [_b("🔄 Выбрать другую", "sit_a_reroll")], *ex, stop),
        )
    if g.phase == "work":
        left = max(0, math.ceil((g.work_ends - time.time()) / 60))
        done = sum(1 for t in g.teams.values() if t["sub"])
        chats = ", ".join(f"#{t}" for t in sorted(set(g.admin_chat.values())))
        return (
            f"⏱ Команды работают над ситуацией:\n«{g.situation}»\n\n"
            f"Осталось ≈{left} мин · Сдали: {done}/{len(g.teams)}"
            + (f" · В запасе: {len(g.reserve)}" if g.reserve else "")
            + (f"\n💬 Ты в чате команд: {chats}" if chats else ""),
            _kb([_b("➕ 2 минуты", "sit_a_plus"), _b("⏹ Завершить досрочно", "sit_a_endwork")], *ex, stop),
        )
    if g.phase == "moderation":
        subs = [t for t in g.teams.values() if t["sub"]]
        kept = sum(1 for t in subs if t["kept"] is True)
        un = sum(1 for t in subs if t["kept"] is None)
        chats = ", ".join(f"#{t}" for t in sorted(set(g.admin_chat.values())))
        return (
            f"🧹 Модерация ответов (игрокам сказано: проверка 3–5 минут)\n\nСдали: {len(subs)}/{len(g.teams)}\n"
            f"✅ Оставлено: {kept} · ❌ Убрано: {len(subs) - kept - un} · не отмечено: {un}\n"
            + (f"💬 Ты в чате команд: {chats}\n" if chats else "")
            + "\nПод каждым ответом выше: Оставить / Убрать / 💬 Связь / ✏️ Править. "
              "Непомеченные в голосование не попадут.",
            _kb([_b("✅ Оставить все сданные", "sit_a_keepall")],
                [_b("🗳 Начать голосование", "sit_a_startvote")], *ex, stop),
        )
    if g.phase == "voting":
        cnt = Counter(g.votes.values())
        lines = "\n".join(f"Ответ {i + 1}: {cnt.get(t, 0)}" for i, t in enumerate(g.order))
        return (
            f"🗳 Идёт голосование\nПроголосовало: {len(g.votes)} (смотрели: {len(g.voters)})\n\n{lines}",
            _kb([_b("🏁 Завершить голосование", "sit_a_endvote")], *ex, stop),
        )
    return (
        "🏁 Игра завершена.\n\nЕщё раунд с теми же игроками — кнопка ниже, новая игра — /go.",
        _kb([_b("🔁 Ещё раунд (те же игроки)", "sit_a_again")], *ex),
    )


async def _refresh_panels(bot):
    g = G
    if not g:
        return
    text, kb = _panel(g)
    for uid, mid in list(g.panels.items()):
        await _edit(bot, uid, mid, text, kb)


async def _send_panel(bot, uid):
    g = G
    text, kb = _panel(g)
    m = await _send(bot, uid, text, kb)
    if m:
        g.panels[uid] = m.message_id


async def _send_sub(bot, chat_id, sub, header, kb=None):
    """Показать сданный ответ (текст или любое медиа). Никогда не бросает исключений."""
    if sub["kind"] == "text":
        return await _send(bot, chat_id, f"{header}\n\n{(sub.get('text') or '')[:MAX_SUB_TEXT]}", kb)
    if sub.get("cap_ok"):
        cap = header + (f"\n\n{sub['caption']}" if sub.get("caption") else "")
        m = await _copy(bot, chat_id, sub["chat_id"], sub["message_id"], caption=cap[:1024], kb=kb)
        if m:
            return m
    else:  # кружки, стикеры: подписи нет — шапка отдельным сообщением
        await _send(bot, chat_id, header)
        m = await _copy(bot, chat_id, sub["chat_id"], sub["message_id"], kb=kb)
        if m:
            return m
    return await _send(bot, chat_id, f"{header}\n\n⚠️ Не удалось показать ответ (сообщение удалено?).", kb)


# ------------------------------------------------------------------
# Команды админа: /go, /sgo
# ------------------------------------------------------------------
async def go_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global G
    uid = update.effective_user.id
    if uid not in ADMINS:
        await update.message.reply_text("❌ Эта команда только для админов!")
        return
    async with _lk("tr"):
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
    async with _lk("tr"):
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
        targets = [u for u in g.players if u not in g.gone]
        await _paced(targets, lambda u: _raw_send(bot, u, "⛔ Игра «Ситуации» остановлена админом."))


async def _raw_send(bot, uid, text):
    """Отправка без обращения к G (после остановки игры G уже None)."""
    try:
        await bot.send_message(uid, text)
    except RetryAfter as e:
        await asyncio.sleep(float(e.retry_after) + 0.5)
        try:
            await bot.send_message(uid, text)
        except TelegramError:
            pass
    except TelegramError:
        pass


# ------------------------------------------------------------------
# Банк ситуаций (GitHub): /sits, /addsit, /delsit
# ------------------------------------------------------------------
def _load_bank():
    global BANK
    if _storage is None:
        return
    try:
        data = _storage.load_file(BANK_FILE, None)
    except Exception:
        logger.exception("Не удалось загрузить банк ситуаций")
        return
    items = data.get("items") if isinstance(data, dict) else data
    if isinstance(items, list):
        clean = [str(x).strip()[:MAX_SUGGESTION_LEN] for x in items if str(x).strip()]
        if clean:
            BANK = clean


async def _save_bank():
    if _storage is None:
        logger.warning("Нет GitHub-хранилища — банк ситуаций сохранён только в памяти")
        return False
    try:
        await asyncio.to_thread(_storage.save_file, BANK_FILE, {"items": list(BANK)})
        return True
    except Exception:
        logger.exception("Не удалось сохранить банк ситуаций")
        return False


async def _add_to_bank(items):
    """Добавляет новые (без дублей). Возвращает сколько реально добавлено."""
    have = {x.lower() for x in BANK}
    added = 0
    for it in items:
        it = " ".join(it.split())[:MAX_SUGGESTION_LEN]
        if it and it.lower() not in have:
            BANK.append(it)
            have.add(it.lower())
            added += 1
    if added:
        await _save_bank()
    return added


async def sits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    lines = [f"{i + 1}. {s}" for i, s in enumerate(BANK)]
    head = f"📚 Банк ситуаций: {len(BANK)}\n/addsit <текст> (можно несколько строк) · /delsit <номера, диапазоны: 3 5-7>\n\n"
    text, parts = head, []
    for ln in lines:
        if len(text) + len(ln) + 1 > 3800:
            parts.append(text)
            text = ""
        text += ln + "\n"
    parts.append(text)
    for p in parts:
        await update.message.reply_text(p)


async def addsit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    raw = update.message.text.partition(" ")[2]
    items = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not items:
        await update.message.reply_text("Использование: /addsit <текст ситуации>\nМожно несколько — каждая с новой строки.")
        return
    n = await _add_to_bank(items)
    await update.message.reply_text(f"✅ Добавлено: {n} (дубли пропущены). Всего в банке: {len(BANK)}")


def _parse_numbers(args, maxn):
    out = set()
    for a in args:
        for part in a.replace(",", " ").split():
            if "-" in part:
                lo, _, hi = part.partition("-")
                if lo.isdigit() and hi.isdigit():
                    out.update(range(int(lo), int(hi) + 1))
            elif part.isdigit():
                out.add(int(part))
    return sorted(n for n in out if 1 <= n <= maxn)


async def delsit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    nums = _parse_numbers(context.args or [], len(BANK))
    if not nums:
        await update.message.reply_text("Использование: /delsit 3 5-7 (номера из /sits)")
        return
    if len(nums) >= len(BANK):
        await update.message.reply_text("⚠️ Нельзя удалить все ситуации — в банке должна остаться хотя бы одна.")
        return
    removed = [BANK[n - 1] for n in nums]
    for n in reversed(nums):
        BANK.pop(n - 1)
    await _save_bank()
    await update.message.reply_text("🗑 Удалено:\n" + "\n".join(f"• {_short(r, 80)}" for r in removed) + f"\n\nОсталось: {len(BANK)}")


# ------------------------------------------------------------------
# Комната (набор игроков)
# ------------------------------------------------------------------
async def _join(bot, uid, name):
    g = G
    g.players[uid] = name
    g.gone.discard(uid)
    _touch()
    old = g.lobby_msgs.get(uid)
    if old and await _edit(bot, uid, old, _lobby_text(g), _lobby_kb()):
        return
    m = await _send(bot, uid, _lobby_text(g), _lobby_kb())
    if m:
        g.lobby_msgs[uid] = m.message_id


async def _push_lobby(bot):
    g = G
    items = [(u, m) for u, m in list(g.lobby_msgs.items()) if u in g.players]
    text, kb = _lobby_text(g), _lobby_kb()

    async def one(it):
        await _edit(bot, it[0], it[1], text, kb)

    await _paced(items, one, per_batch=25)


async def _tick(context: ContextTypes.DEFAULT_TYPE):
    """Фоновый тик: живой счётчик комнаты, обновление панелей (раз в несколько секунд, без флуда)."""
    global _dirty_panels, _last_panel, _last_lobby
    try:
        g = G
        now = time.time()
        if g:
            if g.phase == "lobby" and len(g.players) != g.last_count and now - _last_lobby >= 5:
                g.last_count = len(g.players)
                _last_lobby = now
                _dirty_panels = True
                await _push_lobby(context.bot)
            if g.phase == "work" and now - _last_panel >= 30:
                _dirty_panels = True
            if _dirty_panels:
                _dirty_panels = False
                _last_panel = now
                await _refresh_panels(context.bot)
        if len(_hits) > 5000:
            for k in [k for k, dq in _hits.items() if not dq or time.monotonic() - dq[-1] > 60]:
                _hits.pop(k, None)
    except Exception:
        logger.exception("Ситуации: ошибка фонового тика")


async def _menu_entry(update, context):
    q = update.callback_query
    user = q.from_user
    bot = context.bot
    if q.message is None or q.message.chat.type != "private":
        await q.answer(f"Игра — в личке с ботом: @{context.bot.username}", show_alert=True)
        return
    await q.answer()
    if _flood(user.id, "menu", 5, 10):
        return
    g = G
    if g is None or g.phase == "finished":
        await _send(bot, user.id, "🎭 Сейчас игра «Ситуации» не идёт. Следи за анонсами 👀")
        return
    if g.phase == "lobby":
        await _join(bot, user.id, _name(user))
        return
    if g.phase == "voting":
        await _send(bot, user.id, _invite_text(g), _kb([_b("🗳 Смотреть ответы и голосовать", "sit_watch")]))
        return
    if user.id in g.user_team:
        await _send(bot, user.id, "🎭 Игра идёт, ты в команде. Загляни в сообщения выше 👆")
    elif user.id in g.reserve:
        await _send(bot, user.id, "🪑 Ты в запасе: если кому-то из команд понадобится замена — позовём!")
    elif g.phase in ("picking", "ready", "work"):
        await _send(bot, user.id, "🎭 Набор уже закрыт, но можно встать в запас — если кто-то выпадет, админ поставит тебя в команду.",
                    _kb([_b("🪑 Встать в запас", "sit_reserve")]))
    else:
        await _send(bot, user.id, "🎭 Команды уже работают. Скоро голосование — жми /vybor и выбирай лучших!")


# ------------------------------------------------------------------
# Раздача команд и выбор ситуации
# ------------------------------------------------------------------
async def _close_lobby(bot):
    g = G
    live = [u for u in g.players if u not in g.gone]
    if len(live) < 2:
        return "Нужно хотя бы 2 игрока"
    groups = make_teams(live, g.team_size)
    g.teams = {i + 1: {"members": m, "sub": None, "kept": None} for i, m in enumerate(groups)}
    g.rebuild()
    g.reserve.clear()
    g.in_chat.clear()
    g.admin_chat.clear()
    g.cards = {}
    g.extended = False
    g.stats_done = False
    g.votes.clear()
    g.voters.clear()
    g.order = []
    g.phase = "picking"
    kb = _kb([_b("🚪 Покинуть игру", "sit_quit")])
    await _send_many(
        bot, list(g.user_team),
        lambda u: f"👥 Команды сформированы!\n{_team_intro(g, g.user_team[u])}\n\nСейчас выбираем ситуацию…",
        kb,
    )
    await _start_picking(bot)
    return None


async def _start_picking(bot):
    g = G
    g.pending.clear()
    g.suggestions.clear()
    g.sit_votes.clear()
    g.sg_off.clear()
    g.sg_closed = False
    g.sg_pick = False
    g.voting_sit = False
    g.situation = None
    if g.sit_mode == "random":
        g.situation = random.choice(_bank())
        g.phase = "ready"
    elif g.sit_mode == "manual":
        g.sit_options = random.sample(_bank(), min(6, len(_bank())))
    elif g.sit_mode == "suggest":
        for uid in g.players:
            if uid in g.gone:
                continue
            g.pending[uid] = "suggest"
            _claim(uid)
        await _send_many(
            bot, list(g.players),
            f"💡 Пришли свою идею ситуации ОДНИМ текстовым сообщением (до {MAX_SUGGESTION_LEN} символов), "
            "например: «самый нелепый способ познакомиться».\nАдмин отберёт лучшие, и из них выберем ситуацию для всех.",
        )
    elif g.sit_mode == "vote":
        await _start_sit_vote(bot, random.sample(_bank(), min(5, len(_bank()))))
    await _refresh_panels(bot)


async def _start_sit_vote(bot, options):
    """Игроки голосуют за ситуацию (варианты — из банка или отобранные идеи)."""
    g = G
    g.sit_options = list(options)
    g.sit_votes.clear()
    g.voting_sit = True
    lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(g.sit_options))
    nums = [_b(str(i + 1), f"sit_ov_{i}") for i in range(len(g.sit_options))]
    kb = _kb(*[nums[i:i + 5] for i in range(0, len(nums), 5)])
    await _send_many(bot, list(g.players), f"🗳 Выбираем ситуацию! Голосуй (голос можно поменять):\n\n{lines}", kb)


def _finish_vote():
    g = G
    cnt = Counter(g.sit_votes.values())
    if cnt:
        top = max(cnt.values())
        i = random.choice([k for k, v in cnt.items() if v == top])
    else:
        i = random.randrange(len(g.sit_options))
    g.situation = g.sit_options[i]
    g.voting_sit = False
    g.phase = "ready"


def _finish_suggest_random():
    g = G
    g.situation = random.choice(_kept_ideas(g) or _bank())
    g.pending = {u: k for u, k in g.pending.items() if k != "suggest"}
    g.phase = "ready"


# ------------------------------------------------------------------
# Работа команд
# ------------------------------------------------------------------
def _schedule_work_jobs():
    g = G
    _cancel_jobs()
    jq = _app.job_queue if _app else None
    if not jq:
        logger.warning("JobQueue недоступен — таймер «Ситуаций» не сработает, завершай работу кнопкой")
        return
    left = g.work_ends - time.time()
    jq.run_once(_work_end_job, max(1, left), name="sit_work_end")
    if left > 65:
        jq.run_once(_work_warn_job, left - 60, name="sit_work_warn")


async def _begin_work(bot):
    g = G
    if not g.teams:
        return "Нет ни одной команды"
    g.phase = "work"
    g.extended = False
    g.work_ends = time.time() + g.work_minutes * 60
    _schedule_work_jobs()
    await _send_many(bot, list(g.user_team), lambda u: _work_text(g, g.teams[g.user_team[u]]), _work_kb())
    if g.reserve:
        await _send_many(bot, list(g.reserve), "🪑 Ты в запасе: если кому-то из команд понадобится замена — позовём!")
    await _refresh_panels(bot)
    return None


async def _work_warn_job(context: ContextTypes.DEFAULT_TYPE):
    g = G
    if g and g.phase == "work":
        pend = [u for u, tid in g.user_team.items() if not g.teams[tid]["sub"]]
        await _send_many(context.bot, pend, "⏰ Осталась 1 минута! Сдай ответ команды («Сдать ответ»).")


async def _work_end_job(context: ContextTypes.DEFAULT_TYPE):
    async with _lk("tr"):
        g = G
        if not g or g.phase != "work":
            return
        if time.time() < g.work_ends - 2:      # время успели продлить — это устаревший вызов
            return
        if await _maybe_extend(context.bot):
            return
        await _end_work(context.bot)


def _bonus_minutes(done, total):
    """Доп. время, если к концу таймера сдали ≤70% команд: 70% → 7 мин, 60% → 6 мин … (мин. 1)."""
    if not total:
        return 0
    pct = done * 100 // total
    if pct > 70:
        return 0
    return max(1, pct // 10)


async def _maybe_extend(bot):
    g = G
    total = len(g.teams)
    done = sum(1 for t in g.teams.values() if t["sub"])
    mins = _bonus_minutes(done, total)
    if g.extended or not mins:
        return False
    g.extended = True
    g.work_ends = time.time() + mins * 60
    _schedule_work_jobs()
    pct = done * 100 // total
    await _send_many(
        bot, list(g.user_team),
        f"⏳ К концу таймера сдали только {done} из {total} команд ({pct}%). "
        f"Всем добавляем {mins} мин! Успей сдать ответ.",
    )
    await _refresh_panels(bot)
    return True


async def _add_time(bot, minutes):
    g = G
    g.work_ends = max(g.work_ends, time.time()) + minutes * 60
    _schedule_work_jobs()
    await _send_many(bot, list(g.user_team), f"⏱ Админ добавил {minutes} мин.")


async def _maybe_all_done(bot):
    g = G
    if g and g.phase == "work" and g.teams and all(t["sub"] for t in g.teams.values()):
        _spawn(_auto_end(bot))


async def _auto_end(bot):
    async with _lk("tr"):
        g = G
        if g and g.phase == "work" and g.teams and all(t["sub"] for t in g.teams.values()):
            await _end_work(bot, all_done=True)


def _mod_kb(tid, kept, has_sub=True):
    rows = []
    if has_sub:
        rows.append([
            _b("✅ Оставить" + (" ✔" if kept is True else ""), f"sit_a_m_{tid}_1"),
            _b("❌ Убрать" + (" ✔" if kept is False else ""), f"sit_a_m_{tid}_0"),
        ])
    rows.append([_b("💬 Связь", f"sit_a_ln_{tid}"), _b("✏️ Править", f"sit_a_ed_{tid}")])
    return _kb(*rows)


async def _mod_card(bot, admin, tid):
    """Карточка ответа команды у админа (с кнопками модерации). Запоминаем id, чтобы обновлять кнопки."""
    g = G
    t = g.teams.get(tid)
    if not t:
        return
    head = f"Команда #{tid}: {_names(g, t['members'])}"
    if t["sub"]:
        m = await _send_sub(bot, admin, t["sub"], head + (" (правил админ)" if t["sub"].get("edited") else ""),
                            _mod_kb(tid, t["kept"], True))
    else:
        m = await _send(bot, admin, head + "\n\n😕 Ответ не сдан. Можно связаться с командой или написать ответ за них.",
                        _mod_kb(tid, None, False))
    if m:
        old = g.cards.get(f"{admin}:{tid}")
        g.cards[f"{admin}:{tid}"] = m.message_id
        if old:
            try:
                await bot.delete_message(admin, old)
            except TelegramError:
                pass


async def _update_cards(bot, tid):
    g = G
    t = g.teams.get(tid)
    if not t:
        return
    for key, mid in list(g.cards.items()):
        admin, _, ctid = key.partition(":")
        if int(ctid) != tid:
            continue
        try:
            await bot.edit_message_reply_markup(int(admin), mid, reply_markup=_mod_kb(tid, t["kept"], bool(t["sub"])))
        except BadRequest:
            pass
        except TelegramError:
            pass


async def _end_work(bot, all_done=False):
    g = G
    _cancel_jobs()
    g.phase = "moderation"
    g.pending.clear()      # сдача закрыта; чат команды (in_chat) остаётся открытым до голосования
    head = "🎉 Все команды сдали ответы!" if all_done else "⏹ Время вышло!"

    def text(u):
        t = g.teams.get(g.user_team.get(u))
        mine = "✅ Ответ твоей команды принят." if (t and t["sub"]) else "😕 Ответ твоей команды не сдан."
        return (
            f"{head}\n{mine}\n\n"
            "📨 Ответы отправлены админу — он проверит, чтобы там не было ерунды. Это займёт минут 3–5, "
            "потом начнётся голосование 🗳\n\n"
            "💬 Чат команды пока открыт. Нужно что-то исправить или объяснить? Жми «📞 Связь с админом» — "
            "админ зайдёт к вам в чат и поправит ответ."
        )

    await _send_many(bot, list(g.user_team), text, _mod_player_kb())
    for admin in list(g.panels):
        await _send(bot, admin, ("🎉 Все команды сдали ответы! " if all_done else "⏹ Время вышло. ") +
                    "Проверь ответы ниже: Оставить / Убрать / 💬 Связь / ✏️ Править.")
        for tid in sorted(g.teams):
            await _mod_card(bot, admin, tid)
            await asyncio.sleep(0.05)
    await _refresh_panels(bot)


# ------------------------------------------------------------------
# Связь админа с командами, правка ответа админом
# ------------------------------------------------------------------
def _admins_of(g, tid):
    return [a for a, t in g.admin_chat.items() if t == tid]


async def _link_admin(bot, admin, tid):
    g = G
    t = g.teams.get(tid)
    if not t:
        return "Команда не найдена"
    if g.phase not in ("work", "moderation"):
        return "Чаты команд сейчас закрыты"
    if not _claim(admin):
        return "Сначала закончи ответ на вопрос/рассылку"
    prev = g.admin_chat.get(admin)
    g.admin_chat[admin] = tid
    g.in_chat.update(t["members"])
    g.pending.pop(admin, None)
    if prev and prev != tid:
        await _notify_unlink(bot, prev, admin)
    await _send_many(bot, list(t["members"]), "👑 Админ зашёл в чат вашей команды. Пишите сюда — он всё видит.")
    await _send(bot, admin,
                f"💬 Ты в чате команды #{tid} ({_names(g, t['members'])}).\n"
                "Всё, что ты напишешь боту, увидит команда; их сообщения придут тебе сюда.",
                _kb([_b("🚪 Выйти из чата", "sit_a_lx")]))
    _touch()
    return None


async def _notify_unlink(bot, tid, admin):
    g = G
    t = g.teams.get(tid)
    if t and not _admins_of(g, tid):
        await _send_many(bot, list(t["members"]), "👑 Админ вышел из чата. Можете продолжать общаться между собой.")


async def _unlink_admin(bot, admin):
    g = G
    tid = g.admin_chat.pop(admin, None)
    if tid:
        await _notify_unlink(bot, tid, admin)
    _touch()
    return tid


async def _close_all_links(bot):
    """С началом голосования чаты команд (и с админом) закрываются."""
    g = G
    members = list(g.in_chat)
    linked = set(g.admin_chat.values())
    g.in_chat.clear()
    g.admin_chat.clear()
    for admin in list(g.pending):
        if str(g.pending.get(admin, "")).startswith("edit:"):
            g.pending.pop(admin, None)
    if members:
        await _send_many(bot, [u for u in members if u in g.user_team], "🔒 Чат команды закрыт — начинается голосование.")


async def _contact_admin(bot, uid):
    """Игрок просит админа зайти в чат его команды. Возвращает текст-ответ."""
    g = G
    tid = g.user_team.get(uid)
    if tid is None or g.phase not in ("work", "moderation"):
        return "Связь с админом сейчас недоступна"
    now = time.time()
    if now - g.last_req.get(tid, 0) < CONTACT_COOLDOWN:
        return "Запрос уже отправлен — админ скоро зайдёт 🙏"
    g.last_req[tid] = now
    _claim(uid)
    g.in_chat.add(uid)
    t = g.teams[tid]
    await _notify_admins(
        bot, f"📞 Команда #{tid} ({_names(g, t['members'])}) приглашает вас в чат.",
        _kb([_b(f"💬 Зайти в чат команды #{tid}", f"sit_a_ln_{tid}")]),
    )
    await _send(bot, uid, "📨 Запрос отправлен админу. Ты в чате команды — как только админ зайдёт, он напишет сюда.",
                _kb([_b("🚪 Выйти из чата", "sit_chat_off")]))
    return ""


def _validate(msg):
    """(info, текст_ошибки). info = (тип, можно_подпись, размер)."""
    info = _content_info(msg)
    if info is None:
        return None, "Этот тип сообщения не поддерживается. Пришли текст, фото, видео, гс, кружок, стикер или файл."
    if info[2] > MAX_MEDIA_BYTES:
        return None, f"Файл слишком большой (максимум {MAX_MEDIA_BYTES // (1024 * 1024)} МБ)."
    return info, None


def _make_sub(msg, info, by):
    kind, cap_ok, _ = info
    return {
        "kind": "text" if kind == "text" else "media",
        "text": (msg.text or "")[:MAX_SUB_TEXT] if kind == "text" else None,
        "caption": msg.caption, "cap_ok": cap_ok,
        "chat_id": msg.chat_id, "message_id": msg.message_id, "by": by,
    }


async def _relay_one(bot, to, msg, label, info):
    kind, cap_ok, _ = info
    if kind == "text":
        await _send(bot, to, f"{label}: {msg.text[:MAX_SUB_TEXT]}")
    elif cap_ok:
        cap = label + (f": {msg.caption}" if msg.caption else "")
        await _copy(bot, to, msg.chat_id, msg.message_id, caption=cap[:1024])
    else:
        await _send(bot, to, f"{label}:")
        await _copy(bot, to, msg.chat_id, msg.message_id)


# ------------------------------------------------------------------
# Выбывшие игроки, замены, перестановки
# ------------------------------------------------------------------
async def _remove_player(bot, uid, reason):
    g = G
    name = g.players.get(uid, str(uid))
    tid = g.user_team.get(uid)
    g.reserve.discard(uid)
    g.pending.pop(uid, None)
    g.in_chat.discard(uid)
    g.sit_votes.pop(uid, None)
    if g.phase in ("picking", "ready", "work"):
        g.players.pop(uid, None)
        if tid in g.teams:
            t = g.teams[tid]
            if uid in t["members"]:
                t["members"].remove(uid)
            mates = list(t["members"])
            if not mates:
                del g.teams[tid]
                for a in _admins_of(g, tid):
                    g.admin_chat.pop(a, None)
            g.rebuild()
            await _send_many(bot, mates, f"👋 {name} выбыл(а) из игры ({reason}).\n{_team_intro(g, tid)}" if mates else "")
            if not mates:
                await _notify_admins(bot, f"⚠️ Команда #{tid} распалась: {name} выбыл(а) ({reason}).")
            elif len(mates) == 1:
                kb = _kb([_b(f"🔁 Подставить из запаса в #{tid}", f"sit_a_fill_{tid}")]) if g.reserve else None
                await _notify_admins(bot, f"⚠️ В команде #{tid} остался 1 человек ({name} выбыл(а): {reason}).", kb)
            else:
                await _notify_admins(bot, f"👋 {name} выбыл(а) из команды #{tid} ({reason}).")
        else:
            await _notify_admins(bot, f"👋 {name} выбыл(а) из запаса/комнаты ({reason}).")
        if g.phase == "work":
            await _maybe_all_done(bot)
    else:
        await _notify_admins(bot, f"👋 {name} недоступен ({reason}). Его ответ остаётся в игре.")
    _touch()


async def _move_player(bot, uid, to_tid):
    """Переставить игрока в команду (to_tid>0) или в запас (0). Возвращает текст ошибки или None."""
    g = G
    if g.phase not in ("picking", "ready", "work"):
        return "Состав меняется только до конца работы команд"
    if uid not in g.players or uid in g.gone:
        return "Игрок недоступен"
    if to_tid and to_tid not in g.teams:
        return "Нет такой команды"
    old = g.user_team.get(uid)
    if (old or 0) == to_tid and (to_tid or uid in g.reserve):
        return "Он уже там"
    name = g.players[uid]
    mates_old = []
    if old:
        t = g.teams[old]
        t["members"].remove(uid)
        mates_old = list(t["members"])
        if not mates_old:
            del g.teams[old]
            for a in _admins_of(g, old):
                g.admin_chat.pop(a, None)
    g.in_chat.discard(uid)
    if g.pending.get(uid) == "submit":
        g.pending.pop(uid, None)
    g.reserve.discard(uid)
    if to_tid:
        g.teams[to_tid]["members"].append(uid)
    else:
        g.reserve.add(uid)
    g.rebuild()
    if mates_old:
        await _send_many(bot, mates_old, f"👋 {name} перешёл(ла) в другую команду.\n{_team_intro(g, old)}")
    if to_tid:
        t = g.teams[to_tid]
        others = [m for m in t["members"] if m != uid]
        await _send_many(bot, others, f"👋 К вам в команду пришёл(ла) {name}.\n{_team_intro(g, to_tid)}")
        if g.phase == "work":
            await _send(bot, uid, _work_text(g, t), _work_kb())
        else:
            await _send(bot, uid, f"👥 Админ поставил тебя в команду.\n{_team_intro(g, to_tid)}",
                        _kb([_b("🚪 Покинуть игру", "sit_quit")]))
    else:
        await _send(bot, uid, "🪑 Админ перевёл тебя в запас.")
    if g.phase == "work":
        await _maybe_all_done(bot)
    _touch()
    return None


async def _fill_team(bot, tid):
    g = G
    pool = [u for u in g.reserve if u not in g.gone]
    if not pool:
        return "В запасе никого нет"
    return await _move_player(bot, random.choice(pool), tid)


def _teams_view(g):
    can = g.phase in ("picking", "ready", "work")
    lines = [f"👥 Составы команд (раунд {g.round})\n"]
    for tid in sorted(g.teams):
        t = g.teams[tid]
        mark = "✅" if t["sub"] else "▫️"
        lines.append(f"#{tid} {mark} {_names(g, t['members'])}")
    if g.reserve:
        lines.append("\n🪑 Запас: " + _names(g, sorted(g.reserve)))
    if not g.teams:
        lines.append("Команд пока нет.")
    rows = []
    if can:
        lines.append("\nНажми на игрока, чтобы переставить:")
        btns = [_b("↔️ " + _short(g.players.get(u, str(u)), 12), f"sit_a_mv_{u}")
                for u in list(g.user_team) + sorted(g.reserve)]
        rows += [btns[i:i + 2] for i in range(0, len(btns), 2)]
        if g.reserve:
            for tid in sorted(g.teams):
                if len(g.teams[tid]["members"]) < g.team_size:
                    rows.append([_b(f"🔁 Из запаса в #{tid}", f"sit_a_fill_{tid}")])
    rows.append([_b("🔄 Обновить", "sit_a_tv"), _b("✖️ Закрыть", "sit_a_cl")])
    return "\n".join(lines), _kb(*rows)


# ------------------------------------------------------------------
# Обработка сообщений игроков и админа
# ------------------------------------------------------------------
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единая точка: чат команды, сдача ответа, идеи, ручная ситуация, чат админа, правка ответа."""
    msg = update.effective_message
    uid = update.effective_user.id
    kind = _active_kind(uid)
    g = G
    if g is None or kind is None or msg is None:
        return
    bot = context.bot

    if kind == "hint":
        if not _flood(uid, "hint", 1, 20):
            await msg.reply_text("💬 Чтобы твои сообщения дошли напарникам, нажми «Войти в чат команды» 👇", reply_markup=_work_kb())
        return

    if kind == "manual":
        if not msg.text:
            await msg.reply_text("Нужен текст ситуации.")
            return
        g.pending.pop(uid, None)
        g.situation = " ".join(msg.text.split())[:MAX_SUGGESTION_LEN]
        g.phase = "ready"
        await _refresh_panels(bot)
        return

    if kind == "suggest":
        if not msg.text:
            await msg.reply_text("Пришли идею текстом 🙂")
            return
        g.suggestions[uid] = " ".join(msg.text.split())[:MAX_SUGGESTION_LEN]
        g.pending.pop(uid, None)
        await msg.reply_text("✅ Идея принята! Ждём остальных.")
        _touch()
        return

    if kind == "edit":
        tid = int(g.pending[uid].split(":")[1])
        t = g.teams.get(tid)
        info, err = _validate(msg)
        if err:
            await msg.reply_text(err)
            return
        if not t:
            g.pending.pop(uid, None)
            return
        g.pending.pop(uid, None)
        t["sub"] = _make_sub(msg, info, "👑 админ")
        t["sub"]["edited"] = True
        await msg.reply_text(f"✅ Ответ команды #{tid} обновлён.")
        for a in list(g.panels):
            await _mod_card(bot, a, tid)
        await _send_many(bot, list(t["members"]), "✏️ Админ обновил ваш ответ. Теперь он такой:")
        for m in t["members"]:
            await _send_sub(bot, m, t["sub"], f"Ответ команды #{tid}")
        _touch()
        return

    info, err = _validate(msg)

    if kind == "achat":
        if err:
            await msg.reply_text(err)
            return
        tid = g.admin_chat.get(uid)
        t = g.teams.get(tid)
        if not t:
            return
        await asyncio.gather(*(_relay_one(bot, m, msg, "👑 Админ", info) for m in t["members"]))
        return

    tid = g.user_team.get(uid)
    if tid is None:
        return
    team = g.teams[tid]
    name = g.players.get(uid, str(uid))

    if kind == "submit":
        if err:
            await msg.reply_text(err)
            return
        g.pending.pop(uid, None)
        sub = _make_sub(msg, info, name)
        team["sub"] = sub
        team["kept"] = None
        await msg.reply_text("✅ Ответ сдан! Можно пересдать кнопкой «Сдать ответ», пока идёт время.")
        await _send_many(bot, [m for m in team["members"] if m != uid], f"✅ {name} сдал(а) ответ команды.")
        _touch()
        await _maybe_all_done(bot)
        return

    # kind == "chat": пересылаем напарникам и админам, зашедшим в чат команды
    if _flood(uid, "chat", *CHAT_FLOOD):
        if not _flood(uid, "chatwarn", 1, 10):
            await msg.reply_text("🐢 Не так быстро — сообщения летят слишком часто.")
        return
    if err:
        await msg.reply_text(err)
        return
    targets = [(m, f"👤 {name}") for m in team["members"] if m != uid]
    targets += [(a, f"#{tid} {name}") for a in _admins_of(g, tid)]
    await asyncio.gather(*(_relay_one(bot, to, msg, label, info) for to, label in targets))


# ------------------------------------------------------------------
# Голосование за ответы
# ------------------------------------------------------------------
def _invite_text(g):
    return (
        "🗳 ГОЛОСОВАНИЕ — «Ситуации»\n\n"
        f"📌 Тема: «{g.situation}»\n"
        f"Ответов: {len(g.order)}\n\n"
        "Как голосовать:\n"
        "• листай ответы кнопками ◀️ ▶️\n"
        "• понравился — жми «🗳 Голосовать за этот ответ»\n"
        "• голос можно поменять, пока голосование открыто\n"
        "• за свою команду голосовать нельзя 🙂\n\n"
        "Авторов покажем после итогов 🎭"
    )


def _viewer_kb(g, uid, idx):
    n = len(g.order)
    tid = g.order[idx]
    mine = g.votes.get(uid) == tid
    return _kb(
        [_b("◀️", f"sit_v_{(idx - 1) % n}"), _b(f"{idx + 1}/{n}", "sit_noop"), _b("▶️", f"sit_v_{(idx + 1) % n}")],
        [_b("✅ Твой голос здесь" if mine else "🗳 Голосовать за этот ответ", f"sit_vote_{tid}")],
    )


async def _show_answer(bot, uid, idx, old_msg=None):
    """Показать ответ №idx. Текст → правим сообщение на месте, медиа → удаляем старое и шлём новое."""
    g = G
    sub = g.teams[g.order[idx]]["sub"]
    kb = _viewer_kb(g, uid, idx)
    if old_msg is not None and sub["kind"] == "text" and old_msg.text:
        if await _edit(bot, uid, old_msg.message_id,
                       f"Ответ №{idx + 1}\n\n{(sub.get('text') or '')[:MAX_SUB_TEXT]}", kb):
            return
    if old_msg is not None:
        try:
            await old_msg.delete()
        except TelegramError:
            pass
    await _send_sub(bot, uid, sub, f"Ответ №{idx + 1}", kb)


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
    await _close_all_links(bot)
    await _send_many(bot, list(g.players), _invite_text(g), _kb([_b("🗳 Смотреть ответы и голосовать", "sit_watch")]))
    await _refresh_panels(bot)


async def _record_stats(g):
    """Участие/победы → общая статистика бота (один коммит на всех)."""
    if g.stats_done or _stat_hook is None:
        g.stats_done = True
        return
    g.stats_done = True
    cnt = Counter(g.votes.values())
    top = max(cnt.values()) if cnt else 0
    upd = {}
    for tid, t in g.teams.items():
        if not t["sub"]:
            continue
        for u in t["members"]:
            d = upd.setdefault(u, {"sit_played": 0, "sit_wins": 0})
            d["sit_played"] += 1
            if top > 0 and tid in g.order and cnt.get(tid, 0) == top:
                d["sit_wins"] += 1
    if not upd:
        return
    try:
        await asyncio.to_thread(_stat_hook, upd)
    except Exception:
        logger.exception("Ситуации: не удалось записать статистику")


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
        lines.append(f"{mark} {_names(g, g.teams[t]['members'])} — голосов: {cnt.get(t, 0)}")
    text = f"🏁 Итоги «Ситуаций»\nТема: «{g.situation}»\n\n" + "\n".join(lines)
    text += "\n\n🎭 Авторы раскрыты!" if top else "\n\nГолосов не было 🤷"
    recipients = [u for u in (set(g.players) | g.voters | set(g.panels)) if u not in g.gone]

    async def one(u):
        await _send(bot, u, text)
        if top > 0:
            for t in winners:
                await _send_sub(bot, u, g.teams[t]["sub"], f"🏆 Победитель: {_names(g, g.teams[t]['members'])}")

    await _paced(recipients, one, per_batch=10)
    await _record_stats(g)
    await _refresh_panels(bot)


# ------------------------------------------------------------------
# Рассылка «Оповестить всех» (в фоне, пачками — бот не подвисает)
# ------------------------------------------------------------------
async def _notify_all(bot, admin, g):
    sent = failed = 0
    try:
        users = [u for u in list(_get_all_users()) if u not in g.players and u not in g.gone]
        kb = _kb([_b("🎭 Войти в комнату", "sit_menu")])
        text = "🎭 Начинается игра «Ситуации»! Заходи в комнату 👇"

        async def one(u):
            nonlocal sent, failed
            for _ in range(2):
                try:
                    await bot.send_message(u, text, reply_markup=kb)
                    sent += 1
                    return
                except RetryAfter as e:
                    await asyncio.sleep(float(e.retry_after) + 0.5)
                except TelegramError:
                    failed += 1
                    return
            failed += 1

        await _paced(users, one, per_batch=20)
    except Exception:
        logger.exception("Ситуации: ошибка рассылки приглашений")
    await _raw_send(bot, admin, f"📢 Оповещение завершено: доставлено {sent}, не доставлено {failed} (заблокировали бота и т.п.).")


# ------------------------------------------------------------------
# Кнопки админа
# ------------------------------------------------------------------
async def _admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global G
    q = update.callback_query
    uid = q.from_user.id
    bot = context.bot
    a = q.data[len("sit_a_"):]

    async def ans(text=None, alert=False):
        try:
            await q.answer(text, show_alert=alert)
        except TelegramError:
            pass

    if uid not in ADMINS:
        await ans("Только для админа", True)
        return

    async with _lk("tr"):
        g = G
        if g is None:
            await ans("Игра не запущена. /go — запустить", True)
            return

        # ---------- общие ----------
        if a == "stop":
            await ans("Игра остановлена")
            await _stop_game(bot)
            try:
                await q.message.edit_text("⛔ Игра «Ситуации» остановлена. /go — новая игра.")
            except TelegramError:
                pass
            return
        if a == "teams":
            await ans()
            text, kb = _teams_view(g)
            await _send(bot, uid, text, kb)
            return
        if a == "tv":
            await ans()
            text, kb = _teams_view(g)
            await _edit(bot, uid, q.message.message_id, text, kb)
            return
        if a == "cl":
            await ans()
            try:
                await q.message.delete()
            except TelegramError:
                pass
            return
        if a.startswith("mv_"):
            u = int(a[3:])
            if g.phase not in ("picking", "ready", "work") or u not in g.players:
                await ans("Сейчас нельзя переставлять", True)
                return
            await ans()
            rows = [[_b(f"→ #{tid}", f"sit_a_mt_{u}_{tid}") for tid in sorted(g.teams)][i:i + 4]
                    for i in range(0, len(g.teams), 4)]
            rows.append([_b("🪑 В запас", f"sit_a_mt_{u}_0"), _b("↩️ Назад", "sit_a_tv")])
            await _edit(bot, uid, q.message.message_id, f"Куда переместить: {g.players.get(u, u)}?", _kb(*rows))
            return
        if a.startswith("mt_"):
            _, u, tid = a.split("_")
            err = await _move_player(bot, int(u), int(tid))
            await ans(err or "✅ Готово", bool(err))
            text, kb = _teams_view(g)
            await _edit(bot, uid, q.message.message_id, text, kb)
            await _refresh_panels(bot)
            return
        if a.startswith("fill_"):
            err = await _fill_team(bot, int(a[5:]))
            await ans(err or "✅ Игрок из запаса добавлен", bool(err))
            if q.message and q.message.text and q.message.text.startswith("👥 Составы"):
                text, kb = _teams_view(g)
                await _edit(bot, uid, q.message.message_id, text, kb)
            await _refresh_panels(bot)
            return
        if a == "sgbank":
            n = await _add_to_bank(_kept_ideas(g))
            await ans(f"💾 В банк добавлено: {n}. Всего: {len(BANK)}", True)
            return

        # ---------- лобби ----------
        if a.startswith(("size_", "mode_", "time_")) and g.phase == "lobby":
            kind, val = a.split("_", 1)
            if kind == "size":
                g.team_size = int(val)
            elif kind == "mode":
                g.sit_mode = val
            else:
                g.work_minutes = int(val)
            await ans()
        elif a == "notify" and g.phase == "lobby":
            wait = NOTIFY_COOLDOWN - (time.time() - g.last_notify)
            if wait > 0:
                await ans(f"Уже отправлено. Повтор через {int(wait)} сек", True)
                return
            g.last_notify = time.time()
            await ans("📢 Рассылка пошла в фоне — пришлю отчёт, когда закончится")
            _spawn(_notify_all(bot, uid, g))
            return
        elif a == "close" and g.phase == "lobby":
            if len([u for u in g.players if u not in g.gone]) < 2:
                await ans("Нужно хотя бы 2 игрока", True)
                return
            await ans("Раздаю команды…")
            err = await _close_lobby(bot)
            if err:
                await _send(bot, uid, "⚠️ " + err)
            return

        # ---------- выбор ситуации ----------
        elif a.startswith("pick_") and g.phase == "picking" and g.sit_mode == "manual":
            i = int(a[5:])
            if 0 <= i < len(g.sit_options):
                g.situation = g.sit_options[i]
                g.phase = "ready"
            await ans()
        elif a == "own" and g.phase == "picking" and g.sit_mode == "manual":
            if not _claim(uid):
                await ans("Сначала закончи ответ на вопрос/рассылку", True)
                return
            g.pending[uid] = "manual"
            await ans()
            await _send(bot, uid, f"✍️ Напиши текст ситуации одним сообщением (до {MAX_SUGGESTION_LEN} символов).")
        elif a == "reroll" and g.phase in ("picking", "ready"):
            await ans()
            if g.sit_mode == "manual":
                g.phase = "picking"
                g.sit_options = random.sample(_bank(), min(6, len(_bank())))
            elif g.sit_mode == "vote":
                g.phase = "picking"
                await _start_sit_vote(bot, random.sample(_bank(), min(5, len(_bank()))))
            elif g.sit_mode == "suggest":
                g.situation = random.choice(_kept_ideas(g) or _bank())
                g.phase = "ready"
            else:
                g.situation = random.choice(_bank())
                g.phase = "ready"
        elif a == "endsugg" and g.phase == "picking" and g.sit_mode == "suggest" and not g.sg_closed:
            g.sg_closed = True
            g.pending = {u: k for u, k in g.pending.items() if k != "suggest"}
            await ans("Сбор закрыт — отбери идеи")
            await _send_many(bot, list(g.players), "💡 Сбор идей закрыт. Админ выбирает ситуацию…")
        elif a.startswith("sgx_") and g.phase == "picking" and g.sg_closed:
            ideas = _ideas(g)
            i = int(a[4:])
            if 0 <= i < len(ideas):
                u = ideas[i][0]
                g.sg_off.symmetric_difference_update({u})
            await ans()
        elif a == "sgmanual" and g.phase == "picking" and g.sg_closed:
            g.sg_pick = not g.sg_pick
            await ans()
        elif a.startswith("sgp_") and g.phase == "picking" and g.sg_closed:
            ideas = _ideas(g)
            i = int(a[4:])
            if 0 <= i < len(ideas) and ideas[i][2]:
                g.situation = ideas[i][1]
                g.sg_pick = False
                g.phase = "ready"
            await ans()
        elif a == "sgrand" and g.phase == "picking" and g.sg_closed and not g.voting_sit:
            _finish_suggest_random()
            await ans()
        elif a == "sgvote" and g.phase == "picking" and g.sg_closed and not g.voting_sit:
            kept = _kept_ideas(g)
            if len(kept) < 2:
                await ans("Для голосования нужно минимум 2 идеи", True)
                return
            await ans("Голосование запущено")
            await _start_sit_vote(bot, random.sample(kept, min(VOTE_OPTIONS_MAX, len(kept))))
        elif a == "endsvote" and g.phase == "picking" and g.voting_sit:
            _finish_vote()
            await ans()

        # ---------- работа команд ----------
        elif a == "begin" and g.phase == "ready":
            await ans("Работа началась")
            err = await _begin_work(bot)
            if err:
                await _send(bot, uid, "⚠️ " + err)
            return
        elif a == "plus" and g.phase == "work":
            await ans("+2 минуты")
            await _add_time(bot, 2)
        elif a == "endwork" and g.phase == "work":
            await ans()
            await _end_work(bot)
            return

        # ---------- модерация ----------
        elif a.startswith("m_") and g.phase == "moderation":
            _, tid, flag = a.split("_")
            t = g.teams.get(int(tid))
            if t and t["sub"]:
                t["kept"] = flag == "1"
                await _update_cards(bot, int(tid))
            await ans()
        elif a == "keepall" and g.phase == "moderation":
            for tid, t in g.teams.items():
                if t["sub"]:
                    t["kept"] = True
                    await _update_cards(bot, tid)
            await ans("Все сданные оставлены")
        elif a == "startvote" and g.phase == "moderation":
            kept = [t for t in g.teams.values() if t["sub"] and t["kept"] is True]
            if not kept:
                await ans("Оставь хотя бы 1 ответ", True)
                return
            await ans("Голосование запущено")
            await _start_voting(bot)
            return
        elif a.startswith("ln_") and g.phase in ("work", "moderation"):
            err = await _link_admin(bot, uid, int(a[3:]))
            await ans(err or "💬 Ты в чате команды", bool(err))
        elif a == "lx":
            tid = await _unlink_admin(bot, uid)
            await ans("Ты вышел из чата" if tid else "Ты ни с кем не в чате")
            if q.message:
                try:
                    await q.message.edit_text("🚪 Ты вышел из чата команды.")
                except TelegramError:
                    pass
        elif a.startswith("ed_") and g.phase == "moderation":
            tid = int(a[3:])
            if tid not in g.teams:
                await ans("Команда не найдена", True)
                return
            if not _claim(uid):
                await ans("Сначала закончи ответ на вопрос/рассылку", True)
                return
            g.pending[uid] = f"edit:{tid}"
            await ans()
            await _send(bot, uid,
                        f"✏️ Пришли новый ответ для команды #{tid} одним сообщением (текст, фото, видео, гс, кружок). "
                        "Он заменит текущий, команде придёт уведомление.",
                        _kb([_b("↩️ Отмена", "sit_a_edc")]))
            return
        elif a == "edc":
            if str(g.pending.get(uid, "")).startswith("edit:"):
                g.pending.pop(uid, None)
            await ans("Отменено")
            return

        # ---------- голосование / итоги ----------
        elif a == "endvote" and g.phase == "voting":
            await ans()
            await _finish_voting(bot)
            return
        elif a == "again" and g.phase == "finished":
            await ans("Новый раунд…")
            new = Game()
            new.team_size, new.sit_mode, new.work_minutes = g.team_size, g.sit_mode, g.work_minutes
            new.round = g.round + 1
            new.players = {u: n for u, n in g.players.items() if u not in g.gone}
            new.gone = set(g.gone)
            new.panels = dict(g.panels)
            G = new
            err = await _close_lobby(bot)
            if err:
                await _send(bot, uid, "⚠️ " + err)
                await _refresh_panels(bot)
            return
        else:
            await ans("Сейчас это недоступно")
            return

        await _refresh_panels(bot)


# ------------------------------------------------------------------
# Кнопки игроков
# ------------------------------------------------------------------
async def _player_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    bot = context.bot
    g = G

    async def ans(text=None, alert=False):
        try:
            await q.answer(text, show_alert=alert)
        except TelegramError:
            pass

    if g is None:
        await ans("Игра уже закончилась", True)
        return

    if data == "sit_leave":
        if g.phase == "lobby":
            g.players.pop(uid, None)
            g.lobby_msgs.pop(uid, None)
            _touch()
            await ans("Ты вышел из комнаты")
            try:
                await q.message.edit_text("🚪 Ты вышел из комнаты. Вернуться можно через меню бота.")
            except TelegramError:
                pass
        else:
            await ans("Набор уже закрыт", True)
        return

    if data == "sit_reserve":
        if g.phase in ("picking", "ready", "work") and uid not in g.players:
            g.players[uid] = _name(q.from_user)
            g.gone.discard(uid)
            g.reserve.add(uid)
            _touch()
            await ans("🪑 Ты в запасе")
            await _notify_admins(bot, f"🪑 {g.players[uid]} встал(а) в запас (всего: {len(g.reserve)}).")
        else:
            await ans("Сейчас в запас встать нельзя", True)
        return

    if data == "sit_quit":
        if g.phase in ("picking", "ready", "work") and uid in g.players:
            await ans("Ты вышел из игры")
            await _remove_player(bot, uid, "вышел(а) сам(а)")
            await _send(bot, uid, "🚪 Ты вышел из игры. Голосовать за ответы всё равно можно — /vybor, когда начнётся.")
        else:
            await ans("Выйти уже нельзя", True)
        return

    if data.startswith("sit_ov_"):
        if g.phase == "picking" and g.voting_sit and uid in g.players:
            i = int(data[7:])
            if 0 <= i < len(g.sit_options):
                g.sit_votes[uid] = i
                _touch()
                await ans(f"Голос за вариант {i + 1} принят")
                return
        await ans("Голосование за ситуацию сейчас недоступно", True)
        return

    if data == "sit_chat_on":
        if g.phase not in ("work", "moderation") or uid not in g.user_team:
            await ans("Чат сейчас недоступен", True)
            return
        if not _claim(uid):
            await ans("Сначала закончи другое действие в боте", True)
            return
        g.in_chat.add(uid)
        await ans()
        await _send(bot, uid, "💬 Ты в чате команды. Пиши, отправляй фото, видео, гс — всё придёт напарникам"
                    + (" и админу." if _admins_of(g, g.user_team[uid]) else "."),
                    _kb([_b("🚪 Выйти из чата", "sit_chat_off")]))
        mates = [m for m in g.teams[g.user_team[uid]]["members"] if m != uid]
        await _send_many(bot, mates, f"💬 {g.players.get(uid)} зашёл(ла) в чат команды.")
        return

    if data == "sit_chat_off":
        g.in_chat.discard(uid)
        await ans("Ты вышел из чата")
        return

    if data == "sit_contact":
        if g.phase not in ("work", "moderation") or uid not in g.user_team:
            await ans("Связь с админом сейчас недоступна", True)
            return
        await ans()
        note = await _contact_admin(bot, uid)
        if note:
            await _send(bot, uid, note)
        return

    if data == "sit_submit":
        if g.phase != "work" or uid not in g.user_team:
            await ans("Сдача ответов закрыта. Нужно поправить — «Связь с админом»", True)
            return
        if not _claim(uid):
            await ans("Сначала закончи другое действие в боте", True)
            return
        g.pending[uid] = "submit"
        await ans()
        had = g.teams[g.user_team[uid]]["sub"]
        await _send(bot, uid,
                    "📨 Отправь итог ОДНИМ сообщением: текст, фото, видео, гс или кружок."
                    + ("\n⚠️ Прежний ответ команды будет заменён." if had else ""),
                    _kb([_b("↩️ Отмена", "sit_submit_cancel")]))
        return

    if data == "sit_submit_cancel":
        if g.pending.get(uid) == "submit":
            g.pending.pop(uid, None)
        await ans("Отменено")
        return

    if data == "sit_watch":
        if g.phase != "voting" or not g.order:
            await ans("Голосование не идёт", True)
            return
        if _flood(uid, "cb", *CB_FLOOD):
            await ans("Не так быстро 🙂")
            return
        g.voters.add(uid)
        await ans()
        await _show_answer(bot, uid, 0)
        return

    if data.startswith("sit_v_"):
        if g.phase != "voting" or not g.order:
            await ans("Голосование уже закончилось", True)
            return
        if _flood(uid, "cb", *CB_FLOOD):
            await ans("Не так быстро 🙂")
            return
        idx = int(data[6:]) % len(g.order)
        await ans()
        await _show_answer(bot, uid, idx, old_msg=q.message)
        return

    if data.startswith("sit_vote_"):
        if g.phase != "voting":
            await ans("Голосование уже закончилось", True)
            return
        tid = int(data[9:])
        if tid not in g.order:
            await ans()
            return
        if uid in g.teams[tid]["members"]:
            await ans("За свою команду голосовать нельзя 🙂", True)
            return
        g.votes[uid] = tid
        g.voters.add(uid)
        await ans("✅ Голос засчитан")
        try:
            await q.message.edit_reply_markup(_viewer_kb(g, uid, g.order.index(tid)))
        except TelegramError:
            pass
        _touch()
        return

    await ans()


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    try:
        if data == "sit_noop":
            await q.answer()
        elif data == "sit_menu":
            await _menu_entry(update, context)
        elif data.startswith("sit_a_"):
            await _admin_cb(update, context)
        else:
            await _player_cb(update, context)
    except Exception:
        logger.exception("Ситуации: ошибка в обработчике кнопки %s", data)
        try:
            await q.answer("Что-то пошло не так, попробуй ещё раз", show_alert=True)
        except TelegramError:
            pass


# ------------------------------------------------------------------
# Подключение
# ------------------------------------------------------------------
def register(app, admin_ids, get_all_users=None, *, storage=None, stat_hook=None, claim=None, busy=None):
    """Вызвать в main() ДО регистрации общих MessageHandler (receive_message).

    storage   — GitHubStorage (для банка ситуаций), stat_hook — функция записи побед/участия в статистику,
    claim(uid) — забрать пользователя у других режимов бота (False — нельзя),
    busy(uid)  — True, если пользователь сейчас в другом режиме бота (игра уступает).
    """
    global ADMINS, _get_all_users, _app, _storage, _stat_hook, _claim, _busy
    ADMINS = set(int(a) for a in admin_ids)
    if get_all_users:
        _get_all_users = get_all_users
    _app, _storage, _stat_hook = app, storage, stat_hook
    if claim:
        _claim = claim
    if busy:
        _busy = busy
    _load_bank()
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("go", go_command, filters=private))
    app.add_handler(CommandHandler("sgo", sgo_command, filters=private))
    app.add_handler(CommandHandler("sits", sits_command, filters=private))
    app.add_handler(CommandHandler("addsit", addsit_command, filters=private))
    app.add_handler(CommandHandler("delsit", delsit_command, filters=private))
    app.add_handler(CommandHandler("vybor", vybor_command))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^sit_"))
    app.add_handler(MessageHandler(private & filters.UpdateType.MESSAGE & ~filters.COMMAND & _SitActive(), on_message))
    if app.job_queue:
        app.job_queue.run_repeating(_tick, interval=TICK_EVERY, first=TICK_EVERY)
    else:
        logger.warning("JobQueue недоступен — таймеры игры «Ситуации» работать не будут")
