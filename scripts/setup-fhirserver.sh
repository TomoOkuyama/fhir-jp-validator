#!/usr/bin/env bash
# fhirserver Docker image をビルドするセットアップスクリプト
#
# 手順:
#   1. HealthIntersections/fhirserver を clone (tx-server-build/fhirserver/)
#   2. patches/*.patch を適用 (LOINC/SNOMED import CLI + SNOMED DateSeparator fix)
#   3. docker buildx で amd64 image (iris4h-ai/fhirserver:local) を build
#
# 前提: Docker Desktop (Apple Silicon なら Rosetta 2 有効化推奨、build 5-8 分)
# 未有効化時は QEMU fallback で 25-30 分かかる
#
# Usage:
#   ./scripts/setup-fhirserver.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FHIRSERVER_DIR="$REPO_ROOT/tx-server-build/fhirserver"
FHIRSERVER_UPSTREAM="https://github.com/HealthIntersections/fhirserver.git"
FHIRSERVER_TAG="${FHIRSERVER_TAG:-v4.0.7}"
IMAGE_TAG="${IMAGE_TAG:-iris4h-ai/fhirserver:local}"

echo "=== 1/3: fhirserver source clone ==="
if [ -d "$FHIRSERVER_DIR/.git" ]; then
  echo "既に $FHIRSERVER_DIR に clone 済み、pull はしません (patch 破損防止)"
else
  git clone --depth 1 --branch "$FHIRSERVER_TAG" "$FHIRSERVER_UPSTREAM" "$FHIRSERVER_DIR"
fi

echo ""
echo "=== 2/3: patches 適用 ==="
cd "$FHIRSERVER_DIR"
for patch in "$REPO_ROOT/patches"/*.patch; do
  [ -f "$patch" ] || continue
  if git apply --check "$patch" 2>/dev/null; then
    echo "適用: $patch"
    git apply "$patch"
  elif git apply --reverse --check "$patch" 2>/dev/null; then
    echo "適用済 (skip): $patch"
  else
    echo "ERROR: patch 適用不能、既存差分と conflict? $patch" >&2
    exit 1
  fi
done

echo ""
echo "=== 3/3: Docker image build ==="
cd "$REPO_ROOT"
docker buildx build --platform linux/amd64 -t "$IMAGE_TAG" "$FHIRSERVER_DIR" 2>&1 | tail -20

echo ""
echo "=== build 完了 ==="
docker images | grep fhirserver | head -3
echo ""
echo "次に: docker compose up -d fhirserver"
