FROM python:3.8
ADD . /root/proxyserver
WORKDIR /root/proxyserver
RUN pip install w3lib aiohttp uvloop -i https://pypi.douban.com/simple/
CMD python main.py