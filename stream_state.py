import json
import logging
import os

from github import Github, GithubException

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
STREAM_STATE_FILE_PATH = os.getenv("STREAM_STATE_FILE_PATH", "stream_state.json")

_repo = None


def _get_repo():
    global _repo
    if _repo is None:
        gh = Github(GITHUB_TOKEN)
        _repo = gh.get_repo(GITHUB_REPO)
    return _repo


def load_stream_state() -> bool:
    """Возвращает True, если стрим был отмечен как идущий (is_live) на момент
    последнего сохранения. По умолчанию False — бот не должен падать из-за этого."""
    try:
        repo = _get_repo()
        contents = repo.get_contents(STREAM_STATE_FILE_PATH)
        data = json.loads(contents.decoded_content.decode("utf-8"))
        return bool(data.get("is_live", False))
    except GithubException as e:
        if e.status == 404:
            logger.info("ℹ️ stream_state.json ещё не создан — считаем, что стрим не идёт")
        else:
            logger.exception(f"❌ Ошибка при загрузке stream_state.json: {e}")
        return False
    except Exception as e:
        logger.exception(f"❌ Ошибка при загрузке состояния стрима: {e}")
        return False


def save_stream_state(is_live: bool) -> None:
    """Сохраняет флаг is_live на GitHub, чтобы состояние 'стрим идёт' переживало
    перезапуск процесса (Render перезапускает бота при простое)."""
    try:
        repo = _get_repo()
        payload = {"is_live": is_live}
        content = json.dumps(payload, ensure_ascii=False, indent=2)

        try:
            existing = repo.get_contents(STREAM_STATE_FILE_PATH)
            repo.update_file(STREAM_STATE_FILE_PATH, "Update stream_state.json", content, existing.sha)
        except GithubException as e:
            if e.status == 404:
                repo.create_file(STREAM_STATE_FILE_PATH, "Create stream_state.json", content)
            else:
                raise

    except Exception as e:
        logger.exception(f"❌ Ошибка при сохранении состояния стрима: {e}")

