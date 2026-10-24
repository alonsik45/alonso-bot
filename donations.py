"""Уведомления о донатах из DonationAlerts → админам в бот (имя, сумма и текст доната).

Как работает: раз в POLL_INTERVAL секунд бот спрашивает у DonationAlerts список последних
донатов (GET /api/v1/alerts/donations) и присылает админам те, что появились с прошлого раза.

Нужна одна переменная окружения на Render:
    DONATIONALERTS_TOKEN — токен доступа с правом oauth-donation-index (как получить — в ответе в чате)

Без неё модуль просто не включается, бот работает как раньше.

Ограничение: «что уже присылали» хранится в памяти. При перезапуске бота прежние донаты
повторно не придут, а пришедшие ровно во время простоя — пропустятся.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://www.donationalerts.com/api/v1/alerts/donations"
POLL_INTERVAL = 20          # секунд; лимит DonationAlerts — 60 запросов в минуту
MAX_PER_POLL = 20           # не заваливать чат, если накопилась пачка

_seen: set = set()
_baseline_done = False
_auth_alerted = False


def format_donation(d: dict) -> str:
    amount = d.get("amount")
    if isinstance(amount, float) and amount.is_integer():
        amount = int(amount)
    lines = ["💸 ДОНАТ", "", f"👤 {d.get('username') or 'Аноним'}", f"💰 {amount} {d.get('currency', '')}".rstrip()]
    if d.get("message_type") == "audio":
        lines.append("🎙 Голосовое сообщение — послушай в DonationAlerts")
    elif (d.get("message") or "").strip():
        lines += ["", f"💬 {d['message'].strip()[:3500]}"]
    return "\n".join(lines)


_client = None


def _get_client() -> "httpx.AsyncClient":
    """Один общий клиент на все опросы. Создавать новый каждые 20 секунд нельзя: каждый новый клиент
    заново грузит SSL-сертификаты, и память сервера растёт, пока Render не убьёт его (OOM)."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15)
    return _client


async def _reset_client():
    """После сетевой ошибки пересоздаём клиент, чтобы не держать «зависшее» соединение."""
    global _client
    client, _client = _client, None
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            pass


async def _fetch(token: str) -> list:
    try:
        r = await _get_client().get(API_URL, headers={"Authorization": f"Bearer {token}"})
    except httpx.TransportError:
        await _reset_client()
        raise
    if r.status_code == 401:
        raise PermissionError("401")
    r.raise_for_status()
    return r.json().get("data", [])


async def _notify(bot, admin_ids: list, text: str):
    for admin in admin_ids:
        try:
            await bot.send_message(chat_id=admin, text=text)
        except Exception:
            logger.exception("Не удалось отправить уведомление о донате админу %s", admin)


def setup(app, admin_ids: list) -> bool:
    """Включает опрос, если задан токен. Вызывать из main() после создания app."""
    token = os.getenv("DONATIONALERTS_TOKEN")
    if not token:
        logger.info("DONATIONALERTS_TOKEN не задан — уведомления о донатах выключены")
        return False
    if app.job_queue is None:
        logger.warning("JobQueue недоступен — уведомления о донатах не заработают")
        return False

    async def poll(context):
        global _baseline_done, _auth_alerted
        try:
            donations = await _fetch(token)
        except PermissionError:
            if not _auth_alerted:
                _auth_alerted = True
                await _notify(context.bot, admin_ids,
                              "⚠️ DonationAlerts не принимает токен (DONATIONALERTS_TOKEN). "
                              "Уведомления о донатах не приходят — нужно получить новый токен.")
            return
        except Exception:
            logger.exception("Ошибка запроса к DonationAlerts")
            return
        _auth_alerted = False

        if not _baseline_done:
            # первый опрос после запуска: всё, что уже есть, считаем прочитанным
            _seen.update(d["id"] for d in donations)
            _baseline_done = True
            logger.info("DonationAlerts подключён, существующих донатов: %d", len(donations))
            return

        new = [d for d in donations if d["id"] not in _seen]
        for d in sorted(new, key=lambda x: x["id"])[-MAX_PER_POLL:]:
            await _notify(context.bot, admin_ids, format_donation(d))
        _seen.update(d["id"] for d in new)

    app.job_queue.run_repeating(poll, interval=POLL_INTERVAL, first=5)
    logger.info("Уведомления о донатах включены")
    return True
