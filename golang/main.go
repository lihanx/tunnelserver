package main

import (
    "log"
    "sync"
    "io"
    "net"
    "time"
    "runtime"
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
                log.Println(err)
                break FOR
            } else if err == io.EOF {
                log.Println("EOF")
                break FOR
            } else if n == 0 {
                // 完成读取
                log.Printf("%s read finished\n", id)
                src.Close()
                break FOR
            }
        }
    }
    log.Printf("%s Done\n", id)
}

func handleConnection(conn *net.TCPConn) {
    defer conn.Close()
    proxy := defaultPool.RandProxy()
    log.Printf("%s:%d\n", proxy.Host, proxy.Port)
    proxyAddr := &net.TCPAddr{
        IP:   net.ParseIP(proxy.Host),
        Port: proxy.Port,
    }
    proxyConn, err := net.DialTCP("tcp", nil, proxyAddr)
    if err != nil {
        log.Println(err.Error())
    }
    if proxyConn == nil {
        log.Println("proxyConn nil")
        return
    }
    log.Println("New Proxy Connection")
    defer proxyConn.Close()

    var wg sync.WaitGroup
    wg.Add(2)
    go bidirectionalTransport(conn, proxyConn, &wg, "forward")
    go bidirectionalTransport(proxyConn, conn, &wg, "backward")
    
    log.Println("Wait.....")
    
    wg.Wait()

    log.Printf("======== Finished: %d =========\n", runtime.NumGoroutine())
}

func main() {

    defaultPool = NewProxyPool("http://192.168.132.81/kuaidaili_proxy.txt")
    go defaultPool.Start(15)

    tcpAddr := &net.TCPAddr{
        IP:   net.ParseIP("0.0.0.0"),
        Port: 18002,
    }

    listener, err := net.ListenTCP("tcp", tcpAddr)
    if err != nil {
        log.Println(err.Error())
        return
    }
    defer listener.Close()
    log.Println("Listening on :18002")
    for {
        conn, err := listener.AcceptTCP()
        if err != nil {
            log.Println(err.Error())
            continue
        }
        go handleConnection(conn)
        log.Println("New Client Connection")
    }
}
