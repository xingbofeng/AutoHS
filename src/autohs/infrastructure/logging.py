import sys

import loguru

from autohs.paths.root import repo_root

_logger_initialized = False
logger = loguru.logger


def custom_format(record):
    time = record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    level = record["level"].name
    file_name = "main" if record["name"] == "__main__" else record["name"]
    function_name = "__main__" if record["function"] == "<module>" else record["function"]
    file_function_line = file_name + ".py:" + str(record["line"]) + "(" + function_name + ")"
    return f"<green>{time}</green> | <level>{level:<7}</level> | <cyan>{file_function_line:<52}</cyan>" + "- <level>{message}</level>\n"


def logger_init(level="INFO"):
    global _logger_initialized

    if _logger_initialized and logger.level == level:
        logger.debug("日志记录器不会被重复初始化")
        return
    elif _logger_initialized:
        logger.info(f"更新日志记录器的日志级别: {level}")

    log_folder = repo_root() / "autohs_log"
    log_folder.mkdir(exist_ok=True)

    logger.remove()
    logger.add(log_folder / "file_{time}.log", retention=20, level=level, format=custom_format)
    logger.add(sys.stdout, level=level, format=custom_format)
    logger.debug("日志记录器已初始化")
    _logger_initialized = True


if __name__ == "__main__":
    logger_init()
