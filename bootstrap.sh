#!/usr/bin/env bash
# One-time setup. Run once after `az login`. Safe to re-run. See README.md.
set -euo pipefail

REPO="${REPO:?set REPO=owner/name of your GitHub repository}"
RG="${RG:-rg-spending-checkup}"
LOCATION="${LOCATION:-eastus}"
APP_NAME="${APP_NAME:-github-spending-checkup}"

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
STATE_ACCOUNT="${STATE_ACCOUNT:-tfspend$(echo -n "$SUBSCRIPTION_ID" | sha1sum | head -c 10)}"

echo "==> Registering resource providers"
for ns in Microsoft.Web Microsoft.Storage Microsoft.Insights Microsoft.OperationalInsights \
          Microsoft.AlertsManagement Microsoft.Consumption; do
  az provider register --namespace "$ns" --wait -o none
done

echo "==> Resource group $RG"
az group create --name "$RG" --location "$LOCATION" -o none
RG_ID=$(az group show --name "$RG" --query id -o tsv)

echo "==> Terraform state storage $STATE_ACCOUNT"
if ! az storage account show --name "$STATE_ACCOUNT" --resource-group "$RG" -o none 2>/dev/null; then
  az storage account create --name "$STATE_ACCOUNT" --resource-group "$RG" --location "$LOCATION" \
    --sku Standard_LRS --min-tls-version TLS1_2 --allow-blob-public-access false \
    --allow-shared-key-access false -o none
fi
STATE_ID=$(az storage account show --name "$STATE_ACCOUNT" --resource-group "$RG" --query id -o tsv)
az rest --method put --url "https://management.azure.com${STATE_ID}/blobServices/default/containers/tfstate?api-version=2023-05-01" \
  --body '{}' -o none

echo "==> GitHub deploy identity $APP_NAME"
CLIENT_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
fi
SP_ID=$(az ad sp show --id "$CLIENT_ID" --query id -o tsv 2>/dev/null || az ad sp create --id "$CLIENT_ID" --query id -o tsv)

# Newer repos put numeric IDs in the token subject (repo:owner@123/name@456), so ask GitHub.
SUB_PREFIX=$(gh api "repos/$REPO/actions/oidc/customization/sub" -q .sub_claim_prefix 2>/dev/null || echo "repo:$REPO")
for env in plan production; do
  params="{
    \"name\": \"github-${env}\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"${SUB_PREFIX}:environment:${env}\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"
  if az ad app federated-credential show --id "$CLIENT_ID" --federated-credential-id "github-${env}" -o none 2>/dev/null; then
    az ad app federated-credential update --id "$CLIENT_ID" --federated-credential-id "github-${env}" --parameters "$params" -o none
  else
    az ad app federated-credential create --id "$CLIENT_ID" --parameters "$params" -o none
  fi
done

echo "==> Role assignments (resource group only)"
assign() {
  for attempt in 1 2 3 4 5; do
    az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
      --role "$1" --scope "$2" -o none 2>/dev/null && return
    echo "    waiting for the service principal to replicate ($attempt/5)..."
    sleep 10
  done
  echo "ERROR: could not assign $1" >&2
  exit 1
}
assign "Contributor" "$RG_ID"
assign "Role Based Access Control Administrator" "$RG_ID"
assign "Storage Blob Data Contributor" "$STATE_ID"

cat <<VARS

Done. In GitHub create two environments, "plan" and "production" (add yourself
as a required reviewer on "production"), then add these repository variables:

  AZURE_CLIENT_ID        $CLIENT_ID
  AZURE_TENANT_ID        $TENANT_ID
  AZURE_SUBSCRIPTION_ID  $SUBSCRIPTION_ID
  AZURE_RESOURCE_GROUP   $RG
  TF_STATE_ACCOUNT       $STATE_ACCOUNT

and one repository secret (Secrets tab, so it is masked in logs):

  ALERT_EMAIL            <your email>
VARS
