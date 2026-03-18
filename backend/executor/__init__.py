from functools import lru_cache

from backend.executor.base import AbstractExecutor


@lru_cache(maxsize=1)
def get_executor() -> AbstractExecutor:
    from backend.config import get_settings
    settings = get_settings()
    if settings.task_executor == "celery":
        from backend.executor.celery_exec import CeleryExecutor
        return CeleryExecutor()
    from backend.executor.local import LocalExecutor
    return LocalExecutor()
