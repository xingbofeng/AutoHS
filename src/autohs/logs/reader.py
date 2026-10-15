"""Tail a Hearthstone log. A missing file is reported and not created."""

import os
import time

from autohs.constants import LOG_CONTAINER_ERROR, LOG_CONTAINER_INFO
from autohs.infrastructure.logging import logger
from autohs.logs.events import LogInfoContainer


def log_iter_func(path, file_name, parse_func):
    if not os.path.exists(path):
        logger.error(f"未找到{file_name}, 路径为: {path}")
        yield LogInfoContainer(LOG_CONTAINER_ERROR)
        return

    if os.path.isdir(path):
        subdirs = [entry for entry in os.listdir(path) if os.path.isdir(os.path.join(path, entry))]
        if not subdirs:
            logger.error(f"未找到{file_name}的会话目录, 路径为: {path}")
            yield LogInfoContainer(LOG_CONTAINER_ERROR)
            return
        path = os.path.join(path, max(subdirs), file_name)
        if not os.path.exists(path):
            logger.warning(f"最新文件夹下不存在{file_name}, 路径为: {path}")
            yield LogInfoContainer(LOG_CONTAINER_ERROR)
            return

    logger.info(f"开始读取{file_name}, 路径为: {path}")
    with open(path, "r", encoding="utf8") as handle:
        while True:
            empty_line_count = 0
            log_info_container = LogInfoContainer(LOG_CONTAINER_INFO)
            while True:
                line = handle.readline()
                if line == "":
                    time.sleep(0.2)
                    empty_line_count += 1
                    if empty_line_count == 2:
                        break
                else:
                    empty_line_count = 0
                    line_container = parse_func(line)
                    if line_container is not None:
                        log_info_container.append_info(line_container)
            yield log_info_container
            if not os.path.exists(path):
                logger.error(f"{file_name}意外失踪, 预期路径为: {path}")
                yield LogInfoContainer(LOG_CONTAINER_ERROR)
                return
