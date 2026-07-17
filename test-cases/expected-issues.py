"""期待 error パターンレジストリ

test-cases/**/*.ndjson の meta.tag に付与する slug をキーに、期待される
OperationOutcome.issue.details.text の正規表現パターン (日/英いずれか) を
定義する。scripts/reconcile-test-cases.py がこの辞書を参照して、期待通り
検出されているかを判定する。

新しい slug を追加するときは:
1. ここに `<slug>: {desc, pattern}` を追加
2. 対応する test-case NDJSON の meta.tag に
   `{system: EXPECTED_ISSUE_SYSTEM, code: <slug>}` を追加

pattern はケースインセンシティブ、re.search で判定 (部分一致)。
日/英どちらの locale でも通るように `.*` で繋いだり `(A|B)` で分岐可。
"""

import re

EXPECTED_ISSUE_SYSTEM = "http://fhir-jp-validator.test/expected-issue"

EXPECTED_ISSUES = {
    # --- FHIR base ---
    "dom-6-narrative": {
        "desc": "Best Practice: narrative missing (dom-6)",
        "pattern": r"dom-6.*narrative",
    },
    "cardinality-min-missing": {
        "desc": "必須要素 min=1 に対して 0 (element name は個別 case による)",
        "pattern": r"最小必要値\s*=\s*1|minimum required\s*=\s*1",
    },
    "invalid-date-format": {
        "desc": "date/dateTime のフォーマット違反",
        "pattern": r"(is not a valid|正しい.*形式.*ありません|有効な日付ではありません|not a valid|invalid.*date)",
    },
    "reference-not-resolvable": {
        "desc": "リソース内から参照する Reference が解決不能",
        "pattern": r"could not (be resolved|find)|解決.*できません|Unable to resolve",
    },
    "invalid-code-enum": {
        "desc": "enum 値以外の code (例: Observation.status に不正値)",
        "pattern": r"(値は|is not|is illegal|not.*valid).*(でなければ|must be)|is not in the (value set|enumeration)|ValueSet.*に含まれていません|is not in the ValueSet|not.*in.*value.*set",
    },

    # --- Terminology ---
    "unknown-codesystem": {
        "desc": "CodeSystem URI が未登録",
        "pattern": r"(未知です|is unknown|not.*supported|no.*definition.*could).*(CodeSystem|システム)|CodeSystem.*(is unknown|未知)",
    },
    "unknown-code-in-codesystem": {
        "desc": "既知 CodeSystem 内に存在しない code",
        "pattern": r"Unknown code|未知のコード",
    },
    "wrong-codesystem-for-slice": {
        "desc": "slice が要求する CodeSystem と異なる system が使われた",
        "pattern": r"値は.*ですが.*でなければなりません|must be from",
    },

    # --- JP Core / JP-CLINS profile 固有 ---
    "jp-condition-identifier-missing": {
        "desc": "JP_Condition_eCS: identifier 必須欠落",
        "pattern": r"Condition\.identifier.*最小必要値.*1|Condition\.identifier.*minimum required.*1",
    },
    "jp-condition-slice-resource-identifier-missing": {
        "desc": "JP_Condition_eCS: identifier:resourceIdentifier slice min=1 欠落",
        "pattern": r"Condition\.identifier:resourceIdentifier.*minimum required.*1",
    },
    "jp-condition-lastupdated-missing": {
        "desc": "JP_Condition_eCS: meta.lastUpdated 必須欠落",
        "pattern": r"Condition\.meta\.lastUpdated.*最小必要値.*1|Condition\.meta\.lastUpdated.*minimum required.*1",
    },
    "jp-obs-lab-identifier-missing": {
        "desc": "JP_Observation_LabResult_eCS: identifier 必須欠落",
        "pattern": r"Observation\.identifier.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-obs-lab-specimen-missing": {
        "desc": "JP_Observation_LabResult_eCS: specimen 必須欠落",
        "pattern": r"Observation\.specimen.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-obs-category-max-exceeded": {
        "desc": "JP_Observation_LabResult_eCS: category:laboratory.coding max=1 超過",
        "pattern": r"Observation\.category:laboratory\.coding.*最大許容値.*1|Observation\.category:laboratory\.coding.*maximum.*1",
    },
    "jp-medadmin-quantity-code-missing": {
        "desc": "JP_MedicationAdministration_eCS: dosage.dose.Quantity.code 欠落",
        "pattern": r"Quantity\.code.*(最小必要値.*1|minimum required.*1)",
    },

    # --- Extension ---
    "unknown-extension-url": {
        "desc": "定義されていない extension URL",
        "pattern": r"(extension|拡張).*(未知|unknown|not.*defined|is not (allowed|permitted))|extension.*URL.*未定義",
    },
    "extension-not-allowed-here": {
        "desc": "定義済 extension だが profile が禁止している位置",
        "pattern": r"extension.*(ここでは許可されていません|is not allowed here|最大許容値.*=\s*0|maximum.*=\s*0)",
    },

    # --- BP profile (自動適用) ---
    "bp-component-missing": {
        "desc": "LOINC 85354-9 を持つ Observation で bp profile 必須 component が欠落",
        "pattern": r"Observation\.component.*(最小必要値.*2|minimum required.*2)|component:SystolicBP|component:DiastolicBP",
    },
}


def slug_exists(slug: str) -> bool:
    return slug in EXPECTED_ISSUES


def pattern_for(slug: str):
    entry = EXPECTED_ISSUES.get(slug)
    if not entry:
        return None
    return re.compile(entry["pattern"], re.IGNORECASE)
