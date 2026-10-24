"""
Мини-апп для Telegram-бота: проверка подписи initData + API-роутер с админ-функциями.

Все админ-эндпоинты требуют валидный Telegram initData с user_id из ADMIN_CHAT_ID.
"""

import hashlib
import hmac
import json
import time
from typing import Awaitable, Callable, Optional
from urllib.parse import parse_qsl

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import JSONResponse, Response
import httpx
from pydantic import BaseModel, Field

INIT_DATA_MAX_AGE_SECONDS = 24 * 3600   # сутки: апп часто остаётся открытым дольше часа


def validate_init_data(init_data: str, bot_token: str, max_age: int = INIT_DATA_MAX_AGE_SECONDS) -> dict:
    """Проверяет подпись initData, присланного Telegram Mini App."""
    if not init_data:
        raise ValueError("empty init_data")

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError as e:
        raise ValueError(f"bad init_data format: {e}")

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise ValueError("no hash in init_data")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("bad signature")

    auth_date = int(pairs.get("auth_date", "0"))
    if max_age and (time.time() - auth_date) > max_age:
        raise ValueError("init_data expired")

    result = dict(pairs)
    if "user" in result:
        result["user"] = json.loads(result["user"])
    return result


# Лимита по длине для пользователя нет; это лишь скрытый технический потолок,
# чтобы никто не залил на сервер/в GitHub гигабайты текста.
MAX_PAYLOAD_TEXT = 100_000


class StoryPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PAYLOAD_TEXT)


class QuestionPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PAYLOAD_TEXT)
    anonymous: bool = True


class BroadcastPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PAYLOAD_TEXT)


class IdeaPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PAYLOAD_TEXT)
    idea_type: str = "ideas"


class AiChatPayload(BaseModel):
    # Жёсткий потолок формата; реальный лимит (1000) проверяет бот и отвечает понятной ошибкой
    text: str = Field(..., min_length=1, max_length=5000)


class StreamTimePayload(BaseModel):
    target_iso: str


class SmsPayload(BaseModel):
    user_id: int
    text: str = Field(..., min_length=1, max_length=MAX_PAYLOAD_TEXT)


def build_miniapp_router(
    *,
    bot_token: str,
    admin_ids: list,
    get_top_users: Callable[[int], list],
    get_next_stream_info: Callable[[], dict],
    get_user_stats_view: Callable[[int], dict],
    get_chbd_enabled: Callable[[], bool],
    submit_story: Callable[[dict, str], Awaitable[dict]],
    submit_question: Callable[[dict, str, bool], Awaitable[dict]],
    submit_idea: Callable[[dict, str, str], Awaitable[dict]],
    get_all_messages: Callable[[str], list],
    do_broadcast: Callable[[list, str], Awaitable[int]],
    do_ban: Callable[[int], Awaitable[None]],
    toggle_chbd: Callable[[bool], Awaitable[None]],
    get_trash_enabled: Callable[[], bool],
    submit_trash: Callable[[dict, str], Awaitable[dict]],
    toggle_trash: Callable[[bool], Awaitable[None]],
    do_sms: Callable[[int, str], Awaitable[None]],
    set_stream_time: Callable[[str], Awaitable[dict]],
    clear_stream_time: Callable[[], Awaitable[None]],
    get_avatar_file_path: Callable[[int], Awaitable[Optional[str]]],
    ai_chat: Callable[[dict, str], Awaitable[dict]],
    ai_reset: Callable[[dict], Awaitable[None]],
    game_action: Callable[[dict, str, dict], Awaitable[dict]],
    friends_info: Callable[[dict], Awaitable[dict]],
) -> APIRouter:
    """Собирает APIRouter с эндпоинтами мини-аппа и админ-функциями."""

    router = APIRouter()

    def _authenticate(init_data_header: Optional[str]) -> dict:
        if not init_data_header:
            raise HTTPException(status_code=401, detail="no init data")
        try:
            data = validate_init_data(init_data_header, bot_token)
        except ValueError:
            raise HTTPException(status_code=401, detail="invalid init data")
        user = data.get("user")
        if not user:
            raise HTTPException(status_code=401, detail="no user in init data")
        return user

    def _check_admin(user_id: int) -> bool:
        """Проверяет, является ли пользователь админом"""
        return user_id in admin_ids

    # ============================================================
    # ПУБЛИЧНЫЕ ЭНДПОИНТЫ
    # ============================================================

    @router.get("/api/countdown")
    async def countdown():
        """Таймер до стрима"""
        return JSONResponse(get_next_stream_info())

    @router.get("/api/top")
    async def top(limit: int = 10, sort: str = "score"):
        """Топ участников: sort = score | cards | coins | stars"""
        limit = max(1, min(limit, 50))
        if sort not in ("score", "cards", "coins", "stars"):
            sort = "score"
        return JSONResponse(get_top_users(limit, sort))

    @router.get("/api/chbd_status")
    async def chbd_status():
        """Статус ЧБД"""
        return JSONResponse({"enabled": get_chbd_enabled()})

    @router.get("/api/trash_status")
    async def trash_status():
        """Открыт ли сейчас приём треш историй"""
        return JSONResponse({"enabled": get_trash_enabled()})

    # ============================================================
    # ЗАЩИЩЁННЫЕ ЭНДПОИНТЫ (требуют аутентификации)
    # ============================================================

    @router.get("/api/profile")
    async def profile(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Профиль пользователя"""
        user = _authenticate(x_telegram_init_data)
        stats = get_user_stats_view(int(user["id"]))
        return JSONResponse({
            **stats,
            "id": user["id"],
            "username": user.get("username") or stats.get("username"),
            "first_name": user.get("first_name"),
        })

    @router.post("/api/story")
    async def post_story(payload: StoryPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Отправить продолжение истории (ЧБД)"""
        user = _authenticate(x_telegram_init_data)
        result = await submit_story(user, payload.text)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Не удалось отправить"))
        return JSONResponse(result)

    @router.post("/api/trash")
    async def post_trash(payload: StoryPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Отправить треш историю"""
        user = _authenticate(x_telegram_init_data)
        result = await submit_trash(user, payload.text)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Не удалось отправить"))
        return JSONResponse(result)

    @router.post("/api/question")
    async def post_question(payload: QuestionPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Отправить вопрос"""
        user = _authenticate(x_telegram_init_data)
        result = await submit_question(user, payload.text, payload.anonymous)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Не удалось отправить"))
        return JSONResponse(result)

    @router.post("/api/idea")
    async def post_idea(payload: IdeaPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Отправить идею / рекламу / сотрудничество / другое"""
        user = _authenticate(x_telegram_init_data)
        result = await submit_idea(user, payload.text, payload.idea_type)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Не удалось отправить"))
        return JSONResponse(result)

    async def _avatar_response(user_id: int) -> Response:
        """Бот скачивает фото профиля у Telegram и отдаёт его сам —
        токен бота в браузер не попадает."""
        file_path = await get_avatar_file_path(user_id)
        if not file_path:
            raise HTTPException(status_code=404, detail="no avatar")

        # В python-telegram-bot file_path обычно уже полный URL, но на всякий случай
        # поддерживаем и относительный путь.
        url = file_path if file_path.startswith("http") else f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
            r.raise_for_status()
        except Exception:
            raise HTTPException(status_code=404, detail="avatar fetch failed")

        return Response(
            content=r.content,
            media_type=r.headers.get("content-type", "image/jpeg"),
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @router.get("/api/avatar/{user_id}")
    async def avatar(user_id: int):
        """Аватарка участника топа. Отдаём только тем, кто в топе-50."""
        allowed = set()
        for u in get_top_users(50):
            try:
                allowed.add(int(u["user_id"]))
            except (KeyError, ValueError, TypeError):
                continue
        if user_id not in allowed:
            raise HTTPException(status_code=404, detail="not found")
        return await _avatar_response(user_id)

    @router.get("/api/my_avatar")
    async def my_avatar(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Аватарка самого пользователя (для профиля) — по подписанному initData."""
        user = _authenticate(x_telegram_init_data)
        return await _avatar_response(int(user["id"]))

    # ============================================================
    # АДМИН-ЭНДПОИНТЫ (требуют администратора)
    # ============================================================

    @router.get("/api/admin/check")
    async def admin_check(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Проверка, является ли пользователь админом"""
        user = _authenticate(x_telegram_init_data)
        user_id = int(user["id"])
        is_admin = _check_admin(user_id)
        return JSONResponse({"is_admin": is_admin})

    @router.get("/api/admin/stats/{user_id}")
    async def admin_stats(user_id: str, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Получить статистику пользователя"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        try:
            uid = int(user_id)
            stats = get_user_stats_view(uid)
            stats["user_id"] = user_id
            return JSONResponse(stats)
        except Exception:
            raise HTTPException(status_code=404, detail="user not found")

    @router.get("/api/admin/messages")
    async def admin_messages(type: str = "questions", x_telegram_init_data: Optional[str] = Header(default=None)):
        """Получить сообщения (questions, stories, proposals)"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        if type not in ["questions", "stories", "proposals", "trash"]:
            raise HTTPException(status_code=400, detail="invalid type")

        messages = get_all_messages(type)
        return JSONResponse({"messages": messages, "type": type})

    @router.post("/api/admin/ban/{user_id}")
    async def admin_ban(user_id: str, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Забанить пользователя"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        try:
            uid = int(user_id)
            await do_ban(uid)
            return JSONResponse({"ok": True})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/api/admin/broadcast")
    async def admin_broadcast(payload: BroadcastPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Рассылка подписчикам"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        try:
            sent = await do_broadcast(["subscribers"], payload.text)
            return JSONResponse({"ok": True, "sent": sent})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/api/admin/super_broadcast")
    async def admin_super_broadcast(payload: BroadcastPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Рассылка ВСЕМ пользователям"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        try:
            sent = await do_broadcast(["all"], payload.text)
            return JSONResponse({"ok": True, "sent": sent})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/api/admin/chbd_on")
    async def admin_chbd_on(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Включить ЧБД"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        try:
            await toggle_chbd(True)
            return JSONResponse({"ok": True})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/api/admin/chbd_off")
    async def admin_chbd_off(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Выключить ЧБД"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        try:
            await toggle_chbd(False)
            return JSONResponse({"ok": True})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/api/admin/trash_on")
    async def admin_trash_on(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Открыть приём треш историй"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")
        await toggle_trash(True)
        return JSONResponse({"ok": True})

    @router.post("/api/admin/trash_off")
    async def admin_trash_off(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Закрыть приём треш историй"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")
        await toggle_trash(False)
        return JSONResponse({"ok": True})

    @router.post("/api/admin/sms")
    async def admin_sms(payload: SmsPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Отправить личное сообщение пользователю от лица бота (аналог /sms)"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        try:
            await do_sms(payload.user_id, payload.text)
            return JSONResponse({"ok": True})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/api/ai/chat")
    async def post_ai_chat(payload: AiChatPayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Сообщение Алонсу (ИИ) из вкладки «Алонс»"""
        user = _authenticate(x_telegram_init_data)
        result = await ai_chat(user, payload.text)
        if not result.get("ok"):
            raise HTTPException(status_code=429 if "лимит" in result.get("error", "") else 400,
                                detail=result.get("error", "Ошибка"))
        return JSONResponse(result)

    @router.post("/api/ai/reset")
    async def post_ai_reset(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Очистить историю чата с Алонсом"""
        user = _authenticate(x_telegram_init_data)
        await ai_reset(user)
        return JSONResponse({"ok": True})

    @router.post("/api/game/{action}")
    async def post_game(action: str, payload: dict = Body(default={}),
                        x_telegram_init_data: Optional[str] = Header(default=None)):
        """Игра «Карточки»: state / open / buy / pvp / challenge_create /
        challenge_info / challenge_accept. Вся логика и случайность — на сервере."""
        user = _authenticate(x_telegram_init_data)
        result = await game_action(user, action, payload or {})
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Ошибка"))
        return JSONResponse(result)

    @router.get("/api/friends")
    async def get_friends(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Вкладка «Друзья»: реферальная ссылка, кого пригласил и кто пригласил тебя.
        Отдельно от /api/game/*, чтобы просмотр вкладки не создавал игровую запись."""
        user = _authenticate(x_telegram_init_data)
        result = await friends_info(user)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Ошибка"))
        return JSONResponse(result)

    @router.post("/api/admin/stream_time")
    async def admin_set_stream_time(payload: StreamTimePayload, x_telegram_init_data: Optional[str] = Header(default=None)):
        """Вручную задать время следующего стрима (МСК)"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        result = await set_stream_time(payload.target_iso)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Не удалось задать время"))
        return JSONResponse(result)

    @router.post("/api/admin/stream_time/clear")
    async def admin_clear_stream_time(x_telegram_init_data: Optional[str] = Header(default=None)):
        """Убрать ручное время — таймер снова считает по расписанию"""
        user = _authenticate(x_telegram_init_data)
        if not _check_admin(int(user["id"])):
            raise HTTPException(status_code=403, detail="not admin")

        await clear_stream_time()
        return JSONResponse({"ok": True})

    return router
