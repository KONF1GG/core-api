"""
Вспомогательные функции для работы приложения.

Содержит утилиты для работы с файловой системой и очистки временных данных.
"""

import os
from pathlib import Path
from logger_config import get_logger

logger = get_logger(__name__)


def cleanup_temp_dir(temp_dir: Path) -> None:
    """
    Очищает временную директорию от старых файлов.

    Args:
        temp_dir: Путь к временной директории

    Note:
        Удаляет только файлы с паттерном 'temp_users_*.json'
    """
    try:
        files_removed = 0
        for file in temp_dir.glob("temp_users_*.json"):
            try:
                os.remove(file)
                files_removed += 1
            except OSError as e:
                logger.warning("Failed to remove temp file %s: %s", file, e)

        if files_removed > 0:
            logger.info("Removed %d temporary files from %s", files_removed, temp_dir)
        else:
            logger.debug("No temporary files to remove in %s", temp_dir)

    except Exception as e:
        logger.error("Error during temp directory cleanup: %s", e)
