package main

import (
    "sync"
    "io"
    "net"
    "fmt"
    "time"
    "runtime"

    log "github.com/sirupsen/logrus"
)

func bidirectionalTransport(src, dst *net.TCPConn, wg *sync.WaitGroup, id string) {
    defer wg.Done()
FOR:
    for {
        select {
        case <- time.After(5*time.Second):
            break FOR
        default:
            if n, err := io.Copy(src, dst); err != nil {
                // 对端关闭
                log.Debug(err)
                break FOR
            } else if err == io.EOF {
                log.Debug("EOF")
                break FOR
            } else if n == 0 {
                // 完成读取
                log.Debug("%s read finished\n", id)
                src.Close()
                break FOR
            }
        }
    }
    log.Debug("%s Done\n", id)
}

func handleConnection(conn *net.TCPConn) {
    defer conn.Close()
    proxy := defaultPool.RandProxy()
    if proxy == nil {
        return
    }
    fields := log.Fields{
        "spider": conn.RemoteAddr().String(),
        "proxy": fmt.Sprintf("%s:%d", proxy.Host, proxy.Port),
    }
    log.Debug("%s:%d\n", proxy.Host, proxy.Port)
    proxyAddr := &net.TCPAddr{
        IP:   net.ParseIP(proxy.Host),
        Port: proxy.Port,
    }
    proxyConn, err := net.DialTCP("tcp", nil, proxyAddr)
    if err != nil {
        log.WithFields(fields).Info("Failed")
        log.Debug(err.Error())
    }
    if proxyConn == nil {
        log.Debug("proxyConn nil")
        log.WithFields(fields).Info("Failed")
        return
    }
    log.Debug("New Proxy Connection")
    defer proxyConn.Close()

    var wg sync.WaitGroup
    wg.Add(2)
    go bidirectionalTransport(conn, proxyConn, &wg, "forward")
    go bidirectionalTransport(proxyConn, conn, &wg, "backward")
    log.Debug("Wait.....")
    wg.Wait()
    log.WithFields(fields).Info("Success")
    log.Debug("======== Finished: %d =========\n", runtime.NumGoroutine())
}

func main() {

    InitLogger()

    defaultPool = NewProxyPool("http://192.168.132.81/kuaidaili_proxy.txt")
    go defaultPool.Start(15)

    tcpAddr := &net.TCPAddr{
        IP:   net.ParseIP("0.0.0.0"),
        Port: 18002,
    }

    listener, err := net.ListenTCP("tcp", tcpAddr)
    if err != nil {
        log.Debug(err.Error())
        return
    }
    defer listener.Close()
    log.Info("Listening on :18002")
    for {
        conn, err := listener.AcceptTCP()
        if err != nil {
            log.Error(err.Error())
            continue
        }
        go handleConnection(conn)
        log.Debug("New Client Connection")
    }
}
