#!/usr/bin/env python3
"""
社会保険診療報酬支払基金 (SSK) レセプト電算処理システム 傷病名マスター (masterB) と
修飾語マスター (masterZ) を FHIR CodeSystem (content=complete) に変換。

Source:
  - 傷病名: https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_07.files/b_20260601.zip
    (27,684 concept)
  - 修飾語: https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_08.files/z_20260601.zip
    (2,390 concept)
  - encoding: SHIFT_JIS
  - License: 公共データ利用規約 (PDL 1.0)、出典明記条件下で再配布可

Output:
  - `tx-server-build/mhlw-receipt-src/CodeSystem-mhlw-masterB-disease.json`
  - `tx-server-build/mhlw-receipt-src/CodeSystem-mhlw-masterZ-modifier.json`

Notes:
  - masterB code = 7桁 receipt-electronic code (例: '0000999', '8848176')
  - masterZ code = 4桁 modifier code (例: '8299', '8282')
  - display は「傷病名/修飾語表記」列 (masterB col 6, masterZ col 7)
  - URI は jpfhir-terminology の fragment CS と同じ (上書き用):
    - http://jpfhir.jp/fhir/core/mhlw/CodeSystem/masterB-disease
    - http://jpfhir.jp/fhir/core/mhlw/CodeSystem/masterZ-disease-modifier

Usage:
  ./scripts/build-mhlw-receipt-masters.py
"""
from __future__ import annotations
import csv, json, sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "tx-server-build/mhlw-receipt-src"

B_SRC = SRC_DIR / "b_20260601.txt"
Z_SRC = SRC_DIR / "z_20260601.txt"

B_OUT = SRC_DIR / "CodeSystem-mhlw-masterB-disease.json"
Z_OUT = SRC_DIR / "CodeSystem-mhlw-masterZ-modifier.json"

B_URL = "http://jpfhir.jp/fhir/core/mhlw/CodeSystem/masterB-disease"
Z_URL = "http://jpfhir.jp/fhir/core/mhlw/CodeSystem/masterZ-disease-modifier"

# version bump to override jpfhir-terminology fragment (v5.18.0)
CS_VERSION = "5.18.1"

COPYRIGHT_LINES = [
    "『レセプト電算処理システム 傷病名/修飾語マスター』 (社会保険診療報酬支払基金) を加工して作成",
    "本 CodeSystem 自体の再配布は 公共データ利用規約 (PDL 1.0) に準拠。",
]


def load_ssk_csv(path: Path, code_col: int, display_col: int) -> list[dict]:
    """SSK 傷病名/修飾語 CSV (SJIS、"quoted CSV") を load して concept リストに変換。

    code_col / display_col は 0-indexed。
    """
    concepts: list[dict] = []
    seen: set[str] = set()
    dup_count = 0
    with path.open("r", encoding="shift_jis", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) <= max(code_col, display_col):
                continue
            code = row[code_col].strip()
            display = row[display_col].strip()
            if not code or not display:
                continue
            if code in seen:
                dup_count += 1
                continue
            seen.add(code)
            concepts.append({"code": code, "display": display})
    if dup_count > 0:
        print(f"  WARNING: {dup_count} duplicate code skipped in {path.name}", file=sys.stderr)
    return concepts


def build_cs(url: str, cs_id: str, name: str, title: str, description: str,
             concepts: list[dict]) -> dict:
    return {
        "resourceType": "CodeSystem",
        "id": cs_id,
        "url": url,
        "version": CS_VERSION,
        "name": name,
        "title": title,
        "status": "active",
        "experimental": False,
        "date": date.today().isoformat(),
        "publisher": "社会保険診療報酬支払基金 (data provider) / fhir-jp-validator (converter)",
        "description": description,
        "copyright": "\n".join(COPYRIGHT_LINES),
        "caseSensitive": True,
        "content": "complete",
        "count": len(concepts),
        "language": "ja",
        "concept": concepts,
    }


def main() -> None:
    for src in (B_SRC, Z_SRC):
        if not src.exists():
            print(f"ERROR: {src} not found. Download from SSK first:", file=sys.stderr)
            print(f"  b: https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_07.files/b_20260601.zip", file=sys.stderr)
            print(f"  z: https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_08.files/z_20260601.zip", file=sys.stderr)
            sys.exit(1)

    # masterB (傷病名): code = col 2 (0-index), display = col 5
    print(f"Loading {B_SRC.name}...", file=sys.stderr)
    b_concepts = load_ssk_csv(B_SRC, code_col=2, display_col=5)
    print(f"  → {len(b_concepts)} concepts", file=sys.stderr)

    b_cs = build_cs(
        url=B_URL,
        cs_id="mhlw-masterB-disease-full",
        name="MHLW_masterB_disease_full",
        title="レセプト電算用傷病名マスター (完全版)",
        description=(
            "社会保険診療報酬支払基金 提供のレセプト電算処理システム 傷病名マスター "
            f"(v20260601、{len(b_concepts)} concept 完全版) を FHIR CodeSystem 化。\n\n"
            "Source: https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_07.html\n"
            "License: 公共データ利用規約 (PDL 1.0)\n"
            "出典: 『レセプト電算処理システム 傷病名マスター』(社会保険診療報酬支払基金) を加工して作成\n\n"
            "jpfhir-terminology 2.2606.0 の fragment CS (2,000 concept) を complete で上書きする目的で "
            "fhir-jp-validator の scripts/build-mhlw-receipt-masters.py で生成。"
        ),
        concepts=b_concepts,
    )
    with B_OUT.open("w", encoding="utf-8") as f:
        json.dump(b_cs, f, ensure_ascii=False, indent=2)
    print(f"Written {B_OUT} ({B_OUT.stat().st_size / 1024 / 1024:.1f} MB)", file=sys.stderr)

    # masterZ (修飾語): code = col 2, display = col 6
    print(f"Loading {Z_SRC.name}...", file=sys.stderr)
    z_concepts = load_ssk_csv(Z_SRC, code_col=2, display_col=6)
    print(f"  → {len(z_concepts)} concepts", file=sys.stderr)

    z_cs = build_cs(
        url=Z_URL,
        cs_id="mhlw-masterZ-modifier-full",
        name="MHLW_masterZ_modifier_full",
        title="レセプト電算用修飾語マスター (完全版)",
        description=(
            "社会保険診療報酬支払基金 提供のレセプト電算処理システム 修飾語マスター "
            f"(v20260601、{len(z_concepts)} concept 完全版) を FHIR CodeSystem 化。\n\n"
            "Source: https://www.ssk.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_08.html\n"
            "License: 公共データ利用規約 (PDL 1.0)\n"
            "出典: 『レセプト電算処理システム 修飾語マスター』(社会保険診療報酬支払基金) を加工して作成"
        ),
        concepts=z_concepts,
    )
    with Z_OUT.open("w", encoding="utf-8") as f:
        json.dump(z_cs, f, ensure_ascii=False, indent=2)
    print(f"Written {Z_OUT} ({Z_OUT.stat().st_size / 1024 / 1024:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
