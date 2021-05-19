FROM python:3.7
ADD ./src /root/proxyserver
WORKDIR /root/proxyserver
RUN pip install w3lib aiohttp -i https://pypi.douban.com/simple/
CMD ["python" "server.py"]