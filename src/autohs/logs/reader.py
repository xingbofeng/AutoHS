"""Tail a Hearthstone log. A missing file is reported and not created."""

import os
import time

from autohs.constants import LOG_CONTAINER_ERROR, LOG_CONTAINER_INFO
from autohs.infrastructure.logging import logger
from autohs.logs.events import LogInfoContainer


def _log_path(path, file_name):
    if os.path.isdir(path):
        subdirs = [entry for entry in os.listdir(path) if os.path.isdir(os.path.join(path, entry))]
        return os.path.join(path, max(subdirs), file_name) if subdirs else None
    return path


def log_iter_func(path, file_name, parse_func, start_at_end=False):
    # Capture the restart boundary now, before a lazy first read can skip a
    # new match created while the FSM activates the window and starts matching.
    boundary = None
    initial_path = _log_path(path, file_name)
    if start_at_end and initial_path and os.path.isfile(initial_path):
        stat = os.stat(initial_path)
        boundary = (stat.st_dev, stat.st_ino, stat.st_size)
    return _tail_log(path, file_name, parse_func, boundary)


def _tail_log(source_path, file_name, parse_func, boundary):
    handle = None
    current_path = None
    identity = None
    try:
        while True:
            path = _log_path(source_path, file_name)
            if not path or not os.path.isfile(path):
                if handle is not None:
                    handle.close()
                    handle = None
                logger.warning(f"等待{file_name}生成, 路径为: {source_path}")
                yield LogInfoContainer(LOG_CONTAINER_ERROR)
                time.sleep(0.2)
                continue
            stat = os.stat(path)
            if handle is None or path != current_path or (stat.st_dev, stat.st_ino) != identity \
                    or stat.st_size < handle.tell():
                if handle is not None:
                    handle.close()
                handle = open(path, "r", encoding="utf8")
                current_path = path
                identity = (stat.st_dev, stat.st_ino)
                if boundary and identity == boundary[:2] and stat.st_size >= boundary[2]:
                    handle.seek(boundary[2])
                boundary = None
                logger.info(f"开始读取{file_name}, 路径为: {path}")
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
    finally:
        if handle is not None:
            handle.close()
