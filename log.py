"""
Searcharr
Sonarr & Radarr Telegram Bot
Log Helper
By Todd Roberts
https://github.com/toddrob99/searcharr
"""
import logging
import os


def set_up_logger(logger_name, verbose, console):
    if verbose:
        rootLogger = logging.getLogger()
        rootLogger.setLevel(logging.DEBUG)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)8s - %(name)s(%(thread)s):%(lineno)d - %(message)s"
    )

    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    fileName = f"{logger_name}.log"
    logPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "logs")
    if not os.path.exists(logPath):
        os.makedirs(logPath)
    fh = logging.handlers.TimedRotatingFileHandler(
        os.path.join(logPath, fileName), when="midnight", interval=1, backupCount=7
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
