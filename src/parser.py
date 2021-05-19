# -*- coding:utf-8 -*-

import logging

from w3lib.http import basic_auth_header

from log import getLogger


class HTTPHeaderParser:

    def __init__(self, reader):
        self.reader = reader
        self.raw_start_line = b""
        self.raw_header = b""
        self.logger = getLogger(self.__class__.__name__)

    async def readStartLine(self):
        self.raw_start_line = await self.reader.readline()
        self.logger.debug(self.raw_start_line)
        return self.raw_start_line
    
    async def readHeader(self):
        if self.raw_start_line.startswith(b"CONNECT"):
            self.logger.debug(self.raw_header)
            return self.raw_header
        header_lines = []
        while 1:
            try:
                line = await self.reader.readline()
            except Exception as e:
                logging.error(e)
            else:
                if line == b"\r\n":
                    break
                header_lines.append(line)
        self.raw_header = b"".join(header_lines)
        self.logger.debug(self.raw_header)
        return self.raw_header

    async def parseMessage(self):
        await self.readStartLine()
        await self.readHeader()

    def update_proxy_auth(self, username, password):
        if username and password:
            auth_info = b"Proxy-Authorization: %s\r\n" % basic_auth_header(username.decode(), password.decode(), encoding="latin-1")
            self.raw_header += auth_info
        return None

    @property
    def authed_message(self):
        return self.raw_start_line + self.raw_header + b"\r\n"