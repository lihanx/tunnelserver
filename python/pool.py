# -*- coding:utf-8 -*-

from typing import List, Tuple, Mapping
from io import BytesIO
import asyncio
import random
import time
import logging
from collections import defaultdict

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



class Connection:

    def __init__(self, host, port, reader, writer):
        self.host = host
        self.port = port
        self.ip = f"{host}:{port}"
        self.reader = reader
        self.writer = writer
        self.in_use = False
        self.verified = False

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

    def acquire(self):
        self.in_use = True

    def release(self):
        self.in_use = False


class ProxyPool:
    """in-memory 代理池"""

    def __init__(self, loop=None):
        self.pool: List[Tuple[str, int]] = None
        self.connections = defaultdict(list)
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
        expired = set(self.connections.keys()) - \
                  {f"{host}:{port}" for host, port in self.pool}

        for ip in expired:
            conns = self.connections.pop(ip, [])
            for conn in conns:
                try:
                    await conn.close()
                except Exception:
                    pass

        self.logger.debug(f"Proxy Pool Updated. Pool Size: {len(self.pool)}")
        return None

    def remove_connection(self, conn):
        self.connections[conn.ip].remove(conn)

    def rand_proxy(self):
        """随机获取代理"""
        if not self.pool:
            return ("", 0)
        return random.choice(self.pool)

    async def open_connection(self, host, port):
        """从连接池中随机获取一个代理连接"""
        ip = f"{host}:{port}"
        connection = next((
            conn for conn in self.connections[ip] 
            if not conn.in_use and not conn.writer.is_closing()
        ), None)
        if connection is None:
            self.logger.debug(f"Open New Connection {ip}")
            pr, pw = await asyncio.open_connection(host=host, port=port)
            connection = Connection(host, port, pr, pw)
            self.connections[ip].append(connection)
        elif connection.writer.is_closing():
            self.connections[ip].remove(connection)
            self.logger.debug(f"Open New Connection {ip}")
            pr, pw = await asyncio.open_connection(host=host, port=port, limit=1<<22)
            connection = Connection(host, port, pr, pw)
            self.connections[ip].append(connection)
        else:
            self.logger.debug(f"Reuse Connection {ip}")
        connection.acquire()
        return connection

    async def close_connections(self):
        """关闭所有代理连接"""
        for ip in list(self.connections.keys()):
            conns = self.connections.pop(ip, [])
            for conn in conns:
                try:
                    await conn.close()
                except Exception as e:
                    self.logger.error(e)
                else:
                    self.logger.debug(f"{ip} connection closed")


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