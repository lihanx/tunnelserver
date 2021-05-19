# -*- coding:utf-8 -*-

import sys
import time
import asyncio
import logging
import random
from io import BytesIO
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__file__)

from w3lib.http import basic_auth_header
import httptools
import aiohttp

"""
ProxyServer 功能点

- [ ] 定时更新代理池(background task)
- [ ] 根据配置文件选项选择代理, 使用镜像启动时, 可以指定 settings.conf
- [ ] 代理异常信息返回
"""


class HTTPRequestHeaders(dict):
        
    def on_header(self, name, value):
        self[name] = value


class HTTPResponseHeaders(dict):
        
    def on_header(self, name, value):
        self[name] = value


UPDATE_TIME = 0
proxies = []


async def get_proxy():
    global UPDATE_TIME
    global proxies
    if int(time.time()) - UPDATE_TIME > 30:
        proxies = []
        async with aiohttp.ClientSession() as session:
            async with session.get("http://192.168.132.81/kuaidaili_proxy.txt") as response:
                content = await response.read()
                for line in BytesIO(content):
                    line = line.strip()
                    if not line:
                        continue
                    _, host, port = line.split(b"\t")
                    _, host = host.split(b"@")
                    proxies.append((host, int(port)))
                UPDATE_TIME = int(time.time())
                logger.debug("UPDATED")
    return random.choice(proxies)


class ProxyServer:
    
    async def readStartLine(self, reader):
        start_line = await reader.readline()


    async def readHeader(self, reader):
        header_lines = []
        while 1:
            try:
                line = await reader.readline()
            except Exception as e:
                logger.error(e)
                break
            else:
                header_lines.append(line)
                if line == b"\r\n":
                    break
        return header_lines[0], b"".join(header_lines)
    
    async def monodirectionalStream(self, src, dst, event, flag):
        while not src.at_eof():
            try:
                chunk = await src.read(1<<20)
            except Exception as e:
                logger.error(e)
                break
            else:
                dst.write(chunk)
                try:
                    await dst.drain()
                except Exception as e:
                    logger.error(e)
        logger.debug(f"{flag} coroutine exit".center(40, "="))
        dst.close()

    async def bidirectionalStream(self, src_pair, proxy_pair):

        client_r, client_w = src_pair
        proxy_r, proxy_w = proxy_pair

        event = asyncio.Event()
        await asyncio.gather(
            self.monodirectionalStream(client_r, proxy_w, event, "up"),
            self.monodirectionalStream(proxy_r, client_w, event, "down")
        )
        # dst.close()

    async def readBody(self, reader, content_length, chunk_size=1<<10):
        body_chunks = []
        received = 0
        while content_length - received >= chunk_size:
            chunk = await reader.read(chunk_size)
            body_chunks.append(chunk)
            received += chunk_size
        if received < content_length:
            chunk = await reader.read(content_length-received)
            body_chunks.append(chunk)
        return b"".join(body_chunks)
    
    
    async def handler(self, reader, writer):
        line1, req_header = await self.readHeader(reader)
        
        # logger.debug(req_header)
        req_headers = HTTPRequestHeaders()
        body = None

        if not line1.startswith(b"CONNECT"):
            req_parser = httptools.HttpRequestParser(req_headers)
            req_parser.feed_data(req_header)
            
            content_length = req_headers.get(b"Content-Length")
            if content_length is not None:
                body = await self.readBody(reader, int(content_length))
        logger.debug(line1)
        host, port = await get_proxy()
    
        try:
            r, w = await asyncio.open_connection(host=host, port=int(port))
        except Exception as e:
            logger.error(e)
            logger.info(b" ".join((line1.strip(), host, b"Failed")).decode("latin-1"))
        else:
            req_headers[b"Proxy-Authorization"] = basic_auth_header('lihanx', 'ht2h1mx9', encoding="latin-1")
            
            req_header = line1 \
                    + b"".join(b"%s: %s\r\n" % (k, v) for k, v in req_headers.items()) \
                    + b"\r\n"
            
            # logger.debug(req_header)
            w.write(req_header)
            await w.drain()

            await self.bidirectionalStream((reader, writer), (r, w))
            logger.info(b" ".join((line1.strip(), host, b"Success")).decode("latin-1"))
            # w.close()
        writer.close()
    
    
    async def main(self, host, port):
        srv = await asyncio.start_server(
            self.handler, host, port
        )
        await srv.serve_forever()
    
server = ProxyServer()
asyncio.run(server.main("0.0.0.0", 18001))

