"""Реферальная программа: приглашаешь друга — бонусы получаете оба.

Ссылка приглашения: https://t.me/<бот>?start=ref_<ID пригласившего>

УСЛОВИЕ БОНУСА: приглашённый должен быть «чистым» — ни разу не заходить во вкладку «Игра»
(у такого игрока в статистике ещё нет записи "game"). Просто быть зарегистрированным в боте можно.
Каждый человек может быть приглашён только один раз.

Всё хранится в записи игрока user_stats[<id>]["ref"], отдельного файла не нужно:
    у приглашённого:   {"by": "<id пригласившего>", "ts": ..., "coins": ...}
    у пригласившего:   {"invited": [{"uid", "ts", "coins", "card", "rewarded"}, ...]}

Все числа ниже можно править — ничего больше менять не нужно.
"""
import time

import game as cardgame

ENABLED = True

# Что получает приглашённый друг (открытие обычной карточки стоит 20 🪙, так что 100 🪙 = 5 карточек)
FRIEND_COINS = 100

# Что получает пригласивший за каждого друга: (с какого по счёту друга, сколько монет за друга).
# Чем больше друзей — тем больше монет за каждого следующего.
INVITER_COINS_TIERS = [(1, 60), (5, 80), (10, 100)]

# Дополнительная награда, когда набралось нужное число друзей:
#   число друзей -> {"coins": сколько монет сверху, "cards": [минимальная редкость каждой карточки]}
MILESTONES = {
    3:  {"coins": 50,  "cards": ["rare"]},
    5:  {"coins": 100, "cards": ["epic"]},
    10: {"coins": 200, "cards": ["legendary"]},
    25: {"coins": 500, "cards": ["legendary", "epic"]},
}

# Защита от накрутки: сколько наград за приглашения пригласивший может получить за сутки (МСК).
# Если лимит исчерпан, друг всё равно получит свой бонус, а пригласивший — нет.
# None — без лимита.
DAILY_REWARDED_LIMIT = 5


def inviter_coins_for(n: int) -> int:
    """Монеты за n-го по счёту друга."""
    coins = 0
    for start, amount in INVITER_COINS_TIERS:
        if n >= start:
            coins = amount
    return coins


def _invited(stats: dict) -> list:
    return (stats.get("ref") or {}).get("invited") or []


def rewarded_count(stats: dict) -> int:
    return sum(1 for e in _invited(stats) if e.get("rewarded", True))


def check_friend(stats) -> str:
    """Можно ли выдать бонус как приглашённому. Возвращает "ok" или причину отказа:
    "referred" — уже приглашён раньше, "played" — уже заходил в игру."""
    if not stats:
        return "ok"
    if (stats.get("ref") or {}).get("by"):
        return "referred"
    if "game" in stats:
        return "played"
    return "ok"


def apply_referral(user_stats: dict, inviter_uid: str, friend_uid: str) -> dict:
    """Проверяет условия и выдаёт бонусы обоим. Всё делается в памяти без пауз (await),
    так что два запроса одновременно не проскочат. Сохранение на GitHub — на стороне бота.

    Возвращает {"ok": True, "friend_coins", "inviter_coins", "card", "rewarded", "total"}
    или {"ok": False, "reason": "self" | "no_inviter" | "referred" | "played"}."""
    if not ENABLED:
        return {"ok": False, "reason": "off"}
    if inviter_uid == friend_uid:
        return {"ok": False, "reason": "self"}
    inviter = user_stats.get(inviter_uid)
    friend = user_stats.get(friend_uid)
    if inviter is None or friend is None:
        return {"ok": False, "reason": "no_inviter"}
    reason = check_friend(friend)
    if reason != "ok":
        return {"ok": False, "reason": reason}

    now = int(time.time())
    today = cardgame._today()

    # награда пригласившему (с учётом суточного лимита)
    rewarded = True
    if DAILY_REWARDED_LIMIT is not None:
        done_today = sum(
            1 for e in _invited(inviter)
            if e.get("rewarded", True)
            and time.strftime("%Y-%m-%d", time.gmtime(e.get("ts", 0) + cardgame.MSK_OFFSET)) == today
        )
        rewarded = done_today < DAILY_REWARDED_LIMIT

    inviter_coins, bonus_coins, cards = 0, 0, []
    total = rewarded_count(inviter)
    if rewarded:
        total += 1
        inviter_coins = inviter_coins_for(total)
        ig = cardgame.ensure(inviter)
        ig["coins"] += inviter_coins
        ms = MILESTONES.get(total)
        if ms:
            bonus_coins = ms.get("coins", 0)
            ig["coins"] += bonus_coins
            new_flags = []
            for min_rarity in ms.get("cards", []):
                need = cardgame.RARITY_ORDER.index(min_rarity)
                pool = [c for c, r in cardgame.CARDS.items() if cardgame.RARITY_ORDER.index(r) >= need] or list(cardgame.CARDS)
                card = cardgame._pick(pool)
                new_flags.append(card not in ig["cards"])
                cardgame._add(ig, card)
                cards.append(card)
            if cards:
                # покажется анимацией открытия, когда пригласивший зайдёт в игру
                ig["unrevealed"].append({"cards": list(cards), "new": new_flags})

    # награда другу (запись game создаётся здесь — после проверки условия)
    fg = cardgame.ensure(friend)
    fg["coins"] += FRIEND_COINS

    friend["ref"] = {"by": inviter_uid, "ts": now, "coins": FRIEND_COINS}
    inv = inviter.setdefault("ref", {}).setdefault("invited", [])
    inv.append({"uid": friend_uid, "ts": now, "coins": inviter_coins + bonus_coins, "cards": cards, "rewarded": rewarded})

    return {"ok": True, "friend_coins": FRIEND_COINS, "inviter_coins": inviter_coins,
            "bonus_coins": bonus_coins, "cards": cards, "rewarded": rewarded, "total": total}


def friends_view(user_stats: dict, uid: str, bot_username: str, label_of) -> dict:
    """Данные для вкладки «Друзья». Ничего не создаёт и не меняет в статистике игрока —
    иначе простое открытие вкладки сделало бы приглашённого «уже игравшим»."""
    st = user_stats.get(uid) or {}
    ref = st.get("ref") or {}
    count = rewarded_count(st)

    invited = [
        {"name": label_of(e["uid"]), "ts": e.get("ts", 0), "coins": e.get("coins", 0),
         "cards": [cardgame.NAMES.get(c, c) for c in (e.get("cards") or [])],
         "rewarded": e.get("rewarded", True)}
        for e in reversed(_invited(st))
    ]
    by = None
    if ref.get("by"):
        by = {"name": label_of(ref["by"]), "ts": ref.get("ts", 0), "coins": ref.get("coins", 0)}

    milestones = [{"need": n, "coins": m.get("coins", 0), "cards": list(m.get("cards", [])), "done": count >= n}
                  for n, m in sorted(MILESTONES.items())]
    nxt = next((m for m in milestones if not m["done"]), None)
    return {
        "ok": True,
        "enabled": ENABLED,
        "link": f"https://t.me/{bot_username}?start=ref_{uid}",
        "count": count,
        "invited": invited,
        "invited_by": by,
        "friend_coins": FRIEND_COINS,
        "tiers": [{"from": s, "coins": c} for s, c in INVITER_COINS_TIERS],
        "milestones": milestones,
        "next_milestone": nxt,
        "daily_limit": DAILY_REWARDED_LIMIT,
    }
