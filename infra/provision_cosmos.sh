#!/usr/bin/env bash
# Provision Azure Cosmos DB with the Gremlin (graph) API.
set -euo pipefail
cd "$(dirname "$0")/.."
source config.env

echo "[cosmos] creating Gremlin account $COSMOS_NAME..."
az cosmosdb create \
  --resource-group "$RG" \
  --name "$COSMOS_NAME" \
  --locations regionName="$LOC" failoverPriority=0 isZoneRedundant=False \
  --capabilities EnableGremlin \
  --default-consistency-level Session \
  -o none

echo "[cosmos] creating database $COSMOS_DB..."
az cosmosdb gremlin database create \
  --resource-group "$RG" \
  --account-name "$COSMOS_NAME" \
  --name "$COSMOS_DB" \
  -o none

echo "[cosmos] creating graph $COSMOS_GRAPH (throughput $COSMOS_THROUGHPUT RU/s)..."
az cosmosdb gremlin graph create \
  --resource-group "$RG" \
  --account-name "$COSMOS_NAME" \
  --database-name "$COSMOS_DB" \
  --name "$COSMOS_GRAPH" \
  --partition-key-path "$COSMOS_PARTITION_KEY" \
  --throughput "$COSMOS_THROUGHPUT" \
  -o none

COSMOS_HOST="${COSMOS_NAME}.gremlin.cosmos.azure.com"
COSMOS_KEY=$(az cosmosdb keys list -g "$RG" -n "$COSMOS_NAME" --query primaryMasterKey -o tsv)
echo "$COSMOS_HOST" > .secrets/cosmos_host
echo "$COSMOS_KEY" > .secrets/cosmos_key
echo "[cosmos] ready. Host: $COSMOS_HOST"
