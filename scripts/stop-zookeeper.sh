#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
RUNTIME_DIR="${ZKDEMO_RUNTIME_DIR:-${PROJECT_DIR}/.zookeeper}"
CONFIG_DIR="${RUNTIME_DIR}/conf"
LOG_DIR="${RUNTIME_DIR}/logs"
CONFIG_FILE="${CONFIG_DIR}/zoo.cfg"

find_zk_server() {
    if [[ -n "${ZOOKEEPER_HOME:-}" ]]; then
        local server="${ZOOKEEPER_HOME}/bin/zkServer.sh"
        if [[ ! -x "${server}" ]]; then
            echo "ZOOKEEPER_HOME does not contain executable bin/zkServer.sh" >&2
            return 1
        fi
        printf '%s\n' "${server}"
        return
    fi

    local command_name
    for command_name in zkServer zkServer.sh; do
        if command -v "${command_name}" >/dev/null 2>&1; then
            command -v "${command_name}"
            return
        fi
    done

    echo "ZooKeeper not found; set ZOOKEEPER_HOME or add zkServer to PATH" >&2
    return 1
}

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "No local ZooKeeper configuration found at ${CONFIG_FILE}" >&2
    exit 1
fi

ZK_SERVER=$(find_zk_server)
export ZOOCFGDIR="${CONFIG_DIR}"
export ZOO_LOG_DIR="${LOG_DIR}"

echo "Stopping standalone ZooKeeper"
"${ZK_SERVER}" stop
