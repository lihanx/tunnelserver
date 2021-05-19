# -*- coding:utf-8 -*-

import signal
import asyncio
from asyncio.streams import StreamReader, StreamReaderProtocol, _DEFAULT_LIMIT

from parser import HTTPHeaderParser
from pool import ProxyPool
from log import getLogger
import settings


class ProxyServer(object):

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.proxy_pool = ProxyPool(loop=self.loop)
        self.logger = getLogger(self.__class__.__name__)
        self._srv = None
        self.srv_task = None
        self.install_handler()

    async def monodirectionalTransport(self, reader, writer):
        while not reader.at_eof() and not writer.is_closing():
            try:
                chunk = await reader.read(1<<16)
            except Exception as e:
                self.logger.error(e)
                break
            else:
                writer.write(chunk)
                try:
                    await writer.drain()
                except Exception as e:
                    self.logger.error(e)
                    await asyncio.sleep(0.01)
        self.logger.debug("monodirectionalTransport Exit")
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
        self.logger.debug(b"-".join((host, str(port).encode("latin-1"), username, password)))
        header_parser.update_proxy_auth(username, password)
        try:
            pr, pw = await asyncio.open_connection(host=host, port=port)
        except Exception as e:
            self.logger.error(e)
            self.logger.info(b" ".join((start_line.strip(), host, b"Failed")).decode("latin-1"))
        else:
            self.logger.debug(header_parser.authed_message)
            pw.write(header_parser.authed_message)
            try:
                await pw.drain()
            except Exception as e:
                self.logger.info(b" ".join((start_line.strip(), host, b"Failed")).decode("latin-1"))
                self.logger.error(e)
            else:
                await self.bidirectionalTransport((reader, writer), (pr, pw))
                self.logger.info(b" ".join((start_line.strip(), host, b"Success")).decode("latin-1"))

    async def start_serve(self, host, port):
        # self._srv = await asyncio.start_server(
        #     self.handler, host, port
        # )
        def factory():
            reader = StreamReader(limit=_DEFAULT_LIMIT, loop=self.loop)
            protocol = StreamReaderProtocol(reader, self.handler, loop=self.loop)
            return protocol

        self._srv = await self.loop.create_server(factory, host, port)
        self.loop.create_task(self._srv)
        # self.logger.info(f"Listening on {host}:{port}")
        # await self._srv.start_serving()
        # self.logger.info(f"Server Closing")
        # await self._srv.wait_closed()
        # self.logger.info("Server Closed")

    def run(self, host="0.0.0.0", port=8001):
        self._running = True
        self.srv_task = self.loop.create_task(self.start_serve(host, port))
        self.srv_task.add_done_callback(lambda _: self.loop.stop())
        try:
            self.loop.run_forever()
        except Exception as e:
            self.logger.error(e)
        finally:
            self.loop.close()
            self.logger.info("Loop Stopped")

    def install_handler(self):
        self.loop.add_signal_handler(signal.SIGINT, self.graceful_shutdown)

    def graceful_shutdown(self):
        self._srv.close()
        self.proxy_pool.close()
        pending = asyncio.all_tasks()
        print(len(pending), pending)
        self.logger.info("Graceful Shutdown..")
        self.loop.remove_signal_handler(signal.SIGINT)
        self.loop.add_signal_handler(signal.SIGINT, self.force_shutdown)

    def force_shutdown(self):
        self.srv_task.cancel()
        self.logger.info("Force Shutdown..")
        pending = asyncio.all_tasks()
        print(len(pending), pending)
        self.loop.stop()


if __name__ == "__main__":
    srv = ProxyServer()
    srv.run("0.0.0.0", 18001)