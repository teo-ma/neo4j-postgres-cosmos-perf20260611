#!/usr/bin/env bash
# Provision the Neo4j Community VM with an attached Premium SSD data disk.
set -euo pipefail
cd "$(dirname "$0")/.."
source config.env

echo "[neo4j-vm] creating VM $VM_NAME ($VM_SIZE)..."
az vm create \
  --resource-group "$RG" \
  --name "$VM_NAME" \
  --image "$VM_IMAGE" \
  --size "$VM_SIZE" \
  --admin-username "$VM_ADMIN" \
  --ssh-key-values "${SSH_KEY}.pub" \
  --os-disk-size-gb 64 \
  --storage-sku Premium_LRS \
  --custom-data infra/neo4j-cloud-init.yaml \
  --public-ip-sku Standard \
  --nsg-rule SSH \
  -o none

echo "[neo4j-vm] attaching $VM_DATA_DISK_GB GB Premium SSD data disk..."
az vm disk attach \
  --resource-group "$RG" \
  --vm-name "$VM_NAME" \
  --name "${VM_NAME}-data" \
  --new \
  --size-gb "$VM_DATA_DISK_GB" \
  --sku Premium_LRS \
  -o none

PIP=$(az vm show -d -g "$RG" -n "$VM_NAME" --query publicIps -o tsv)
echo "$PIP" > .secrets/neo4j_vm_ip
echo "[neo4j-vm] VM ready. Public IP: $PIP"
