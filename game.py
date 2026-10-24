"""Логика игры «Карточки» (вкладка «Игра» в мини-аппе).

Все данные игрока лежат внутри его записи user_stats[<id>]["game"], поэтому
отдельного хранилища не нужно: они сохраняются на GitHub тем же save_user_stats(),
что и остальная статистика. Всё решается на сервере (случайность, списание звёзд,
дуэли), поэтому накрутить через консоль браузера нельзя.
"""
import random
import time
import uuid

try:
    from promos import PROMOS
except Exception:   # файла нет или он сломан — игра работает без промокодов
    PROMOS = {}

# ---------- карточки ----------
# ЕДИНЫЙ каталог: здесь id, название, редкость и описание. Фронт получает его с сервера,
# так что добавить/переименовать карточку можно только в этом месте.
# Картинка карточки: miniapp/static/cards/<id>.jpg (если файла нет — рисуется цветной градиент
# редкости, поэтому игра работает и без фото). У первых 8 карточек есть старые фото как запасной вариант.
# Состав: 10 common · 8 uncommon · 6 rare · 4 epic · 2 legendary = 30 (под него посчитан прайс).
# Новые карточки «Рома»: фото лежат в miniapp/static/ как role_<имя>.jpg (см. ROLE_PHOTOS ниже);
# у Голодного/Сонного/Доброго/Злого Ромы и Босса фото пока нет — рисуется градиент редкости.
# Названия остальных карточек — заглушки, переименуй под свой контент.
_C = [
    # id,          название,          редкость,     описание,                               старое фото
    ("viewer",    "Зритель",         "common",    "Верный зритель. Всегда в чате.",        "photo_2026-09-18_20-27-30.jpg"),
    ("chatter",   "Чатер",           "common",    "Активный участник чата.",               "photo_2026-09-18_20-27-23.jpg"),
    ("hungry",    "Голодный Рома",   "common",    "Стрим идёт, а холодильник пуст.",       None),
    ("newbie",    "Новичок",         "common",    "Только зашёл и уже в теме.",            None),
    ("spammer",   "Спамер смайлов",  "common",    "Чат без него — не чат.",                None),
    ("night",     "Ночной зритель",  "common",    "Не спит ради стрима.",                  None),
    ("memer",     "Мемолог",         "common",    "Знает мем на любой случай.",            None),
    ("clipper",   "Клипмейкер",      "common",    "Нарезает лучшие моменты.",              None),
    ("fan",       "Фанат",           "common",    "Смотрит с самого начала.",              None),
    ("skeptic",   "Скептик",         "common",    "«Да ладно, не может быть».",            None),

    ("supporter", "Саппортер",       "uncommon",  "Поддерживает донатами.",                "photo_2026-09-18_20-27-26.jpg"),
    ("ideator",   "Идеатор",         "uncommon",  "Генерирует идеи для стрима.",           "photo_2026-09-18_20-27-30.jpg"),
    ("sleepy",    "Сонный Рома",     "uncommon",  "Третья ночь без сна. Но стрим идёт.",   None),
    ("happy",     "Радостный Рома",  "uncommon",  "Улыбка до ушей. Заряжает весь чат.",    None),
    ("tiktoker",  "Тиктокер",        "uncommon",  "Лайкает и репостит каждое видео.",      None),
    ("sub",       "Подписчик",       "uncommon",  "Подписан на всё, что есть.",            None),
    ("regular",   "Завсегдатай",     "uncommon",  "Его ник знает весь чат.",               None),
    ("editor",    "Монтажёр",        "uncommon",  "Собирает ролики по ночам.",             None),

    ("streamer",  "Стример",         "rare",      "Сам умеет стримить. Редкость.",         "photo_2026-09-18_20-27-23.jpg"),
    ("mod",       "Модератор",       "rare",      "Держит порядок в чате.",                "photo_2026-09-18_20-27-26.jpg"),
    ("kind",      "Добрый Рома",     "rare",      "Раздаёт плюсы в карму и подарки.",      None),
    ("sly",       "Хитрый Рома",     "rare",      "Что-то задумал. Лучше не отвлекать.",   None),
    ("melon",     "Арбузик",         "rare",      "Выбирает арбуз как никто другой.",      None),
    ("alons",     "Алонс (ИИ)",      "rare",      "Помощник бота. Знает почти всё про Рому.", None),

    ("legend",    "Легенда",         "epic",      "Был с первого стрима.",                 "photo_2026-09-18_20-27-30.jpg"),
    ("evil",      "Злой Рома",       "epic",      "Лучше не донатить на мут.",             None),
    ("glam",      "Гламурный Рома",  "epic",      "Розовый салон, белый лук, чистый шик.", None),
    ("og",        "Старожил",        "epic",      "Помнит времена до первой тысячи.",      None),

    ("alonso",    "Алонсо",          "legendary", "Сам Алонсо. Мегаредкая.",               "photo_2026-09-18_20-27-23.jpg"),
    ("boss",      "Рома-Босс",       "legendary", "Финальный босс чата. Мегаредкая.",      None),
]
CARDS = {c[0]: c[2] for c in _C}
NAMES = {c[0]: c[1] for c in _C}
import os as _os
_CARDS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "miniapp", "static", "cards")

# Фото новых карточек лежат рядом с index.html. Для «Хитрого Ромы» поддержаны оба названия
# файла (role_sly.jpg и role_shy.jpg) — какой из них есть в папке, тот и покажется.
ROLE_PHOTOS = {
    "sly":   ["role_sly.jpg", "role_shy.jpg"],
    "glam":  ["role_glam.jpg"],
    "happy": ["role_happy.jpg"],
    "melon": ["role_melon.jpg"],
}

# Пронумерованные фото карточек лежат рядом с index.html: 4.jpg … 25.jpg.
# Расширение и регистр (.jpg / .JPG / .JPEG и т.д.) подбираются автоматически — на сервере Linux
# «4.JPG» и «4.jpg» разные файлы, поэтому имя берётся из того, что реально лежит в папке.
# Тут надо ТОЛЬКО указать, какой номер фото какой карточке принадлежит (id карточки -> номер).
# Фото cards/<id>.jpg, если оно есть, имеет приоритет над этим списком. Если для карточки нет ни
# cards/<id>.jpg, ни номера здесь — показываются прежние фото: role_*.jpg, затем старое photo_2026-09-18_….jpg,
# и в самом конце градиент редкости. Так что ничего из прежних фото не теряется.
CARD_PHOTO_NUM = {
    # сначала карточки, у которых вообще не было фото
    "hungry": 4,   "newbie": 5,   "spammer": 6,  "night": 7,    "memer": 8,
    "clipper": 9,  "fan": 10,     "skeptic": 11, "sleepy": 12,  "tiktoker": 13,
    "sub": 14,     "regular": 15, "editor": 16,  "kind": 17,    "alons": 18,
    "evil": 19,    "og": 20,      "boss": 21,
    # потом те, у кого были только старые общие фото photo_2026-09-18_….jpg
    "viewer": 22,  "chatter": 23, "supporter": 24, "ideator": 25,
}
_STATIC_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "miniapp", "static")
_PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _numbered_photo(card_id):
    """Имя файла вида 4.JPG для карточки (как он реально называется в папке) или None."""
    num = CARD_PHOTO_NUM.get(card_id)
    if num is None:
        return None
    try:
        files = _os.listdir(_STATIC_DIR)
    except OSError:
        return None
    for f in files:
        stem, ext = _os.path.splitext(f)
        if stem == str(num) and ext.lower() in _PHOTO_EXTS:
            return f
    return None


# Старые id карточек-заглушек -> новые id (у игроков, которые успели получить заглушку,
# карточка превращается в новую той же редкости; ничего не теряется).
ID_ALIASES = {
    "lurker": "hungry", "asker": "sleepy", "scenarist": "happy",
    "vip": "kind", "clutcher": "sly", "narrator": "melon",
    "champion": "evil", "godchat": "glam", "king": "boss",
}

CATALOG = [
    {
        "id": c[0], "name": c[1], "rarity": c[2], "desc": c[3], "legacy_img": c[4],
        # фото лежит в miniapp/static/cards/<id>.jpg; если файла нет — фронт пробует role_*.jpg,
        # старое фото и в конце рисует градиент, поэтому игра работает и без фото
        "photo": (f"cards/{c[0]}.jpg" if _os.path.exists(_os.path.join(_CARDS_DIR, f"{c[0]}.jpg"))
                  else _numbered_photo(c[0])),
        "role_imgs": ROLE_PHOTOS.get(c[0], []),
    }
    for c in _C
]

# Шансы выпадения (чем больше число, тем чаще)
DROP_WEIGHTS = {"common": 51.3, "uncommon": 28, "rare": 15, "epic": 5, "legendary": 0.7}   # легендарка была 2, теперь в 2,5 раза реже

# Дуэли ЧЕСТНЫЕ: сражаться можно только карточками одной редкости, шанс победы 50/50.
# Так нельзя «перебить» чужую common своей epic (раньше это был почти 100% выигрыш).
DUEL_WIN_CHANCE = 0.4

# Две валюты:
#  • МОНЕТЫ 🪙 — игровые, зарабатываются активностью, тратятся на открытие обычной карточки;
#  • ЗВЁЗДЫ TELEGRAM ⭐ (XTR) — настоящие деньги, ими покупаются паки в магазине.
OPEN_COST = 20   # монет за обычную карточку (шансы как у обычного открытия)

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]

# ОБМЕН (трейд): отдаёшь N лишних карточек одной редкости -> шанс получить карточку редкостью выше.
# Не повезло — получаешь одну карточку той же редкости (отдавал N, вернулась 1).
# «Лишняя» = вторая и последующие копии: единственную копию в обмен отдать нельзя.
# редкость: (сколько отдать, на что обменять, шанс успеха)
TRADE_RULES = {
    "common":   (5, "uncommon",  0.30),   # было 0.60
    "uncommon": (4, "rare",      0.225),  # было 0.45
    "rare":     (3, "epic",      0.15),   # было 0.30
    "epic":     (3, "legendary", 0.125),  # было 0.25
}
# ОБМЕН НА НАГРАДЫ ОТ РОМЫ: игрок отдаёт карточки (любые, в т.ч. единственную копию), у каждой редкости
# своя «ценность». Набрал нужную сумму — выбирает награду; заявка приходит админам в Telegram.
# Это отдельно от TRADE_RULES (обмен дубликатов на редкость выше). Звёзды Telegram тут не участвуют.
EXCH_VALUE = {"common": 15, "uncommon": 20, "rare": 30, "epic": 60, "legendary": 120}
EXCH_REWARDS = [
    {"id": "circle",   "name": "Видео-кружок",        "desc": "Персональный кружок только для тебя", "cost": 625},    # было 250
    {"id": "congrats", "name": "Поздравление",        "desc": "Видео-поздравление тебе или другу",   "cost": 1000},   # было 400
    {"id": "answer",   "name": "Ответ на вопрос",     "desc": "Рома ответит на твой вопрос в видео", "cost": 1500},   # было 600
]
EXCH_MAX_CARDS = 100   # технический потолок на одну заявку

TRADE_PREFER_MISSING = 3   # карточка, которой ещё нет, выпадает в обмене в 3 раза охотнее

# Паки в магазине. Каждый слот пака = «минимальная редкость» карточки в этом слоте:
# карточка выбирается среди всех карточек этой редкости и выше (шансы по DROP_WEIGHTS).
# Цены подобраны симуляцией (см. прайс-лист в README_PRICING.md): топ-донатер собирает
# полную коллекцию примерно за 450-750 ⭐ (30 карточек, с обменом), бесплатный игрок — месяцами.
PACK_SLOTS = {
    "common": ["common"],                                                   # 1 карта, любая редкость
    "rare": ["rare", "uncommon", "common", "common"],                       # 4 карты, минимум 1 Rare+
    "mega": ["epic", "rare", "rare", "uncommon", "uncommon"] + ["common"] * 6,   # 11 карт, Epic+ и 2 Rare+
    "legend1": ["legendary"],                                               # 1 гарантированная легендарная
    "legend2": ["legendary", "legendary"],                                  # 2 гарантированные легендарные (разные)
}

# название -> (цена в звёздах Telegram, сколько карточек, заголовок, описание)
# Ключи "common"/"rare"/"mega" не менять — на них завязана вёрстка и оплата.
STARS_SINGLE = 5   # ⭐ за одну карточку (то же, что 20 🪙 → курс 1 ⭐ ≈ 4 🪙)
PACKS = {
    "common": (STARS_SINGLE, len(PACK_SLOTS["common"]), "Одна карточка", "1 карточка любой редкости"),
    "rare": (49, len(PACK_SLOTS["rare"]), "Редкий пак", "4 карточки, минимум одна Rare или выше"),
    "mega": (199, len(PACK_SLOTS["mega"]), "Мега-пак", "11 карточек: минимум одна Epic+ и две Rare+"),
    "legend1": (599, len(PACK_SLOTS["legend1"]), "Легендарная карта", "1 гарантированная легендарная карточка"),
    "legend2": (999, len(PACK_SLOTS["legend2"]), "Две легендарные", "2 разные гарантированные легендарные карточки"),
}
# В этих паках карточки не повторяются внутри одного пака (пока в пуле есть другие варианты)
PACK_DISTINCT = {"legend1", "legend2"}
# Сколько звёзд один человек может потратить в сутки (по МСК). None — без лимита (сейчас лимита нет).
STARS_DAILY_CAP = None

# КОНКУРС «Собери всю коллекцию». Всё, что видит игрок, берётся отсюда — правь тексты здесь.
# Менял состав карточек или запускаешь новый сезон — увеличь version: у всех завершение сбросится.
CONTEST = {
    "version": 1,
    "active": True,
    "title": "Конкурс: собери всю коллекцию",
    "prize": "Это секрет 🤫",
    "rules": (
        "Собери все 30 карточек всех редкостей. Победителя определит рулетка среди всех, кто собрал коллекцию. "
        "Чем раньше ты собрал — тем выше твой шанс выиграть. Время засчитывается в момент, когда в коллекции "
        "появилась последняя карточка."
    ),
    # Строки для отображения. Реальные веса шансов — в CONTEST_WEIGHTS ниже (игрокам не показываются).
    "places": [
        "Собрал первым — самый высокий шанс в рулетке",
        "Собрал вторым — шанс чуть ниже",
        "Собрал третьим — ещё ниже, и так далее",
    ],
    # Награда для ВСЕХ, кто собрал коллекцию (не только победителей)
    "everyone_reward": "Личное видео от Ромы",
    "ends": "",   # например "30 ноября" — покажется игрокам; пусто = без даты
}

# Вес в рулетке по порядку завершения коллекции: 1-й собравший, 2-й, 3-й, ...
# Все, кто собрал позже последнего в списке, получают вес CONTEST_BASE_WEIGHT.
# Шанс игрока = его вес / сумма весов всех собравших. Меняй под себя.
CONTEST_WEIGHTS = [10, 8, 6, 5, 4, 3]
CONTEST_BASE_WEIGHT = 2

# Ежедневный бонус монет по дням подряд (после 7-го дня цикл повторяется).
# Пропустил день — серия начинается заново.
DAILY_BONUS = [30, 30, 45, 45, 60, 60, 90]   # было [10, 10, 15, 15, 20, 20, 30] — теперь ×3

# Ставить в дуэли с другом можно только дубликат (карточку, у которой есть ≥2 копии).
# Включи, если не хочешь, чтобы игроки теряли единственную копию карточки.
DUEL_ONLY_DUPLICATES = False

START_COINS = 0          # стартовых монет больше нет
_OLD_START_BONUS = 30    # раньше всем выдавалось 30 — при миграции снимаем
# Сколько монет даётся за действие в боте/мини-аппе
STARS_FOR_ACTION = {
    "questions_anonymous": 5,
    "questions_named": 5,
    "ideas": 8,
    "ads": 8,
    "cooperation": 8,
    "other_proposals": 5,
    "story": 12,          # продолжение «Что было дальше?»
}
DAILY_COIN_CAP = 40           # за действия (вопросы, идеи, ЧБД) больше этого за сутки не начисляется. Ежедневный бонус — отдельно
CHALLENGE_TTL = 24 * 3600     # вызов другу живёт 24 часа
PVP_DAILY_LIMIT = 5           # дуэлей с ботом в сутки (победа даёт новую карточку, без лимита её можно фармить)


MSK_OFFSET = 3 * 3600   # сутки в игре считаем по Москве: бонус и кап сбрасываются в 00:00 МСК


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + MSK_OFFSET))


def _yesterday() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + MSK_OFFSET - 86400))


def _migrate_ids(g: dict) -> None:
    """Переносит карточки-заглушки со старыми id на новые (см. ID_ALIASES)."""
    cards = g.get("cards", {})
    for old, new in ID_ALIASES.items():
        if old in cards:
            cards[new] = cards.get(new, 0) + cards.pop(old)
    ch = g.get("challenge")
    if ch and ch.get("card") in ID_ALIASES:
        ch["card"] = ID_ALIASES[ch["card"]]
    for pack in g.get("unrevealed", []):
        pack["cards"] = [ID_ALIASES.get(c, c) for c in pack.get("cards", [])]


def ensure(stats: dict) -> dict:
    """Возвращает (и при необходимости создаёт) игровые данные пользователя."""
    g = stats.setdefault("game", {})
    if "stars" in g:   # старое поле: переносим в монеты и снимаем бесплатные 30
        g["coins"] = max(0, g.pop("stars") - _OLD_START_BONUS)
    g.setdefault("coins", START_COINS)
    g.setdefault("cards", {})          # {card_id: количество}
    g.setdefault("pvp_wins", 0)
    g.setdefault("challenge", None)    # {"id", "card", "ts"} — карточка заморожена
    g.setdefault("reward_notified", False)
    g.setdefault("earned", {"day": "", "n": 0})
    g.setdefault("paid_ids", [])       # id платежей Telegram (защита от двойного зачисления)
    g.setdefault("unrevealed", [])     # купленные паки, которые игрок ещё не «открыл» на экране
    g.setdefault("pvp_day", {"day": "", "n": 0})   # сколько дуэлей с ботом сегодня
    g.setdefault("purchases", [])      # журнал покупок за звёзды: [{pack, stars, ts, charge}]
    g.setdefault("stars_day", {"day": "", "n": 0})   # сколько звёзд потрачено сегодня (для STARS_DAILY_CAP)
    g.setdefault("stars_spent", 0)     # сколько всего звёзд Telegram потратил игрок
    g.setdefault("daily", {"last": "", "streak": 0})   # ежедневный бонус
    g.setdefault("promos_used", [])    # промокоды, которые игрок уже активировал
    g.setdefault("trades", 0)          # сколько обменов сделал
    g.setdefault("completed_ts", None) # когда собрал все карточки (для мест в конкурсе)
    if g.get("contest_ver") != CONTEST["version"]:
        # состав карточек изменился -> завершение коллекции считаем заново
        g["contest_ver"] = CONTEST["version"]
        g["completed_ts"] = None
        g["reward_notified"] = False
    g.setdefault("show_stars", False)  # показывать ли потраченные звёзды в глобальном топе (по желанию игрока)
    g.setdefault("exchanges", [])      # заявки на обмен карточек на награды от Ромы
    _migrate_ids(g)
    return g


def refund_expired(g: dict) -> bool:
    """Если вызов друга просрочен — возвращает карточку владельцу."""
    ch = g.get("challenge")
    if ch and time.time() - ch["ts"] > CHALLENGE_TTL:
        g["cards"][ch["card"]] = g["cards"].get(ch["card"], 0) + 1
        g["challenge"] = None
        return True
    return False


def award_for_action(stats: dict, stat_type: str) -> int:
    """Начисляет звёзды за действие. Возвращает, сколько реально начислено."""
    amount = STARS_FOR_ACTION.get(stat_type, 0)
    if not amount:
        return 0
    g = ensure(stats)
    day = _today()
    if g["earned"]["day"] != day:
        g["earned"] = {"day": day, "n": 0}
    room = DAILY_COIN_CAP - g["earned"]["n"]
    amount = max(0, min(amount, room))
    g["earned"]["n"] += amount
    g["coins"] += amount
    return amount


def _pick(pool: list) -> str:
    """Сначала выбираем РЕДКОСТЬ по DROP_WEIGHTS, потом случайную карточку этой редкости
    (раньше вес применялся к каждой карточке, и эпик/легенда выпадали вдвое реже задуманного)."""
    by_rarity = {}
    for c in pool:
        by_rarity.setdefault(CARDS[c], []).append(c)
    rarities = list(by_rarity)
    rarity = random.choices(rarities, weights=[DROP_WEIGHTS[r] for r in rarities], k=1)[0]
    return random.choice(by_rarity[rarity])


def _add(g: dict, card_id: str, n: int = 1):
    g["cards"][card_id] = g["cards"].get(card_id, 0) + n


def _remove(g: dict, card_id: str) -> bool:
    if g["cards"].get(card_id, 0) <= 0:
        return False
    g["cards"][card_id] -= 1
    if g["cards"][card_id] == 0:
        del g["cards"][card_id]
    return True


def daily_status(g: dict) -> dict:
    """Состояние ежедневного бонуса: можно ли забрать, какая серия и сколько дадут."""
    d = g["daily"]
    n = len(DAILY_BONUS)
    if d["last"] == _today():
        return {"available": False, "streak": d["streak"], "amount": DAILY_BONUS[d["streak"] % n]}
    streak = d["streak"] if d["last"] == _yesterday() else 0
    return {"available": True, "streak": streak, "amount": DAILY_BONUS[streak % n]}


def claim_daily(g: dict) -> dict:
    st = daily_status(g)
    if not st["available"]:
        return {"ok": False, "error": "Бонус на сегодня уже получен. Возвращайся завтра 🎁"}
    g["coins"] += st["amount"]
    g["daily"] = {"last": _today(), "streak": st["streak"] + 1}
    return {"ok": True, "amount": st["amount"], "streak": st["streak"] + 1}


def view(g: dict) -> dict:
    """Состояние для фронта."""
    ch = g.get("challenge")
    return {
        "catalog": CATALOG,
        "trade": trade_status(g),
        "contest": {k: CONTEST[k] for k in ("active", "title", "prize", "rules", "places", "everyone_reward", "ends")},
        "completed": bool(g.get("completed_ts")),
        "total_cards": len(CARDS),
        "open_cost": OPEN_COST,
        "daily": daily_status(g),
        "show_stars": bool(g.get("show_stars")),
        "coins": g["coins"],
        "cards": dict(g["cards"]),
        "pvp_wins": g["pvp_wins"],
        "challenge": ({"id": ch["id"], "card": ch["card"]} if ch else None),
        "all_collected": all(c in g["cards"] for c in CARDS),
        "pvp_left": max(0, PVP_DAILY_LIMIT - (g["pvp_day"]["n"] if g["pvp_day"]["day"] == _today() else 0)),
        "exchange": {"values": EXCH_VALUE, "rewards": EXCH_REWARDS},
        # цены магазина берёт фронт отсюда — в index.html их дублировать больше не нужно
        "packs": {k: {"stars": v[0], "count": v[1], "title": v[2], "desc": v[3]} for k, v in PACKS.items()},
        "stars_cap": STARS_DAILY_CAP,
        "daily_coin_cap": DAILY_COIN_CAP,
    }


# ---------- действия ----------

def open_card(g: dict) -> dict:
    if g["coins"] < OPEN_COST:
        return {"ok": False, "error": f"Недостаточно монет. Нужно {OPEN_COST} 🪙 (их дают за вопросы, идеи и ЧБД)"}
    g["coins"] -= OPEN_COST
    card = _pick(list(CARDS))
    is_new = card not in g["cards"]
    _add(g, card)
    return {"ok": True, "cards": [card], "new": [is_new]}


def stars_room(g: dict, price: int) -> bool:
    """Можно ли сегодня потратить ещё `price` звёзд."""
    if STARS_DAILY_CAP is None:
        return True
    d = g["stars_day"]
    spent = d["n"] if d["day"] == _today() else 0
    return spent + price <= STARS_DAILY_CAP


def grant_pack(g: dict, pack: str, charge_id: str) -> dict:
    """Выдаёт оплаченный (звёздами Telegram) пак. Повторный charge_id игнорируется."""
    if pack not in PACKS:
        return {"ok": False, "error": "Неизвестный пак"}
    if charge_id in g["paid_ids"]:
        return {"ok": False, "error": "Этот платёж уже зачислен", "duplicate": True}
    g["paid_ids"] = (g["paid_ids"] + [charge_id])[-200:]
    g["stars_spent"] = g.get("stars_spent", 0) + PACKS[pack][0]
    if g["stars_day"]["day"] != _today():
        g["stars_day"] = {"day": _today(), "n": 0}
    g["stars_day"]["n"] += PACKS[pack][0]
    g["purchases"] = (g.get("purchases", []) + [
        {"pack": pack, "stars": PACKS[pack][0], "ts": int(time.time()), "charge": charge_id}
    ])[-100:]

    got, new = [], []
    for min_rarity in PACK_SLOTS[pack]:
        need = RARITY_ORDER.index(min_rarity)
        pool = [c for c, r in CARDS.items() if RARITY_ORDER.index(r) >= need] or list(CARDS)
        if pack in PACK_DISTINCT:
            pool = [c for c in pool if c not in got] or pool
        card = _pick(pool)
        new.append(card not in g["cards"])
        _add(g, card)
        got.append(card)
    g["unrevealed"].append({"cards": got, "new": new})
    return {"ok": True, "cards": got, "new": new}


def claim_unrevealed(g: dict) -> list:
    """Отдаёт фронту купленные паки для показа и очищает список."""
    packs = g["unrevealed"]
    g["unrevealed"] = []
    return packs


def _duel_win() -> bool:
    """Дуэль честная: карточки одной редкости, шанс DUEL_WIN_CHANCE."""
    return random.random() < DUEL_WIN_CHANCE


def pvp_random(g: dict, card_id: str) -> dict:
    """Дуэль с «Ареной» (бот). Соперник — случайная карточка ТОЙ ЖЕ редкости, шанс 50/50.
    Победа — забираешь карточку соперника, поражение — твоя ставка теряется."""
    if card_id not in CARDS:
        return {"ok": False, "error": "Неизвестная карточка"}
    if g["cards"].get(card_id, 0) <= 0:
        return {"ok": False, "error": "У тебя нет этой карточки"}
    day = _today()
    if g["pvp_day"]["day"] != day:
        g["pvp_day"] = {"day": day, "n": 0}
    if g["pvp_day"]["n"] >= PVP_DAILY_LIMIT:
        return {"ok": False, "error": f"Лимит дуэлей с ареной на сегодня исчерпан ({PVP_DAILY_LIMIT}). Вызови друга или возвращайся завтра"}
    g["pvp_day"]["n"] += 1
    same = [c for c, r in CARDS.items() if r == CARDS[card_id]]
    opp = random.choice(same)
    win = _duel_win()
    if win:
        _add(g, opp)
        g["pvp_wins"] += 1
    else:
        _remove(g, card_id)
    return {"ok": True, "win": win, "my": card_id, "opp": opp}


def create_challenge(g: dict, card_id: str) -> dict:
    """Вызов другу: карточка замораживается (убирается из коллекции) до ответа."""
    refund_expired(g)
    if g.get("challenge"):
        return {"ok": False, "error": "У тебя уже есть активный вызов. Дождись ответа (до 24 часов)."}
    if DUEL_ONLY_DUPLICATES and g["cards"].get(card_id, 0) < 2:
        return {"ok": False, "error": "Ставить можно только дубликат: нужно минимум 2 такие карточки"}
    if not _remove(g, card_id):
        return {"ok": False, "error": "У тебя нет этой карточки"}
    cid = uuid.uuid4().hex[:8].upper()
    g["challenge"] = {"id": cid, "card": card_id, "rarity": CARDS[card_id], "ts": time.time()}
    return {"ok": True, "id": cid}


def find_challenge(user_stats: dict, cid: str):
    """Ищет активный вызов по id. Возвращает (user_id_str, stats) или (None, None)."""
    cid = (cid or "").strip().upper()
    for uid, st in user_stats.items():
        g = st.get("game")
        if not g:
            continue
        refund_expired(g)
        ch = g.get("challenge")
        if ch and ch["id"] == cid:
            return uid, st
    return None, None


def accept_challenge(owner_g: dict, guest_g: dict, guest_card: str) -> dict:
    """Дуэль по вызову. Победитель забирает обе карточки, проигравший ставку теряет."""
    ch = owner_g["challenge"]
    owner_card = ch["card"]
    if guest_card not in CARDS or guest_g["cards"].get(guest_card, 0) <= 0:
        return {"ok": False, "error": "У тебя нет этой карточки"}
    if CARDS[guest_card] != CARDS[owner_card]:
        return {"ok": False, "error": f"Дуэль честная: нужна карточка той же редкости ({CARDS[owner_card].capitalize()})"}
    if DUEL_ONLY_DUPLICATES and guest_g["cards"].get(guest_card, 0) < 2:
        return {"ok": False, "error": "Ставить можно только дубликат: нужно минимум 2 такие карточки"}

    owner_g["challenge"] = None
    _remove(guest_g, guest_card)          # ставка гостя уходит на кон
    guest_wins = _duel_win()
    winner = guest_g if guest_wins else owner_g
    # обе ставки достаются победителю
    _add(winner, owner_card)
    _add(winner, guest_card)
    winner["pvp_wins"] += 1
    return {
        "ok": True, "win": guest_wins,
        "my": guest_card, "opp": owner_card,
    }


# ---------- обмен (трейд) ----------

def _spare(g: dict) -> dict:
    """Лишние копии по редкостям: {rarity: {card_id: сколько лишних}}. Последняя копия не считается."""
    out = {r: {} for r in RARITY_ORDER}
    for c, n in g["cards"].items():
        if c in CARDS and n > 1:
            out[CARDS[c]][c] = n - 1
    return out


def trade_status(g: dict) -> list:
    """Для фронта: что можно обменять сейчас."""
    spare = _spare(g)
    res = []
    for r, (need, to, chance) in TRADE_RULES.items():
        have = sum(spare[r].values())
        res.append({"rarity": r, "need": need, "to": to, "chance": round(chance * 100), "have": have, "can": have >= need})
    return res


def trade(g: dict, rarity: str) -> dict:
    """Обмен: отдаёт `need` лишних карточек редкости `rarity` -> шанс на редкость выше."""
    rule = TRADE_RULES.get(rarity)
    if not rule:
        return {"ok": False, "error": "Эту редкость обменять нельзя"}
    need, to, chance = rule
    spare = _spare(g)[rarity]
    if sum(spare.values()) < need:
        return {"ok": False, "error": f"Нужно {need} лишних карточек {rarity.capitalize()} (дубликатов), у тебя {sum(spare.values())}"}

    # забираем сначала те копии, которых больше всего
    given = []
    left = need
    for c, n in sorted(spare.items(), key=lambda kv: -kv[1]):
        take = min(n, left)
        for _ in range(take):
            _remove(g, c)
            given.append(c)
        left -= take
        if left == 0:
            break

    success = random.random() < chance
    out_rarity = to if success else rarity
    pool = [c for c, r in CARDS.items() if r == out_rarity]
    weights = [TRADE_PREFER_MISSING if c not in g["cards"] else 1 for c in pool]
    got = random.choices(pool, weights=weights, k=1)[0]
    is_new = got not in g["cards"]
    _add(g, got)
    g["trades"] = g.get("trades", 0) + 1
    return {"ok": True, "success": success, "given": given, "got": got, "new": is_new, "rarity": out_rarity}


# ---------- промокоды ----------

def exchange(g: dict, reward_id: str, give) -> dict:
    """Обмен карточек на награду от Ромы. give = {card_id: сколько копий отдаём}.
    Карточки списываются сразу и навсегда; заявку админам отправляет бот (bot.py)."""
    reward = next((r for r in EXCH_REWARDS if r["id"] == reward_id), None)
    if not reward:
        return {"ok": False, "error": "Неизвестная награда"}
    if not isinstance(give, dict) or not give:
        return {"ok": False, "error": "Выбери карточки для обмена"}
    clean = {}
    for cid, n in give.items():
        try:
            n = int(n)
        except (TypeError, ValueError):
            return {"ok": False, "error": "Неверное количество"}
        if cid not in CARDS:
            return {"ok": False, "error": "Неизвестная карточка"}
        if n < 1:
            continue
        clean[cid] = n
    total = sum(clean.values())
    if not clean or total > EXCH_MAX_CARDS:
        return {"ok": False, "error": "Неверный набор карточек"}
    for cid, n in clean.items():
        if g["cards"].get(cid, 0) < n:
            return {"ok": False, "error": "Этих карточек уже нет в коллекции"}
    value = sum(EXCH_VALUE[CARDS[cid]] * n for cid, n in clean.items())
    if value < reward["cost"]:
        return {"ok": False, "error": f"Не хватает ценности: нужно {reward['cost']}, набрано {value}"}
    for cid, n in clean.items():
        for _ in range(n):
            _remove(g, cid)
    req = {"id": uuid.uuid4().hex[:6].upper(), "reward": reward_id, "cards": clean,
           "value": value, "ts": int(time.time())}
    g["exchanges"] = (g.get("exchanges", []) + [req])[-50:]
    return {"ok": True, "request": req, "reward_name": reward["name"], "count": total}


def redeem_promo(g: dict, user_stats: dict, code: str) -> dict:
    code = (code or "").strip().upper()
    if not code or len(code) > 40:
        return {"ok": False, "error": "Введи промокод"}
    p = PROMOS.get(code)
    if not p:
        return {"ok": False, "error": "Такого промокода нет"}
    if code in g["promos_used"]:
        return {"ok": False, "error": "Ты уже активировал этот промокод"}
    until = p.get("until")
    if until and _today() > until:
        return {"ok": False, "error": "Срок действия промокода закончился"}
    uses = p.get("uses")
    if uses is not None:
        used = sum(1 for st in user_stats.values() if code in ((st.get("game") or {}).get("promos_used") or []))
        if used >= uses:
            return {"ok": False, "error": "Промокод закончился — его уже активировали все, кто успел"}

    g["promos_used"] = g["promos_used"] + [code]
    res = {"ok": True, "coins": 0, "cards": [], "new": []}
    coins = int(p.get("coins") or 0)
    if coins:
        g["coins"] += coins
        res["coins"] = coins
    # конкретные карточки по id (поле card_ids в promos.py) — выдаются ровно они
    for card in p.get("card_ids") or []:
        if card in CARDS:
            res["new"].append(card not in g["cards"])
            _add(g, card)
            res["cards"].append(card)
    n_cards = int(p.get("cards") or 0)
    if n_cards:
        need = RARITY_ORDER.index(p.get("min_rarity", "common"))
        pool = [c for c, r in CARDS.items() if RARITY_ORDER.index(r) >= need] or list(CARDS)
        for _ in range(n_cards):
            card = _pick(pool)
            res["new"].append(card not in g["cards"])
            _add(g, card)
            res["cards"].append(card)
    return res


# ---------- конкурс ----------

def is_complete(g: dict) -> bool:
    return all(c in g["cards"] for c in CARDS)


def mark_completion(g: dict) -> bool:
    """Фиксирует момент, когда игрок собрал всё. True — если это произошло только что."""
    if is_complete(g) and not g.get("completed_ts"):
        g["completed_ts"] = time.time()
        return True
    return False


def contest_board(user_stats: dict, my_uid: str, name_of, limit: int = 10) -> dict:
    """Таблица конкурса: сначала те, кто собрал всё (по времени), потом по прогрессу."""
    rows = []
    for uid, st in user_stats.items():
        g = st.get("game")
        if not g or not g.get("cards"):
            continue
        done = g.get("completed_ts") if g.get("contest_ver") == CONTEST["version"] else None
        rows.append({"uid": uid, "unique": sum(1 for c in g["cards"] if c in CARDS), "ts": done})
    rows.sort(key=lambda r: (0, r["ts"]) if r["ts"] else (1, -r["unique"]))
    out, mine = [], None
    for i, r in enumerate(rows, 1):
        if r["uid"] == my_uid:
            mine = {"place": i, "unique": r["unique"], "done": bool(r["ts"])}
        if i <= limit:
            out.append({"place": i, "name": name_of(r["uid"]), "unique": r["unique"], "done": bool(r["ts"]), "me": r["uid"] == my_uid})
    finished = sum(1 for r in rows if r["ts"])
    return {"rows": out, "me": mine, "finished": finished, "total": len(CARDS)}


def contest_odds(user_stats: dict) -> list:
    """Шансы в рулетке для всех, кто собрал коллекцию (по порядку завершения).
    Возвращает [{"uid", "place", "weight", "chance"}], chance — в процентах."""
    done = []
    for uid, st in user_stats.items():
        g = st.get("game")
        if g and g.get("contest_ver") == CONTEST["version"] and g.get("completed_ts"):
            done.append((g["completed_ts"], uid))
    done.sort()
    rows = []
    for i, (_, uid) in enumerate(done):
        w = CONTEST_WEIGHTS[i] if i < len(CONTEST_WEIGHTS) else CONTEST_BASE_WEIGHT
        rows.append({"uid": uid, "place": i + 1, "weight": w})
    total = sum(r["weight"] for r in rows) or 1
    for r in rows:
        r["chance"] = round(r["weight"] * 100 / total, 1)
    return rows


def contest_draw(user_stats: dict):
    """Крутит рулетку: случайный победитель с учётом весов. None — если никто не собрал."""
    import random
    rows = contest_odds(user_stats)
    if not rows:
        return None
    return random.choices(rows, weights=[r["weight"] for r in rows], k=1)[0]
