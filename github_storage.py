import os
import json
import logging
from github import Github
from github.GithubException import GithubException

logger = logging.getLogger(__name__)

class GitHubStorage:
    def __init__(self, github_token, repo_name):
        """
        Инициализация GitHub storage
        
        Args:
            github_token: GitHub Personal Access Token
            repo_name: Имя репозитория в формате "username/repo"
        """
        self.github = Github(github_token)
        
        # ИСПРАВЛЕННОЕ: Правильно парсим username/repo
        try:
            # Получаем репозиторий через github.get_repo("username/repo")
            self.repo = self.github.get_repo(repo_name)
            self.repo_name = repo_name
            logger.info(f"✅ Подключился к репозиторию {repo_name}")
        except GithubException as e:
            if e.status == 404:
                raise RuntimeError(f"❌ Репозиторий '{repo_name}' не найден. Проверь GITHUB_REPO переменную.")
            elif e.status == 401:
                raise RuntimeError(f"❌ Ошибка аутентификации. Проверь GITHUB_TOKEN.")
            else:
                raise RuntimeError(f"❌ Ошибка GitHub: {e}")
        
    def load_file(self, filename, default_value):
        """
        Загрузить JSON файл из GitHub
        
        Args:
            filename: Имя файла (например "all_users.json")
            default_value: Значение по умолчанию если файл не найден
            
        Returns:
            Данные из файла или default_value
        """
        try:
            contents = self.repo.get_contents(filename)
            data = json.loads(contents.decoded_content.decode('utf-8'))
            logger.info(f"✅ Загружено {filename} из GitHub")
            return data
        except GithubException as e:
            if e.status == 404:
                logger.info(f"⚠️ {filename} не найден на GitHub. Используем значение по умолчанию.")
                return default_value
            else:
                logger.error(f"❌ Ошибка при загрузке {filename}: {e}")
                return default_value
        except Exception as e:
            logger.error(f"❌ Ошибка при парсинге {filename}: {e}")
            return default_value

    def save_file(self, filename, data):
        """
        Сохранить JSON файл на GitHub
        
        Args:
            filename: Имя файла
            data: Данные для сохранения
        """
        try:
            content = json.dumps(data, indent=2, ensure_ascii=False)
            
            try:
                # Пытаемся получить существующий файл
                contents = self.repo.get_contents(filename)
                # Если существует, обновляем
                self.repo.update_file(
                    path=filename,
                    message=f"Update {filename}",
                    content=content,
                    sha=contents.sha
                )
                logger.info(f"✅ {filename} обновлён на GitHub")
            except GithubException as e:
                if e.status == 404:
                    # Если файла нет, создаём новый
                    self.repo.create_file(
                        path=filename,
                        message=f"Create {filename}",
                        content=content
                    )
                    logger.info(f"✅ {filename} создан на GitHub")
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении {filename}: {e}")

    def load_users(self):
        """Загрузить список пользователей"""
        users_list = self.load_file("all_users.json", [])
        return set(users_list)

    def save_users(self, users_set):
        """Сохранить список пользователей"""
        self.save_file("all_users.json", list(users_set))

    def load_stats(self):
        """Загрузить статистику пользователей"""
        return self.load_file("user_stats.json", {})

    def save_stats(self, stats_dict):
        """Сохранить статистику пользователей"""
        self.save_file("user_stats.json", stats_dict)

    def load_subscribers(self):
        """Загрузить список подписчиков"""
        subscribers_list = self.load_file("subscribers.json", [])
        return set(subscribers_list)

    def save_subscribers(self, subscribers_set):
        """Сохранить список подписчиков"""
        self.save_file("subscribers.json", list(subscribers_set))

    def load_wishlists(self):
        """Загрузить вишлисты пользователей"""
        return self.load_file("wishlists.json", {})

    def save_wishlists(self, wishlists_dict):
        """Сохранить вишлисты пользователей"""
        self.save_file("wishlists.json", wishlists_dict)
