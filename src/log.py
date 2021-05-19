# -*- coding:utf-8 -*-

import logging

import settings


def getLogger(name="ProxyServer"):
    level = getattr(logging, settings.LOGGING_LEVEL, logging.DEBUG)

    logging.basicConfig(
        level=level,
        format="[%(levelname)s][%(asctime)s][%(name)s][%(lineno)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(name)
    return logger