#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
RUNTIME_DIR="${ZKDEMO_RUNTIME_DIR:-${PROJECT_DIR}/.zookeeper}"
CONFIG_DIR="${RUNTIME_DIR}/conf"
DATA_DIR="${RUNTIME_DIR}/data"
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

mkdir -p "${CONFIG_DIR}" "${DATA_DIR}" "${LOG_DIR}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
    cat >"${CONFIG_FILE}" <<EOF
tickTime=2000
initLimit=10
syncLimit=5
dataDir=${DATA_DIR}
clientPort=2181
maxClientCnxns=60
admin.enableServer=false
standaloneEnabled=true
EOF
fi

ZK_SERVER=$(find_zk_server)
export ZOOCFGDIR="${CONFIG_DIR}"
export ZOO_LOG_DIR="${LOG_DIR}"

echo "Starting standalone ZooKeeper with data in ${DATA_DIR}"
"${ZK_SERVER}" start
