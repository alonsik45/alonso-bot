import json
import logging
import os

from github import Github, GithubException

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
BANS_FILE_PATH = os.getenv("BANS_FILE_PATH", "banned_users.json")

_repo = None


def _get_repo():
    global _repo
    if _repo is None:
        gh = Github(GITHUB_TOKEN)
        _repo = gh.get_repo(GITHUB_REPO)
    return _repo


def load_banned_users() -> set:
    """Загружает список забаненных user_id из GitHub. Пустое множество при
    отсутствии файла или любой ошибке — бот не должен падать из-за этого."""
    try:
        repo = _get_repo()
        contents = repo.get_contents(BANS_FILE_PATH)
        data = json.loads(contents.decoded_content.decode("utf-8"))
        banned = set(int(uid) for uid in data.get("banned", []))
        logger.info(f"✅ Загружено {len(banned)} забаненных пользователей из GitHub")
        return banned
    except GithubException as e:
        if e.status == 404:
            logger.info("ℹ️ banned_users.json ещё не создан — банов пока нет")
        else:
            logger.exception(f"❌ Ошибка при загрузке banned_users.json: {e}")
        return set()
    except Exception as e:
        logger.exception(f"❌ Ошибка при загрузке банов: {e}")
        return set()


def save_banned_users(banned_users: set) -> None:
    """Сохраняет список забаненных user_id на GitHub, чтобы баны переживали
    перезапуск процесса (как и остальные данные бота)."""
    try:
        repo = _get_repo()
        payload = {"banned": sorted(banned_users)}
        content = json.dumps(payload, ensure_ascii=False, indent=2)

        try:
            existing = repo.get_contents(BANS_FILE_PATH)
            repo.update_file(BANS_FILE_PATH, "Update banned_users.json", content, existing.sha)
        except GithubException as e:
            if e.status == 404:
                repo.create_file(BANS_FILE_PATH, "Create banned_users.json", content)
            else:
                raise

    except Exception as e:
        logger.exception(f"❌ Ошибка при сохранении банов: {e}")
