# -*- coding:utf-8 -*-

from typing import List, Tuple
from io import BytesIO
import asyncio
import random
import time
import logging

import aiohttp

import settings
from log import getLogger


class LoopingCall:

    def __init__(self, func, loop=None):
        self.func = func
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.logger = getLogger(self.__class__.__name__)
        self._task = None
        self.running = False
        self.interval = 0

    def callback(self, _):
        if self.running:
            self.loop.call_later(self.interval, self)

    def __call__(self):
        self._task = self.loop.create_task(self.func())

    def start(self, interval, now=True):
        self.running = True
        self.interval = interval
        if now:
            self.loop.call_soon(self)
        else:
            self.loop.call_later(interval, self)
        return None

    def stop(self):
        if not self.running:
            return None
        self.running = False
        if self._task is not None:
            self._task.remove_done_callback(self.callback)
            self._task.cancel()
            self.logger.debug(self._task)
            self._task = None
        self.logger.debug("Looping Call Stopped")


class ProxyPool:

    def __init__(self, loop=None):
        self.pool: List[Tuple[bytes, int, bytes, bytes]] = []
        if loop is None:
            loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(loop=loop)
        self.loop = loop
        self.priodically_update = LoopingCall(self.repopulate)
        self.priodically_update.start(30)
        self.logger = getLogger(self.__class__.__name__)

    def parse_proxy(self, content):
        for line in BytesIO(content):
            line = line.strip()
            if not line:
                continue
            _, host, port = line.split(b"\t")
            username, password = b"", b""
            if b"@" in host:
                auth, host = host.split(b"@")
                username, password = auth.split(b":")
            yield host, int(port), username, password

    async def repopulate(self):
        pool = []
        async with self.session.get(settings.PROXY_URL) as response:
            content = await response.read()
            for proxy in self.parse_proxy(content):
                pool.append(proxy)
        self.pool = pool
        self.logger.debug(f"Proxy Pool Updated. Pool Size: {len(self.pool)}")
        return self.pool

    def rand_proxy(self):
        if not self.pool:
            return (b"", 0, b"", b"")
        return random.choice(self.pool)

    def close(self):
        self.priodically_update.stop()
        self.session.close()
        self.logger.debug("ProxyPool Stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    pool = ProxyPool(loop)
    try:
        loop.run_forever()
    except Exception as e:
        logging.error(e)
    finally:
        loop.close()