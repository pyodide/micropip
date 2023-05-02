#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# Adapted from: https://github.com/LordGaav/docker-devpi

function generate_password() {
    # We disable exit on error because we close the pipe
    # when we have enough characters, which results in a
    # non-zero exit status
    set +e
    tr -cd '[:alnum:]' < /dev/urandom | fold -w30 | head -n1 | tr -cd '[:alnum:]'
    set -e
}

function kill_devpi() {
    _PID=$(pgrep devpi-server)
    echo "ENTRYPOINT: Sending SIGTERM to PID $_PID"
    kill -SIGTERM "$_PID"
}

if [ "${1:-}" == "bash" ]; then
    exec "$@"
fi

DEVPI_ROOT_PASSWORD="${DEVPI_ROOT_PASSWORD:-}"
if [ -f "$DEVPI_SERVER_ROOT/.root_password" ]; then
    DEVPI_ROOT_PASSWORD=$(cat "$DEVPI_SERVER_ROOT/.root_password")
elif [ -z "$DEVPI_ROOT_PASSWORD" ]; then
    DEVPI_ROOT_PASSWORD=$(generate_password)
fi

echo "ENTRYPOINT: Starting devpi-server"
devpi-server --host 0.0.0.0 --port 3141 --offline-mode "$@" &

timeout 10 bash -c 'until printf "" 2>>/dev/null >>/dev/tcp/$0/$1; do sleep 1; done' localhost 3141

echo "ENTRYPOINT: Installing signal traps"
trap kill_devpi SIGINT SIGTERM

echo "ENTRYPOINT: Initializing devpi-server"
devpi use http://localhost:3141
devpi login root --password=''

echo "ENTRYPOINT: Setting root password to $DEVPI_ROOT_PASSWORD"
devpi user -m root "password=$DEVPI_ROOT_PASSWORD"

# Upload packages to devpi
devpi index -c dev bases=root/pypi
devpi use root/dev
devpi upload /tmp/packages/*


devpi logoff

echo "ENTRYPOINT: Watching devpi-server"
PID=$(pgrep devpi-server)

if [ -z "$PID" ]; then
    echo "ENTRYPOINT: Could not determine PID of devpi-server!"
    exit 1
fi

set +e

while : ; do
    kill -0 "$PID" > /dev/null 2>&1 || break
    sleep 2s
done

echo "ENTRYPOINT: devpi-server died, exiting..."
