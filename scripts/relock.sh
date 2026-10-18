#!/usr/bin/env bash
# Rebuild the hashed lock files: runtime (for deployment) and dev (tests, ruff, mypy, pip-audit).
# Run after any change to requirements.txt or requirements-dev.txt, including Dependabot PRs.
# CI checks that the lock files are fresh. An existing lock is used as a preference so versions do not drift.
set -euo pipefail
cd "$(dirname "$0")/.."
uv pip compile requirements.txt -o requirements.lock --generate-hashes --python-version 3.13 --no-header -q
uv pip compile requirements-dev.txt -c requirements.lock -o requirements-dev.lock --generate-hashes --python-version 3.13 --no-header -q
echo "requirements.lock: $(grep -c '^[A-Za-z0-9_.-]*==' requirements.lock) packages; requirements-dev.lock: $(grep -c '^[A-Za-z0-9_.-]*==' requirements-dev.lock)"
