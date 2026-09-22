#!/usr/bin/env bash
set -euo pipefail
repo=ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent
gh workflow run build-test.yml --repo "$repo" --ref main
printf '\nBuild requested. Follow the run at:\nhttps://github.com/%s/actions/workflows/build-test.yml\n' "$repo"
