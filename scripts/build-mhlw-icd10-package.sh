#!/usr/bin/env bash
# MHLW ICD-10 2013 完全版を FHIR NPM package (.tgz) にパッケージ化して
# fhirserver に load 可能な形式で配布する。
#
# 前提: scripts/build-mhlw-icd10-full.py で CodeSystem JSON を生成済み
#
# Output:
#   tx-server-build/mhlw-icd10-src/fhir-jp-validator.mhlw-icd10-2013-full-1.1.1.tgz
#     - fhirserver `packages.ini` に追加 load できる standard FHIR NPM package
#
# Usage:
#   ./scripts/build-mhlw-icd10-package.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$REPO_ROOT/tx-server-build/mhlw-icd10-src"
CS_JSON="$SRC_DIR/CodeSystem-mhlw-icd10-2013-full.json"

PKG_NAME="fhir-jp-validator.mhlw-icd10-2013-full"
PKG_VERSION="1.1.2"
PKG_STAGE="$SRC_DIR/pkg-stage"
PKG_TGZ="$SRC_DIR/${PKG_NAME}-${PKG_VERSION}.tgz"

if [ ! -f "$CS_JSON" ]; then
  echo "ERROR: $CS_JSON not found. Run scripts/build-mhlw-icd10-full.py first" >&2
  exit 1
fi

echo "=== 1. Cleaning package stage ==="
rm -rf "$PKG_STAGE"
mkdir -p "$PKG_STAGE/package"

echo "=== 2. Copying CodeSystem into package/ ==="
cp "$CS_JSON" "$PKG_STAGE/package/CodeSystem-mhlw-icd10-2013-full.json"

echo "=== 3. Generating package.json ==="
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
  "title": "MHLW ICD-10 2013 Full (fhir-jp-validator supplement)",
  "description": "厚労省 疾病分類 (2013 年基本分類表) 15,586 concept 完全版。jpfhir-terminology の fragment CS を override するために fhir-jp-validator で追加 load される目的の standalone package。Source: 厚労省統計情報 (PDL 1.0)。",
  "fhirVersions": ["4.0.1"],
  "dependencies": {
    "hl7.fhir.r4.core": "4.0.1"
  }
}
EOF

echo "=== 4. Generating .index.json ==="
python3 - "$PKG_STAGE/package" <<'PY'
import json, sys, os
pkg_dir = sys.argv[1]
files = []
for fn in sorted(os.listdir(pkg_dir)):
    if not fn.endswith('.json') or fn == '.index.json' or fn == 'package.json':
        continue
    with open(os.path.join(pkg_dir, fn)) as f:
        r = json.load(f)
    entry = {
        'filename': fn,
        'resourceType': r.get('resourceType', ''),
        'id': r.get('id', ''),
        'url': r.get('url', ''),
        'version': r.get('version', ''),
    }
    if r.get('resourceType') == 'CodeSystem':
        entry['content'] = r.get('content', '')
    files.append(entry)
index = {'index-version': 2, 'files': files}
with open(os.path.join(pkg_dir, '.index.json'), 'w') as f:
    json.dump(index, f, ensure_ascii=False, indent=2)
print(f'  wrote .index.json with {len(files)} entries')
PY

echo "=== 5. Creating tarball ==="
tar -czf "$PKG_TGZ" -C "$PKG_STAGE" package
echo "  → $PKG_TGZ ($(du -h "$PKG_TGZ" | cut -f1))"

echo ""
echo "=== NEXT STEPS ==="
echo "1. Copy package into terminology dir:"
echo "   PKG_DIR=tx-server-build/terminology/fhir-server/${PKG_NAME}#${PKG_VERSION}"
echo "   mkdir -p \"\$PKG_DIR\""
echo "   tar -xzf $PKG_TGZ -C \"\$PKG_DIR\" --strip-components=1"
echo ""
echo "2. Restart fhirserver + HAPI cluster to pick up new CodeSystem"
echo "3. Verify: curl 'http://localhost:8181/r4/CodeSystem/\$validate-code?url=http://jpfhir.jp/fhir/core/mhlw/CodeSystem/ICD10-2013-full&code=S67.2'"
