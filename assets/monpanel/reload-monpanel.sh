#!/usr/bin/env bash
# monpanel 证书热重载（acme.sh renew 的 reloadcmd 调用；cron 环境无 DBUS，需补环境变量）
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
exec systemctl --user restart monpanel.service
