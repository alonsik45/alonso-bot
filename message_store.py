import json
import logging
import os

from github import Github, GithubException

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
MESSAGES_FILE_PATH = os.getenv("MESSAGES_FILE_PATH", "messages.json")

_repo = None


def _get_repo():
    global _repo
    if _repo is None:
        gh = Github(GITHUB_TOKEN)
        _repo = gh.get_repo(GITHUB_REPO)
    return _repo


def load_messages():
    """Загружает message_to_user, message_content и message_counter из GitHub.

    Раньше эти три переменные жили только в оперативной памяти процесса — при
    любом перезапуске бота (например, Render на бесплатном тарифе перезапускает
    процесс при простое) вся связка "message_id → кто спросил / что спросил"
    терялась. Из-за этого кнопки «🔴 На стриме», «✍️ Ответить» и «✅ Прочитано»
    переставали находить автора для сообщений, заданных до последнего рестарта.

    Возвращает (message_to_user, message_content, message_counter).
    При отсутствии файла или любой ошибке возвращает пустое состояние —
    бот не должен падать из-за проблем с этим хранилищем.
    """
    try:
        repo = _get_repo()
        contents = repo.get_contents(MESSAGES_FILE_PATH)
        data = json.loads(contents.decoded_content.decode("utf-8"))

        message_to_user = {int(k): v for k, v in data.get("message_to_user", {}).items()}
        message_content = {
            int(k): tuple(v) for k, v in data.get("message_content", {}).items()
        }
        message_counter = data.get("message_counter", 0)

        logger.info(f"✅ Загружено {len(message_content)} сообщений из GitHub")
        return message_to_user, message_content, message_counter

    except GithubException as e:
        if e.status == 404:
            logger.info("ℹ️ messages.json ещё не создан — начинаем с пустого состояния")
        else:
            logger.exception(f"❌ Ошибка при загрузке messages.json: {e}")
        return {}, {}, 0
    except Exception as e:
        logger.exception(f"❌ Ошибка при загрузке сообщений: {e}")
        return {}, {}, 0


def save_messages(message_to_user: dict, message_content: dict, message_counter: int):
    """Сохраняет message_to_user, message_content и message_counter на GitHub.

    Вызывать сразу после регистрации нового вопроса/предложения/истории/вишлиста
    (после того как message_id получил своё содержимое), чтобы кнопки админа
    продолжали работать даже после перезапуска процесса.
    """
    try:
        repo = _get_repo()

        payload = {
            "message_to_user": {str(k): v for k, v in message_to_user.items()},
            "message_content": {str(k): list(v) for k, v in message_content.items()},
            "message_counter": message_counter,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2)

        try:
            existing = repo.get_contents(MESSAGES_FILE_PATH)
            repo.update_file(MESSAGES_FILE_PATH, "Update messages.json", content, existing.sha)
        except GithubException as e:
            if e.status == 404:
                repo.create_file(MESSAGES_FILE_PATH, "Create messages.json", content)
            else:
                raise

    except Exception as e:
        logger.exception(f"❌ Ошибка при сохранении сообщений: {e}")
