#! /bin/sh

docker run -it --rm -v $(pwd):$(pwd) -w $(pwd) -e GOPROXY=https://goproxy.cn,direct golang:latest bash -c "go build ."