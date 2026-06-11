#!/usr/bin/env bash
# Delete ALL resources created for this benchmark (the whole resource group).
set -euo pipefail
cd "$(dirname "$0")/.."
source config.env
echo "Deleting resource group $RG (this removes the VM, PostgreSQL and Cosmos DB)..."
az group delete -n "$RG" --yes --no-wait
echo "Deletion started (running in background)."
