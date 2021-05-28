# -*- coding:utf-8 -*-


import configparser

from w3lib.http import basic_auth_header


config = configparser.ConfigParser()
config.read("config.ini")

PROXY_URL = config["PROXY"]["url"]
UPDATE_INTERVAL = config.getint("PROXY", "interval")
PROXY_USERNAME = config["PROXY"].get("username", "")
PROXY_PASSWORD = config["PROXY"].get("password", "")
if PROXY_USERNAME and PROXY_PASSWORD:
    PROXY_AUTH = basic_auth_header(PROXY_USERNAME, PROXY_PASSWORD)
else:
    PROXY_AUTH = b""

PORT = int(config["SERVER"]["port"])
BACKLOG = int(config["SERVER"]["backlog"])


LOGGING_LEVEL = config["LOGGING"]["level"]
LOGGING_DB = config["LOGGING"]["logdb"]
BUFFER_SIZE = config.getint("LOGGING", "buffersize")