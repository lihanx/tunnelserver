# -*- coding:utf-8 -*-

import logging

from w3lib.http import basic_auth_header

from log import getLogger
import settings

class HTTPHeaderParser:
    """用于解析通过 TCP 层读取的 HTTP 原始报文"""
    def __init__(self, reader):
        self.reader = reader
        self.raw_start_line = b""
        self.raw_header = b""
        self.logger = getLogger(self.__class__.__name__)

    async def readStartLine(self):
        """读取 HTTP 首行原始报文"""
        self.raw_start_line = await self.reader.readline()
        # self.logger.debug(self.raw_start_line)
        return self.raw_start_line
    
    async def readHeader(self):
        """读取 HTTP Header 原始报文"""
        if self.raw_start_line.startswith(b"CONNECT"):
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
        return self.raw_header

    async def parseMessage(self):
        """按固定顺序读取 HTTP 报文原始数据流"""
        await self.readStartLine()
        await self.readHeader()

    def update_proxy_auth(self):
        """向 Header 中添加第三方代理认证信息"""
        if settings.PROXY_AUTH:
            auth_info = b"Proxy-Authorization: %s\r\n" % settings.PROXY_AUTH
            self.raw_header += auth_info
        return None

    @property
    def authed_message(self):
        """获取添加认证信息后的请求报文"""
        return self.raw_start_line + self.raw_header + b"\r\n"