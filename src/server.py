# -*- coding:utf-8 -*-

import signal
from concurrent.futures import ThreadPoolExecutor
import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from asyncio.streams import (StreamReader, 
                             StreamReaderProtocol, 
                             _DEFAULT_LIMIT)

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from parser import HTTPHeaderParser
from pool import ProxyPool
from log import getLogger
import settings


class ProxyServer(object):

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        thread_pool = ThreadPoolExecutor(max_workers=5)
        self.loop.set_default_executor(thread_pool)
        self.proxy_pool = ProxyPool(loop=self.loop)
        self.logger = getLogger(self.__class__.__name__, export=False)
        # self.install_error_handler()

    async def monodirectionalTransport(self, reader, writer):
        """单向数据传输"""
        while not reader.at_eof() and not writer.is_closing():
            chunk = await reader.read(1<<16)
            if chunk == b'':
                break
            await self.loop.run_in_executor(None, writer.write, chunk)
            await writer.drain()

    async def bidirectionalTransport(self, client_pair, proxy_pair):
        """由一对单向传输任务组成双工读写传输"""
        cr, cw = client_pair
        pr, pw = proxy_pair
        await asyncio.wait(
            [self.monodirectionalTransport(cr, pw),
            self.monodirectionalTransport(pr, cw)],
            # timeout=120
        )
        self.logger.debug("bindirectional transport finished")

    async def handler(self, reader, writer):
        """请求处理 Handler"""
        header_parser = HTTPHeaderParser(reader)
        await header_parser.parseMessage()
        start_line = header_parser.raw_start_line
        host, port = self.proxy_pool.rand_proxy()
        header_parser.update_proxy_auth()
        try:
            proxy_conn = await self.proxy_pool.open_connection(host, port)
        except Exception as e:
            self.logger.error(e)
            self.logger.info(
                " ".join((
                    start_line.decode("latin-1").strip(), 
                    host + ":" + str(port), 
                    "Failed"
                ))
            )
        else:
            proxy_conn.writer.write(header_parser.authed_message)
            await proxy_conn.writer.drain()
            await self.bidirectionalTransport(
                (reader, writer), 
                (proxy_conn.reader, proxy_conn.writer)
            )
            self.logger.info(
                " ".join((
                    start_line.decode("latin-1").strip(), 
                    host + ":" + str(port), 
                    "Success"
                ))
            )
            proxy_conn.release()
        del header_parser
        writer.close()
        # await writer.wait_closed()
        self.logger.debug("reader -> writer closed")

    async def start_serve(self, host, port):
        """创建服务实例"""
        def factory():
            reader = StreamReader(limit=_DEFAULT_LIMIT, loop=self.loop)
            protocol = StreamReaderProtocol(reader, self.handler, loop=self.loop)
            return protocol

        return await self.loop.create_server(factory, host, port, backlog=settings.BACKLOG)

    def run(self, host="0.0.0.0", port=8001):
        """启动服务，监听指定端口
        停止时清理环境，平滑退出"""
        srv = self.loop.run_until_complete(self.start_serve(host, port))
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            srv.close()
            self.proxy_pool.close()
            self.loop.run_until_complete(self.proxy_pool.close_connections())
            self.loop.run_until_complete(srv.wait_closed())
            self.loop.run_until_complete(self.clean_up())
            self.loop.run_until_complete(asyncio.sleep(0.25))
            self.loop.close()
            self.logger.debug("Loop Stopped")

    async def clean_up(self):
        """清理未完成的任务"""
        pending = asyncio.all_tasks()
        self.logger.debug(f"{len(pending)} Task(s) Running")
        pending = set(filter(lambda p: p.get_coro().__name__ != "clean_up", pending))
        if not pending:
            return None
        await asyncio.gather(*pending)

    def install_error_handler(self):
        """异常处理 handler"""
        def handler(loop, context):
            self.logger.error(context.get("exception", context))

        self.loop.set_exception_handler(handler)


if __name__ == "__main__":
    srv = ProxyServer()
    srv.run("0.0.0.0", settings.PORT)