# -*- coding:utf-8 -*-

from server import ProxyServer
import settings

if __name__ == "__main__":
    srv = ProxyServer()
    srv.run("0.0.0.0", settings.PORT)