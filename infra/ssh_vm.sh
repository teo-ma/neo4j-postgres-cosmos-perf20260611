#!/usr/bin/env bash
# Helper to SSH into the Neo4j VM with correct options (avoids zsh word-split).
# Usage: bash infra/ssh_vm.sh "remote command"
set -euo pipefail
cd "$(dirname "$0")/.."
source config.env
VM_IP=$(cat .secrets/neo4j_vm_ip)
exec ssh -i "$SSH_KEY" \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR \
  -o ConnectTimeout=15 \
  "$VM_ADMIN@$VM_IP" "$@"
