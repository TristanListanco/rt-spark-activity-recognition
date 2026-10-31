#!/usr/bin/env bash
# Create the Azure VM that runs the cloud stack. Run once from your computer,
# after `az login`. Then run cloud/scripts/azure_deploy.sh.
#
# What it creates (all in one resource group, so `az group delete -n rg-activity`
# removes everything):
#   - an Ubuntu 24.04 VM (B1s: 1 vCPU, 1 GB RAM), set up by cloud/deploy/cloud-init.yaml
#   - a static public IP with a DNS name: <DNS_LABEL>.<location>.cloudapp.azure.com
#   - firewall rules: SSH only from this computer's current IP; MQTT (1883) and
#     HTTP (80) from anywhere, because the board and the phone can be on any network
#
# Settings (environment variables, all optional):
#   LOCATION   Azure region (default: southeastasia; student subscriptions may only
#              allow some regions; the error lists them)
#   SIZE       VM size (default: Standard_B1s)
#   DNS_LABEL  DNS name prefix (default: rtspark-activity-<random>)
set -euo pipefail

RG="${RG:-rg-activity}"
VM="${VM:-activity-vm}"
LOCATION="${LOCATION:-southeastasia}"
SIZE="${SIZE:-Standard_B1s}"
DNS_LABEL="${DNS_LABEL:-rtspark-activity-$(openssl rand -hex 3)}"
KEY="$HOME/.ssh/rtspark_azure"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$KEY" ]; then
  echo "==> Creating SSH key $KEY"
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  ssh-keygen -q -t ed25519 -N "" -C "rtspark-azure" -f "$KEY"
fi
my_ip="$(curl -fsS https://api.ipify.org)"

echo "==> Resource group $RG in $LOCATION"
az group create -n "$RG" -l "$LOCATION" -o none

echo "==> VM $VM ($SIZE, Ubuntu 24.04), DNS label $DNS_LABEL"
az vm create -g "$RG" -n "$VM" -l "$LOCATION" \
  --image Ubuntu2404 --size "$SIZE" --os-disk-size-gb 30 \
  --admin-username azureuser --ssh-key-values "$KEY.pub" \
  --public-ip-sku Standard --public-ip-address-allocation static \
  --public-ip-address-dns-name "$DNS_LABEL" \
  --nsg-rule NONE --custom-data "$here/../deploy/cloud-init.yaml" -o none

nsg="${VM}NSG"
echo "==> Firewall: SSH from $my_ip only; MQTT 1883 and HTTP 80 from anywhere"
az network nsg rule create -g "$RG" --nsg-name "$nsg" -n ssh-from-my-ip --priority 100 \
  --access Allow --protocol Tcp --direction Inbound --destination-port-ranges 22 \
  --source-address-prefixes "$my_ip/32" -o none
az network nsg rule create -g "$RG" --nsg-name "$nsg" -n mqtt --priority 110 \
  --access Allow --protocol Tcp --direction Inbound --destination-port-ranges 1883 -o none
az network nsg rule create -g "$RG" --nsg-name "$nsg" -n http --priority 120 \
  --access Allow --protocol Tcp --direction Inbound --destination-port-ranges 80 -o none

fqdn="$(az network public-ip show -g "$RG" -n "${VM}PublicIP" --query dnsSettings.fqdn -o tsv)"
ip="$(az network public-ip show -g "$RG" -n "${VM}PublicIP" --query ipAddress -o tsv)"
echo
echo "VM ready: $fqdn ($ip)"
echo "Next: cloud/scripts/azure_deploy.sh $fqdn"
