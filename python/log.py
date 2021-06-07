# -*- coding:utf-8 -*-

import asyncio
import logging
import json

import redis

import settings


class RedisBufferingHandler(logging.Handler):

    def __init__(self, capacity, uri, loop=None):
        super(RedisBufferingHandler, self).__init__()
        self.capacity = capacity
        self.buffer = []
        self.url, self.key = uri.rsplit("/", 1)
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.redis_conn = redis.StrictRedis.from_url(self.url, socket_timeout=15)
        self._running_task = None

    def shouldFlush(self, record):
        return (len(self.buffer) >= self.capacity)

    def emit(self, record):
        self.buffer.append(record.getMessage())
        if self.shouldFlush(record):
            self.flush()

    async def _flush(self, buf):
        if not buf:
            return None
        await self.loop.run_in_executor(None, self.redis_conn.lpush, self.key, *buf)

    def flush(self):
        self.acquire()
        if self.loop is not None and self.loop.is_running():
            _buffer = self.buffer
            self.buffer = []
            self._running_task = self.loop.create_task(self._flush(_buffer))
        self.release()

    def close(self):
        try:
            if self.buffer:
                self.redis_conn.lpush(self.key, *self.buffer)
        except Exception:
            pass
        finally:
            super(RedisBufferingHandler, self).close()


class StatusFilter:

    def __init__(self, name):
        self.name = name

    def filter(self, record):
        if record.name == self.name \
                and record.levelno == logging.INFO:
            return True
        return False


def getLogger(name="ProxyServer", export=False):
    level = getattr(logging, settings.LOGGING_LEVEL, logging.DEBUG)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="[%(levelname)s][%(asctime)s][%(name)s][%(lineno)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch.setFormatter(formatter)
    ch.setLevel(level)
    logger.addHandler(ch)

    if export:
        bh = RedisBufferingHandler(settings.BUFFER_SIZE, settings.LOGGING_DB)
        bh.setLevel(level)
        bh.setFormatter(formatter)
        logger.addHandler(bh)
        sf = StatusFilter(name)
        bh.addFilter(sf)

    return logger