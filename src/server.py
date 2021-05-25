# -*- coding:utf-8 -*-

import signal
import asyncio
from asyncio.streams import StreamReader, StreamReaderProtocol, _DEFAULT_LIMIT

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from parser import HTTPHeaderParser
from pool import ProxyPool
from log import getLogger
import settings


class ProxyServer(object):

    def __init__(self):
        self.loop = uvloop.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.proxy_pool = ProxyPool(loop=self.loop)
        self.logger = getLogger(self.__class__.__name__)
        self._srv = None
        self.install_error_handler()

    async def monodirectionalTransport(self, reader, writer):
        while not reader.at_eof() and not writer.is_closing():
            try:
                chunk = await reader.read(1<<16)
            except Exception as e:
                self.logger.error(e)
                break
            else:
                writer.write(chunk)
                await writer.drain()
        # self.logger.debug("monodirectionalTransport Exit")
        writer.close()
        await writer.wait_closed()

    async def bidirectionalTransport(self, client_pair, proxy_pair):
        cr, cw = client_pair
        pr, pw = proxy_pair
        await asyncio.gather(
            self.monodirectionalTransport(cr, pw),
            self.monodirectionalTransport(pr, cw)
        )

    async def handler(self, reader, writer):
        header_parser = HTTPHeaderParser(reader)
        await header_parser.parseMessage()
        start_line = header_parser.raw_start_line
        host, port, username, password = self.proxy_pool.rand_proxy()
        header_parser.update_proxy_auth(username, password)
        try:
            pr, pw = await asyncio.open_connection(host=host, port=port)
        except Exception as e:
            self.logger.error(e)
            self.logger.info(b" ".join((start_line.strip(), host, b"Failed")).decode("latin-1"))
        else:
            pw.write(header_parser.authed_message)
            await pw.drain()
            await self.bidirectionalTransport((reader, writer), (pr, pw))
            self.logger.info(b" ".join((start_line.strip(), host, b"Success")).decode("latin-1"))

    async def start_serve(self, host, port):
        await self.proxy_pool.init_session()
        
        def factory():
            reader = StreamReader(limit=_DEFAULT_LIMIT, loop=self.loop)
            protocol = StreamReaderProtocol(reader, self.handler, loop=self.loop)
            return protocol

        return await self.loop.create_server(factory, host, port, backlog=settings.BACKLOG)

    def run(self, host="0.0.0.0", port=8001):
        srv = self.loop.run_until_complete(self.start_serve(host, port))
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            srv.close()
            self.proxy_pool.close()
            self.loop.run_until_complete(srv.wait_closed())
            self.loop.run_until_complete(self.proxy_pool.close_session())
            self.loop.run_until_complete(self.clean_up())
            self.loop.close()
            self.logger.info("Loop Stopped")

    async def clean_up(self):
        pending = asyncio.all_tasks()
        self.logger.info(f"{len(pending)} Task(s) Running")
        pending = set(filter(lambda p: p.get_coro().__name__ != "clean_up", pending))
        if not pending:
            return None
        await asyncio.gather(*pending)

    def install_error_handler(self):

        def handler(loop, context):
            self.logger.error(context.get("exception"))

        self.loop.set_exception_handler(handler)


if __name__ == "__main__":
    srv = ProxyServer()
    srv.run("0.0.0.0", settings.PORT)