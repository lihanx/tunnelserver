package main

import (
    "fmt"
    "strconv"
    "bufio"
    "io"
    "io/ioutil"
    "bytes"
    "strings"
    "math/rand"
    "net/http"
    "time"
)

type Proxy struct {
    Host     string
    Port     int
    Username string
    Password string
}

type ProxyPool struct {
    Client   *http.Client
    Pool     []*Proxy
    Size     int
    Interval int
    URL      string
    exit     chan bool
}

var defaultPool *ProxyPool

func NewProxyPool(URL string) *ProxyPool {
    p := new(ProxyPool)
    p.Pool = make([]*Proxy, 0)
    p.URL = URL
    p.Client = http.DefaultClient
    p.exit = make(chan bool)
    return p
}

func (p *ProxyPool) Start(interval int) {
    p.Repopulate()
    ticker := time.Tick(15 * time.Second)
    // defer close(ticker)
    for {
        select {
        case <-p.exit:
            break
        case <-ticker:
            p.Repopulate()
        }
    }
}

func (p *ProxyPool) Repopulate() {
    response, err := p.Client.Get(p.URL)
    if err != nil {
        return
    }
    defer response.Body.Close()
    body, err := ioutil.ReadAll(response.Body)
    if err != nil {
        return
    }
    reader := bufio.NewReader(bytes.NewReader(body))
    p.Pool = p.Pool[:0]
    p.Size = 0
    for {
        line, err := reader.ReadString(byte('\n'))
        if err == io.EOF {
            break
        } else if err != nil {
            fmt.Println(err)
            break
        }
        if line == "\n" {
            break
        }
        parsedLine := strings.Split(line, "\t")
        proxy := parsedLine[1]
        port, err := strconv.Atoi(strings.TrimRight(parsedLine[2], "\n"))
        if err != nil {
            fmt.Println(err)
            continue
        }
        if strings.Contains(proxy, "@") {
            parsedProxy := strings.Split(proxy, "@")
            up := strings.Split(parsedProxy[0], ":")
            if err != nil {
                continue
            }
            proxyInfo := &Proxy{
                Host:     parsedProxy[1],
                Port:     port,
                Username: up[0],
                Password: up[1],
            }
            p.Pool = append(p.Pool, proxyInfo)
        } else {
            proxyInfo := &Proxy{
                Host: proxy,
                Port: port,
            }
            p.Pool = append(p.Pool, proxyInfo)
        }
        p.Size++
    }
    fmt.Println("Repopulate")
    // fmt.Printf("%+v %d", p.Pool, p.Size)
}

func (p *ProxyPool) RandProxy() *Proxy {
    if p.Size == 0 {
        return nil
    }
    return p.Pool[rand.Intn(p.Size-1)]
}

func (p *ProxyPool) Stop() {
    p.exit <- true
    close(p.exit)
}