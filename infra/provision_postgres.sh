#!/usr/bin/env bash
# Provision Azure Database for PostgreSQL Flexible Server.
set -euo pipefail
cd "$(dirname "$0")/.."
source config.env

# Generate and persist an admin password
if [ ! -f .secrets/pg_password ]; then
  openssl rand -base64 18 | tr -d '/+=' | cut -c1-20 > .secrets/pg_password
fi
PG_PASSWORD=$(cat .secrets/pg_password)

echo "[postgres] creating flexible server $PG_NAME ($PG_SKU)..."
az postgres flexible-server create \
  --resource-group "$RG" \
  --name "$PG_NAME" \
  --location "$LOC" \
  --tier "$PG_TIER" \
  --sku-name "$PG_SKU" \
  --storage-size "$PG_STORAGE_GB" \
  --version "$PG_VERSION" \
  --admin-user "$PG_ADMIN" \
  --admin-password "$PG_PASSWORD" \
  --public-access 0.0.0.0 \
  --yes \
  -o none

# Allow the current client IP and all Azure to connect (benchmark runs externally)
MYIP=$(curl -s https://api.ipify.org || echo "")
if [ -n "$MYIP" ]; then
  az postgres flexible-server firewall-rule create \
    --resource-group "$RG" --name "$PG_NAME" \
    --rule-name client --start-ip-address "$MYIP" --end-ip-address "$MYIP" \
    -o none
fi
az postgres flexible-server firewall-rule create \
  --resource-group "$RG" --name "$PG_NAME" \
  --rule-name allazure --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 \
  -o none || true

PG_HOST=$(az postgres flexible-server show -g "$RG" -n "$PG_NAME" --query fullyQualifiedDomainName -o tsv)
echo "$PG_HOST" > .secrets/pg_host
echo "[postgres] ready. Host: $PG_HOST"
