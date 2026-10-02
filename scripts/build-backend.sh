#!/usr/bin/env bash
set -euo pipefail
repo=ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent
workflow=api-deploy.yml
case "${1:-api}" in
  api)
    if [[ $# != 2 || ! "$2" =~ ^[0-9a-f]{40}$ ]]; then
      echo 'Usage: bash scripts/build-backend.sh api <final-tested-main-SHA>' >&2
      exit 64
    fi
    gh workflow run "$workflow" --repo "$repo" --ref main -f "release_sha=$2"
    ;;
  lab)
    if [[ $# != 1 ]]; then exit 64; fi
    workflow=build-test.yml
    gh workflow run "$workflow" --repo "$repo" --ref main
    ;;
  *) echo 'Usage: bash scripts/build-backend.sh api <final-tested-main-SHA> | lab' >&2; exit 64 ;;
esac
printf '\nBuild requested. Follow the run at:\nhttps://github.com/%s/actions/workflows/%s\n' "$repo" "$workflow"
