#!/usr/bin/env bash
# Deploy (or update) the cloud stack on the Azure VM made by azure_create_vm.sh.
#
#   cloud/scripts/azure_deploy.sh <vm-host>
#
# Pulls this repository on the VM, copies cloud/.env over SSH with the API on
# port 80 (the passwords never pass through GitHub or Azure), starts the stack
# with Docker Compose, and runs the end-to-end smoke test on the VM. Safe to
# re-run after pushing changes.
set -euo pipefail

host="${1:?usage: $0 <vm-host>}"
repo_url="https://github.com/TristanListanco/rt-spark-activity-recognition.git"
cloud_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ssh_opts=(-i "$HOME/.ssh/rtspark_azure" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
remote="azureuser@$host"

[ -f "$cloud_dir/.env" ] || { echo "cloud/.env not found (copy cloud/.env.example and set passwords)" >&2; exit 1; }

echo "==> Waiting for first-boot setup (cloud-init) on $host"
ssh "${ssh_opts[@]}" "$remote" 'cloud-init status --wait >/dev/null; docker --version'

echo "==> Fetching the repository on the VM"
# $repo_url is filled in here before the command is sent; that's intended.
# shellcheck disable=SC2029
ssh "${ssh_opts[@]}" "$remote" "
  set -e
  if [ -d rt-spark-activity-recognition/.git ]; then
    git -C rt-spark-activity-recognition pull -q --ff-only
  else
    git clone -q $repo_url
  fi
  git -C rt-spark-activity-recognition log -1 --format='   at commit %h %s'"

echo "==> Copying cloud/.env (API on port 80)"
sed -E 's/^API_PORT=.*/API_PORT=80/' "$cloud_dir/.env" \
  | ssh "${ssh_opts[@]}" "$remote" 'umask 077; cat > rt-spark-activity-recognition/cloud/.env'

echo "==> Starting the stack and running the smoke test on the VM"
ssh "${ssh_opts[@]}" "$remote" 'cd rt-spark-activity-recognition && sg docker -c "cloud/scripts/smoke_test.sh"'

echo
echo "Deployed. MQTT broker: $host:1883   API: http://$host/api/health"
