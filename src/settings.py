# -*- coding:utf-8 -*-


import configparser

config = configparser.ConfigParser()
config.read("config.ini")

PROXY_URL = config["PROXY"]["url"]

PORT = config["SERVER"]["port"]


LOGGING_LEVEL = config["LOGGING"]["level"]

if __name__ == "__main__":
    print(config["PROXY"]["url"])

    print(config["SERVER"]["port"])