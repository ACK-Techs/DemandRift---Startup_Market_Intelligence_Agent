#!/usr/bin/env bash
set -euo pipefail
repo=ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent
workflow=api-deploy.yml
case "${1:-api}" in
  api) ;;
  lab) workflow=build-test.yml ;;
  *) echo 'Usage: bash scripts/build-backend.sh [api|lab]' >&2; exit 64 ;;
esac
gh workflow run "$workflow" --repo "$repo" --ref main
printf '\nBuild requested. Follow the run at:\nhttps://github.com/%s/actions/workflows/%s\n' "$repo" "$workflow"
