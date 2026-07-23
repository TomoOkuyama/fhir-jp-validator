#!/usr/bin/env bash
# MHLW masterB (傷病名) + masterZ (修飾語) を単一 FHIR NPM package (.tgz) にパッケージ化。
#
# 前提: scripts/build-mhlw-receipt-masters.py で CS JSON 群を生成済み
#
# Output:
#   tx-server-build/mhlw-receipt-src/fhir-jp-validator.mhlw-receipt-masters-5.18.1.tgz
#
# Usage:
#   ./scripts/build-mhlw-receipt-package.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$REPO_ROOT/tx-server-build/mhlw-receipt-src"

PKG_NAME="fhir-jp-validator.mhlw-receipt-masters"
PKG_VERSION="5.18.1"
PKG_STAGE="$SRC_DIR/pkg-stage"
PKG_TGZ="$SRC_DIR/${PKG_NAME}-${PKG_VERSION}.tgz"

for f in "$SRC_DIR/CodeSystem-mhlw-masterB-disease.json" "$SRC_DIR/CodeSystem-mhlw-masterZ-modifier.json"; do
  [ -f "$f" ] || { echo "ERROR: $f not found. Run build-mhlw-receipt-masters.py first" >&2; exit 1; }
done

echo "=== 1. Clean stage ==="
rm -rf "$PKG_STAGE"; mkdir -p "$PKG_STAGE/package"

echo "=== 2. Copy CodeSystems ==="
cp "$SRC_DIR/CodeSystem-mhlw-masterB-disease.json" "$PKG_STAGE/package/"
cp "$SRC_DIR/CodeSystem-mhlw-masterZ-modifier.json" "$PKG_STAGE/package/"

echo "=== 3. package.json ==="
cat > "$PKG_STAGE/package/package.json" <<EOF
{
  "name": "$PKG_NAME",
  "version": "$PKG_VERSION",
  "tools-version": 3,
  "type": "IG",
  "date": "$(date +%Y%m%d%H%M%S)",
  "license": "CC0-1.0",
  "canonical": "http://jpfhir.jp/fhir/core/mhlw",
  "notForPublication": true,
  "title": "MHLW Receipt Masters Full (fhir-jp-validator supplement)",
  "description": "レセプト電算処理システム 傷病名マスター (27,684 concept) + 修飾語マスター (2,390 concept) の完全版を FHIR CodeSystem 化。jpfhir-terminology 2.2606.0 の fragment CS を override。Source: 社会保険診療報酬支払基金 (PDL 1.0)。",
  "fhirVersions": ["4.0.1"],
  "dependencies": {"hl7.fhir.r4.core": "4.0.1"}
}
EOF

echo "=== 4. .index.json ==="
python3 - "$PKG_STAGE/package" <<'PY'
import json, sys, os
pkg_dir = sys.argv[1]
files = []
for fn in sorted(os.listdir(pkg_dir)):
    if not fn.endswith('.json') or fn in ('.index.json', 'package.json'):
        continue
    with open(os.path.join(pkg_dir, fn)) as f:
        r = json.load(f)
    e = {'filename': fn, 'resourceType': r.get('resourceType',''), 'id': r.get('id',''),
         'url': r.get('url',''), 'version': r.get('version','')}
    if r.get('resourceType') == 'CodeSystem':
        e['content'] = r.get('content','')
    files.append(e)
json.dump({'index-version': 2, 'files': files},
          open(os.path.join(pkg_dir, '.index.json'), 'w'), ensure_ascii=False, indent=2)
print(f'  wrote .index.json with {len(files)} entries')
PY

echo "=== 5. tarball ==="
tar -czf "$PKG_TGZ" -C "$PKG_STAGE" package
echo "  → $PKG_TGZ ($(du -h "$PKG_TGZ" | cut -f1))"
