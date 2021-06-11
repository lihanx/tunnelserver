package main


import (
    "github.com/sirupsen/logrus"
	log "github.com/rogierlommers/logrus-redis-hook"
)


func Init() {
	hookConfig := logredis.HookConfig{
		Host:     "192.168.182.212",
		Key:      "proxy_log",
		Format:   "v1",
		App:      "tunnel-proxy",
		Port:     6379,
		Hostname: "test", // will be sent to field @source_host
		DB:       0, // optional
		TTL:      3600,
	}

	hook, err := logredis.NewHook(hookConfig)
	if err == nil {
		log.AddHook(hook)
	} else {
		log.Errorf("logredis error: %q", err)
	}
	log.SetLevel(log.InfoLevel)
}
