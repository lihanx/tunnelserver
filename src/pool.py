# -*- coding:utf-8 -*-

from typing import List, Tuple
from io import BytesIO
import asyncio
import random
import time
import logging

import redis

import settings
from log import getLogger


class LoopingCall:
    """通过定时创建 Task 并自回调的方式实现周期任务"""

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
        """回调函数"""
        if self.running:
            self.loop.call_later(self.interval, self)

    def __call__(self):
        self._task = self.loop.create_task(self.func())
        self._task.add_done_callback(self.callback)

    def start(self, interval, now=True):
        """开始定时任务"""
        self.running = True
        self.interval = interval
        if now:
            self.loop.call_soon(self)
        else:
            self.loop.call_later(interval, self)
        return None

    def stop(self):
        """终止定时任务"""
        if not self.running:
            return None
        self.running = False
        if self._task is not None:
            self._task.remove_done_callback(self.callback)
            self._task.cancel()
            self._task = None
        self.logger.debug("Looping Call Stopped")


class ProxyPool:
    """in-memory 代理池"""

    def __init__(self, loop=None):
        self.pool: List[Tuple[str, int]] = None
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.priodically_update = LoopingCall(self.repopulate)
        self.priodically_update.start(settings.UPDATE_INTERVAL)
        self.logger = getLogger(self.__class__.__name__)
        self.url, self.key = settings.PROXY_URL.rsplit("/", 1)
        self.redis_conn = redis.StrictRedis.from_url(self.url, socket_timeout=10, decode_responses=True)
        
    def _get_new_pool(self):
        """获取新代理池"""
        pool = []
        for proxy, score in self.redis_conn.zscan_iter(self.key):
            proxy = proxy.rsplit("@", 1)[-1]
            host, port = proxy.split(":")
            pool.append((host, int(port)))
        return pool

    async def repopulate(self):
        """更新代理池"""
        self.pool = await self.loop.run_in_executor(None, self._get_new_pool)
        self.logger.debug(f"Proxy Pool Updated. Pool Size: {len(self.pool)}")
        return None

    def rand_proxy(self):
        """随机获取代理"""
        if not self.pool:
            return ("", 0)
        return random.choice(self.pool)

    def close(self):
        """关闭代理池，停止周期任务"""
        self.priodically_update.stop()
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