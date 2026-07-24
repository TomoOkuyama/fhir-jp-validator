"""期待 error パターンレジストリ

test-cases/**/*.ndjson の meta.tag に付与する slug をキーに、期待される
OperationOutcome.issue.details.text の正規表現パターン (日/英いずれか) を
定義する。scripts/reconcile-test-cases.py がこの辞書を参照して、期待通り
検出されているかを判定する。

新しい slug を追加するときは:
1. ここに `<slug>: {desc, pattern, expected_type}` を追加
2. 対応する test-case NDJSON の meta.tag に
   `{system: EXPECTED_ISSUE_SYSTEM, code: <slug>}` を追加

pattern はケースインセンシティブ、re.search で判定 (部分一致)。
日/英どちらの locale でも通るように `.*` で繋いだり `(A|B)` で分岐可。

expected_type (省略時は "error-warning"、reconcile 側では filter しないが
docs 化・ユーザー説明用のメタ情報):
- "error-warning": Tier 1 通常、error か warning が発火することを assert
- "info-only-pass": Tier 2 の盲点記録、information のみで pass することを assert
- "positive-control": 検証機構が生きていることの前提条件 (発火することが前提)
- "record-only-not-enforced": HAPI が現状強制していないことの記録 (MustSupport
  等、フラグや将来の HAPI 版で変わる可能性)
- "record-only-spec-not-encoded": Tier 3、FHIR 制約として符号化されておらず、
  custom check を書かない限り どの validator でも永久に検出されない
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
        "pattern": r"(値は|is not|is illegal|not.*valid).*(でなければ|must be)|is not in the (value set|enumeration)|ValueSet.*に含まれていません|is not in the ValueSet|not.*in.*value.*set|codingのいずれもが.*ValueSet|none of the.*codings.*ValueSet",
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
        "desc": (
            "slice が要求する CodeSystem と異なる system or code が使われた。"
            "system が slice-fixed と一致した上で code が VS 範囲外の場合、"
            "'提供された値 (X) はValueSet Y に含まれていません' が発火する。"
            "code が CS 内で unknown なら 'system で未知のコード' が発火する。"
        ),
        "pattern": r"提供された値.*ValueSet.*(含まれ|not in the value set|not in.*ValueSet)|system.*で未知のコード|is not in the value set|Unknown code.*in.*CodeSystem",
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

    # --- 追加: display 誤り / example URL ---
    "loinc-display-mismatch": {
        "desc": "LOINC code の display が正規名と異なる (Wrong Display Name)",
        "pattern": r"Wrong Display Name|不正な表示名|表示名.*正しくない",
    },
    "example-codesystem-url-not-allowed": {
        "desc": "http://example.org/ で始まる Example URL は許可されていない",
        "pattern": r"Example URL\s?は許可されていません|Example URLs are not permitted|example\.org.*not (allowed|permitted)",
    },

    # --- 追加: Reference 型不一致 ---
    "reference-type-mismatch": {
        "desc": "Reference が期待される型と異なる (例: Reference(Patient) に Practitioner)",
        "pattern": r"invalid.*Reference|Reference.*must be of type|参照.*(型|タイプ).*(不一致|invalid)|タイプ\s*'\w+'\s*は.*有効なターゲットではありません|is not a valid target|not (a valid|allowed as) target",
    },

    # --- 追加: JP_Condition_eCS 詳細 ---
    "jp-condition-clinicalstatus-display-missing": {
        "desc": "JP_Condition_eCS: clinicalStatus.coding.display 必須欠落",
        "pattern": r"Condition\.clinicalStatus\.coding\.display.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-condition-verificationstatus-display-missing": {
        "desc": "JP_Condition_eCS: verificationStatus.coding.display 必須欠落",
        "pattern": r"Condition\.verificationStatus\.coding\.display.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-condition-category-missing": {
        "desc": "JP_Condition_eCS: category 必須欠落",
        "pattern": r"Condition\.category.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-condition-code-text-missing": {
        "desc": "JP_Condition_eCS: code.text 必須欠落",
        "pattern": r"Condition\.code\.text.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-condition-medisrecordno-slice-missing": {
        "desc": "JP_Condition_eCS: code.coding:medisRecordNo slice 必須欠落",
        "pattern": r"Condition\.code\.coding:medisRecordNo.*minimum required.*1",
    },

    # --- 追加: JP_Observation_LabResult 詳細 ---
    "jp-obs-lab-effective-missing": {
        "desc": "JP_Observation_LabResult_eCS: effective[x] 必須欠落",
        "pattern": r"Observation\.effective\[x\].*(最小必要値.*1|minimum required.*1)",
    },
    "jp-obs-lab-code-text-missing": {
        "desc": "JP_Observation_LabResult_eCS: code.text 必須欠落",
        "pattern": r"Observation\.code\.text.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-obs-lab-code-coding-display-missing": {
        "desc": "JP_Observation_LabResult_eCS: code.coding.display 必須欠落",
        "pattern": r"Observation\.code\.coding\.display.*(最小必要値.*1|minimum required.*1)",
    },

    # --- 追加: JP_MedicationRequest_eCS 詳細 ---
    "jp-medreq-identifier-count-min3": {
        "desc": "JP_MedicationRequest_eCS: identifier 必要数 3 未満",
        "pattern": r"MedicationRequest\.identifier.*(最小必要値.*3|minimum required.*3)",
    },
    "jp-medreq-request-identifier-slice-missing": {
        "desc": "JP_MedicationRequest_eCS: identifier:requestIdentifier slice 必須欠落",
        "pattern": r"MedicationRequest\.identifier:requestIdentifier.*minimum required.*1",
    },
    "jp-medreq-lastupdated-missing": {
        "desc": "JP_MedicationRequest_eCS: meta.lastUpdated 必須欠落",
        "pattern": r"MedicationRequest\.meta\.lastUpdated.*(最小必要値.*1|minimum required.*1)",
    },

    # --- 追加 v3: FHIRPath invariant ---
    "condition-con-4-abatement": {
        "desc": "con-4: Condition.abatement を設定するなら clinicalStatus は inactive/resolved/remission でなければならない",
        "pattern": r"con-4|abatement.*(inactive|resolved|remission)|abatement.*only.*if",
    },
    # --- 追加 v3: Bundle-level ---
    "bundle-document-first-composition": {
        "desc": "Bundle.type=document なら最初の entry は Composition でなければならない",
        "pattern": r"(bdl-1|first entry.*Composition|Bundle\.entry.*first|Composition.*first.*entry)",
    },

    # --- 追加 v3: JP Core 各種 profile ---
    "jp-patient-identifier-missing": {
        "desc": "JP_Patient: identifier 必須欠落",
        "pattern": r"Patient\.identifier.*(最小必要値.*1|minimum required.*1)",
    },
    # --- 追加 v3: required binding 違反 ---
    "patient-gender-invalid-binding": {
        "desc": "Patient.gender が admin-gender ValueSet の範囲外",
        "pattern": r"(Patient\.)?gender.*ValueSet|gender.*is not (in|a valid)|不明.*gender|(male|female|other|unknown).*でなければ",
    },

    # --- 追加 v3: JP-CLINS constraint from real data ---
    "medreq-r5020-usage-constraint": {
        "desc": "validUsage-MedicationUsage-codesystem: R5020 の用法コード制約",
        "pattern": r"validUsage-MedicationUsage-codesystem|R5020",
    },
    "medreq-dosage-periodofuse-extension-required": {
        "desc": "JP_MedicationDosage_eCS: Dosage.extension:periodOfUse 必須欠落",
        "pattern": r"Dosage\.extension:periodOfUse|Dosage\.extension.*(最小必要値.*1|minimum required.*1)",
    },
    "diagnosticreport-category-first-slice": {
        "desc": "JP_DiagnosticReport: category:first slice 必須欠落",
        "pattern": r"DiagnosticReport\.category:first.*minimum required.*1",
    },

    # --- 追加 v4: 追加パターン ---
    "immunization-vaccinecode-missing": {
        "desc": "Immunization.vaccineCode 必須欠落 (R4 base cardinality)",
        "pattern": r"Immunization\.vaccineCode.*(最小必要値.*1|minimum required.*1)",
    },
    "encounter-status-missing": {
        "desc": "Encounter.status 必須欠落",
        "pattern": r"Encounter\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "encounter-class-missing": {
        "desc": "Encounter.class 必須欠落",
        "pattern": r"Encounter\.class.*(最小必要値.*1|minimum required.*1)",
    },
    "bundle-transaction-entry-request-missing": {
        "desc": "Bundle.type=transaction で entry.request 欠落 (bdl-3)",
        "pattern": r"bdl-3|entry\.request.*required|transaction.*request.*(必須|required)",
    },
    "extension-value-type-mismatch": {
        "desc": "定義済 extension に対して定義と異なる value[x] 型を指定",
        "pattern": r"extension\s*'[^']+'\s*の定義はタイプ\s*\[[^\]]*\]\s*を許可していますが|extension.*definition allows type|value type.*not.*allowed.*extension",
    },
    "slice-not-matching-known-slice": {
        "desc": "既知の slice discriminator と合わない要素 (Observation.category など)",
        "pattern": r"どの既知のスライスとも一致しません|does not match any (known )?slice|要素は既知のスライス.*と一致せず",
    },
    "reference-target-profile-mismatch": {
        "desc": "Reference が profile が要求する target と一致しない",
        "pattern": r"タイプ\s*'\w+'\s*は.*有効なターゲット|not a valid target|Reference.*target.*(型|profile).*(不一致|not allowed)|参照.*profile.*違反",
    },
    "medication-request-intent-missing": {
        "desc": "MedicationRequest.intent 必須欠落 (R4 base)",
        "pattern": r"MedicationRequest\.intent.*(最小必要値.*1|minimum required.*1)",
    },
    "condition-clinical-verification-consistency": {
        "desc": "Condition の clinicalStatus と verificationStatus の consistency 制約 (con-3 / con-5)",
        "pattern": r"con-[35]|clinicalStatus.*(必要|conflicts|not.*combined)|verificationStatus.*conflict",
    },

    # --- 追加 v5: 各種 base 必須要素 ---
    "coverage-status-missing": {
        "desc": "Coverage.status 必須欠落",
        "pattern": r"Coverage\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "coverage-beneficiary-missing": {
        "desc": "Coverage.beneficiary 必須欠落",
        "pattern": r"Coverage\.beneficiary.*(最小必要値.*1|minimum required.*1)",
    },
    "coverage-payor-missing": {
        "desc": "Coverage.payor 必須欠落",
        "pattern": r"Coverage\.payor.*(最小必要値.*1|minimum required.*1)",
    },
    "allergyintolerance-patient-missing": {
        "desc": "AllergyIntolerance.patient 必須欠落",
        "pattern": r"AllergyIntolerance\.patient.*(最小必要値.*1|minimum required.*1)",
    },
    "location-status-invalid": {
        "desc": "Location.status に enum 外の値",
        "pattern": r"Location\.status|location-status.*(ValueSet|でなければ|not.*valid|not in the value set)",
    },
    "imagingstudy-subject-missing": {
        "desc": "ImagingStudy.subject 必須欠落",
        "pattern": r"ImagingStudy\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "medicationdispense-status-missing": {
        "desc": "MedicationDispense.status 必須欠落",
        "pattern": r"MedicationDispense\.status.*(最小必要値.*1|minimum required.*1)",
    },
    # --- 追加 v5: profile slice closed 違反 ---
    "bp-profile-extra-component": {
        "desc": "bp profile (LOINC 85354-9) で closed slice に定義外の component を追加 (info level detection)",
        "pattern": r"どの既知のスライスとも一致しません.*bp\|4\.0\.1|does not match any (known )?slice.*bp\|4\.0\.1",
    },

    # --- 追加 v5: Observation invariant ---
    "observation-value-and-dataabsentreason": {
        "desc": "Observation.value[x] と dataAbsentReason が同時に存在 (obs-6/obs-7)",
        "pattern": r"obs-[67]|dataAbsentReason.*not.*if.*value|value.*absent.*同時",
    },

    # --- v6 B1: FHIR base 追加 resource 種別 ---
    "diagnosticreport-status-missing": {
        "desc": "DiagnosticReport.status 必須欠落",
        "pattern": r"DiagnosticReport\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "diagnosticreport-code-missing": {
        "desc": "DiagnosticReport.code 必須欠落",
        "pattern": r"DiagnosticReport\.code.*(最小必要値.*1|minimum required.*1)",
    },
    "servicerequest-status-missing": {
        "desc": "ServiceRequest.status 必須欠落",
        "pattern": r"ServiceRequest\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "servicerequest-intent-missing": {
        "desc": "ServiceRequest.intent 必須欠落",
        "pattern": r"ServiceRequest\.intent.*(最小必要値.*1|minimum required.*1)",
    },
    "servicerequest-subject-missing": {
        "desc": "ServiceRequest.subject 必須欠落",
        "pattern": r"ServiceRequest\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "procedure-status-missing": {
        "desc": "Procedure.status 必須欠落",
        "pattern": r"Procedure\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "procedure-subject-missing": {
        "desc": "Procedure.subject 必須欠落",
        "pattern": r"Procedure\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "composition-status-missing": {
        "desc": "Composition.status 必須欠落",
        "pattern": r"Composition\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "composition-type-missing": {
        "desc": "Composition.type 必須欠落",
        "pattern": r"Composition\.type.*(最小必要値.*1|minimum required.*1)",
    },
    "composition-date-missing": {
        "desc": "Composition.date 必須欠落",
        "pattern": r"Composition\.date.*(最小必要値.*1|minimum required.*1)",
    },
    "composition-author-missing": {
        "desc": "Composition.author 必須欠落",
        "pattern": r"Composition\.author.*(最小必要値.*1|minimum required.*1)",
    },
    "composition-title-missing": {
        "desc": "Composition.title 必須欠落",
        "pattern": r"Composition\.title.*(最小必要値.*1|minimum required.*1)",
    },
    "careplan-status-missing": {
        "desc": "CarePlan.status 必須欠落",
        "pattern": r"CarePlan\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "careplan-intent-missing": {
        "desc": "CarePlan.intent 必須欠落",
        "pattern": r"CarePlan\.intent.*(最小必要値.*1|minimum required.*1)",
    },
    "careplan-subject-missing": {
        "desc": "CarePlan.subject 必須欠落",
        "pattern": r"CarePlan\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "goal-lifecyclestatus-missing": {
        "desc": "Goal.lifecycleStatus 必須欠落",
        "pattern": r"Goal\.lifecycleStatus.*(最小必要値.*1|minimum required.*1)",
    },
    "goal-description-missing": {
        "desc": "Goal.description 必須欠落",
        "pattern": r"Goal\.description.*(最小必要値.*1|minimum required.*1)",
    },
    "goal-subject-missing": {
        "desc": "Goal.subject 必須欠落",
        "pattern": r"Goal\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "task-status-missing": {
        "desc": "Task.status 必須欠落",
        "pattern": r"Task\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "task-intent-missing": {
        "desc": "Task.intent 必須欠落",
        "pattern": r"Task\.intent.*(最小必要値.*1|minimum required.*1)",
    },
    "medicationstatement-status-missing": {
        "desc": "MedicationStatement.status 必須欠落",
        "pattern": r"MedicationStatement\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "medicationstatement-subject-missing": {
        "desc": "MedicationStatement.subject 必須欠落",
        "pattern": r"MedicationStatement\.subject.*(最小必要値.*1|minimum required.*1)",
    },

    # --- v6 B2: JP Core profile 適用時の必須欠落 ---
    "jp-organization-identifier-system-missing": {
        "desc": "JP_Organization: identifier.system 必須欠落",
        "pattern": r"Organization\.identifier(\[\d+\]|\.[^:]+)?\.system.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-coverage-identifier-system-missing": {
        "desc": "JP_Coverage: identifier.system 必須欠落",
        "pattern": r"Coverage\.identifier(\[\d+\]|\.[^:]+)?\.system.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-coverage-identifier-value-missing": {
        "desc": "JP_Coverage: identifier.value 必須欠落",
        "pattern": r"Coverage\.identifier(\[\d+\]|\.[^:]+)?\.value.*(最小必要値.*1|minimum required.*1)",
    },
    "immunization-patient-missing": {
        "desc": "Immunization.patient 必須欠落",
        "pattern": r"Immunization\.patient.*(最小必要値.*1|minimum required.*1)",
    },
    "immunization-status-missing": {
        "desc": "Immunization.status 必須欠落",
        "pattern": r"Immunization\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "immunization-occurrence-missing": {
        "desc": "Immunization.occurrence[x] 必須欠落",
        "pattern": r"Immunization\.occurrence\[x\].*(最小必要値.*1|minimum required.*1)",
    },
    "documentreference-status-missing": {
        "desc": "DocumentReference.status 必須欠落",
        "pattern": r"DocumentReference\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "documentreference-content-missing": {
        "desc": "DocumentReference.content 必須欠落",
        "pattern": r"DocumentReference\.content.*(最小必要値.*1|minimum required.*1)",
    },
    "condition-subject-missing": {
        "desc": "Condition.subject 必須欠落",
        "pattern": r"Condition\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "medreq-medication-missing": {
        "desc": "MedicationRequest.medication[x] 必須欠落",
        "pattern": r"MedicationRequest\.medication\[x\].*(最小必要値.*1|minimum required.*1)",
    },
    "medreq-subject-missing": {
        "desc": "MedicationRequest.subject 必須欠落",
        "pattern": r"MedicationRequest\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "medreq-status-missing": {
        "desc": "MedicationRequest.status 必須欠落",
        "pattern": r"MedicationRequest\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "familymemberhistory-status-missing": {
        "desc": "FamilyMemberHistory.status 必須欠落",
        "pattern": r"FamilyMemberHistory\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "familymemberhistory-patient-missing": {
        "desc": "FamilyMemberHistory.patient 必須欠落",
        "pattern": r"FamilyMemberHistory\.patient.*(最小必要値.*1|minimum required.*1)",
    },
    "familymemberhistory-relationship-missing": {
        "desc": "FamilyMemberHistory.relationship 必須欠落",
        "pattern": r"FamilyMemberHistory\.relationship.*(最小必要値.*1|minimum required.*1)",
    },

    # --- v6 B3: JP-CLINS eCS profile 必須欠落 ---
    "resource-meta-lastupdated-missing": {
        "desc": "任意リソースの meta.lastUpdated 必須欠落 (eCS 系プロファイル全般で要求)",
        "pattern": r"\w+\.meta\.lastUpdated.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-encounter-ecs-period-start-missing": {
        "desc": "JP_Encounter_eCS: period.start 必須欠落",
        "pattern": r"Encounter\.period\.start.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-careplan-ecs-title-missing": {
        "desc": "JP_CarePlan_eCS: title 必須欠落",
        "pattern": r"CarePlan\.title.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-careplan-ecs-description-missing": {
        "desc": "JP_CarePlan_eCS: description 必須欠落",
        "pattern": r"CarePlan\.description.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-patient-ecs-gender-missing": {
        "desc": "JP_Patient_eCS: gender 必須欠落",
        "pattern": r"Patient\.gender.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-patient-ecs-birthdate-missing": {
        "desc": "JP_Patient_eCS: birthDate 必須欠落",
        "pattern": r"Patient\.birthDate.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-organization-ecs-name-missing": {
        "desc": "JP_Organization_eCS: name 必須欠落",
        "pattern": r"Organization\.name.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-familymemberhistory-ecs-relationship-coding-missing": {
        "desc": "JP_FamilyMemberHistory_eCS: relationship.coding 必須欠落",
        "pattern": r"FamilyMemberHistory\.relationship\.coding.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-composition-extension-version-missing": {
        "desc": "JP_Composition_*: extension:version slice 必須欠落",
        "pattern": r"Composition\.extension:version.*(最小必要値.*1|minimum required.*1)",
    },
    "consent-status-missing": {
        "desc": "Consent.status 必須欠落",
        "pattern": r"Consent\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "consent-scope-missing": {
        "desc": "Consent.scope 必須欠落",
        "pattern": r"Consent\.scope.*(最小必要値.*1|minimum required.*1)",
    },
    "consent-category-missing": {
        "desc": "Consent.category 必須欠落",
        "pattern": r"Consent\.category.*(最小必要値.*1|minimum required.*1)",
    },
    "medadmin-status-missing": {
        "desc": "MedicationAdministration.status 必須欠落",
        "pattern": r"MedicationAdministration\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "medadmin-medication-missing": {
        "desc": "MedicationAdministration.medication[x] 必須欠落",
        "pattern": r"MedicationAdministration\.medication\[x\].*(最小必要値.*1|minimum required.*1)",
    },
    "medadmin-subject-missing": {
        "desc": "MedicationAdministration.subject 必須欠落",
        "pattern": r"MedicationAdministration\.subject.*(最小必要値.*1|minimum required.*1)",
    },

    # --- v6 B4: Terminology 追加 ---
    "quantity-code-without-system": {
        "desc": "Quantity.code が存在するが system が欠落 (qty-3 invariant)",
        "pattern": r"qty-3|Quantity\.system\s+SHALL\s+be\s+present|A code SHALL only be present if it has|codeがあるならsystemも必要|systemがない場合、コード",
    },
    "dataabsentreason-not-in-valueset": {
        "desc": "Observation.dataAbsentReason が拡張可能/必須 ValueSet 外",
        "pattern": r"(dataAbsentReason.*not in|is not in the value set.*data-absent-reason|dataAbsentReason.*(ValueSet|でなければ)|DataAbsentReason)",
    },
    "coding-no-system": {
        "desc": "Coding.code はあるが system が欠落",
        "pattern": r"(system SHALL be present|Coding\.system.*(最小必要値.*1|minimum required.*1)|コーディング.*systemが必要|A system must be provided|システム.*(必須|欠落)|Codingには.*systemがない|Coding.*(no|without) system|Coding.*needs a system)",
    },

    # --- v6 B5: Extension 追加 ---
    "ext-1-invariant-violation": {
        "desc": "ext-1: extension は value[x] か nested extension のどちらか片方のみ",
        "pattern": r"(ext-1|Must have either (extensions|extension) (or|and) value\[x\], not both|(値|value\[x\]).*(のいずれか|extension.*のどちらか)|either extensions or value)",
    },
    "modifierextension-cannot-be-ignored": {
        "desc": (
            "modifierExtension が未知で無視できない状態。HAPI は error で "
            "'extension <url> は未知であり、ここでは許可されていません' を発火 "
            "(msg 自体は modifierExtension 名を含まないが、severity=error であること "
            "が modifierExtension 由来である証拠 = 通常 extension は warning に留まる)。"
        ),
        "pattern": r"(extension\s+http\S+\s+は未知であり.*許可されていません|extension\s+http\S+\s+is unknown.*not.*allowed|Unknown modifierExtension|modifierExtension.*(cannot be ignored|must be recognized))",
    },
    "extension-missing-url": {
        "desc": "extension.url 欠落 (base cardinality)",
        "pattern": r"(Extension\.url|extension\.url).*(最小必要値.*1|minimum required.*1)",
    },

    # --- v6 B6: 100 突破のための追加 ---
    "medadmin-effective-missing": {
        "desc": "MedicationAdministration.effective[x] 必須欠落",
        "pattern": r"MedicationAdministration\.effective\[x\].*(最小必要値.*1|minimum required.*1)",
    },
    "imagingstudy-status-missing": {
        "desc": "ImagingStudy.status 必須欠落",
        "pattern": r"ImagingStudy\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "endpoint-connectiontype-missing": {
        "desc": "Endpoint.connectionType 必須欠落",
        "pattern": r"Endpoint\.connectionType.*(最小必要値.*1|minimum required.*1)",
    },
    "endpoint-payloadtype-missing": {
        "desc": "Endpoint.payloadType 必須欠落",
        "pattern": r"Endpoint\.payloadType.*(最小必要値.*1|minimum required.*1)",
    },
    "endpoint-address-missing": {
        "desc": "Endpoint.address 必須欠落",
        "pattern": r"Endpoint\.address.*(最小必要値.*1|minimum required.*1)",
    },
    "endpoint-status-missing": {
        "desc": "Endpoint.status 必須欠落",
        "pattern": r"Endpoint\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "specimen-status-invalid": {
        "desc": "Specimen.status に enum 外の値",
        "pattern": r"Specimen\.status|specimen-status.*(ValueSet|でなければ|not.*valid)",
    },

    # === v7 Batch A: DataType 系 invariant ===
    "period-end-before-start": {
        "desc": "Period.end が Period.start より前 (per-1 invariant)",
        "pattern": r"(per-1|Period\.end.*(before|SHALL be on or after).*Period\.start|If present.*end SHALL have.*value greater or equal to.*start|end.*(先|before).*start)",
    },
    "attachment-url-and-data": {
        "desc": "Attachment.url と Attachment.data 両方指定 (att-1 invariant)",
        "pattern": r"(att-1|Attachment.*(both|either).*data.*url|If the Attachment has data|url.*data.*同時)",
    },
    "range-high-lower-than-low": {
        "desc": "Range.high が Range.low より小さい (rng-2)",
        "pattern": r"(rng-2|high.*(cannot|SHALL).*lower|low.*(cannot|SHALL).*greater.*high|Range.*inconsistent)",
    },
    "ratio-denominator-zero": {
        "desc": "Ratio.denominator = 0",
        "pattern": r"(rat-1|Ratio.*denominator.*(zero|0)|denominator.*0.*(禁止|invalid))",
    },
    "signature-who-missing": {
        "desc": "Signature.who 必須欠落",
        "pattern": r"Signature\.who.*(最小必要値.*1|minimum required.*1)",
    },
    "signature-when-missing": {
        "desc": "Signature.when 必須欠落",
        "pattern": r"Signature\.when.*(最小必要値.*1|minimum required.*1)",
    },
    "contactpoint-value-no-system": {
        "desc": "ContactPoint.value あるが system 無し (cpt-2)",
        "pattern": r"(cpt-2|ContactPoint.*(system).*(required|SHALL|必要)|value.*system.*欠落|A system is required if a value is provided)",
    },
    "patient-multiple-deceased": {
        "desc": (
            "Patient.deceased[x] の複数型指定 (choice violation)。HAPI は 2 つ目の "
            "value[x] を 認識できないプロパティ として弾く (最初にセットされた "
            "value[x] が primary、後続は Unknown property 扱い)。"
        ),
        "pattern": r"(認識できないプロパティ.*'deceased|Unrecognized property.*deceased|Cannot have more than one value.*deceased|value\[x\].*deceased)",
    },
    "patient-multiple-multiplebirth": {
        "desc": (
            "Patient.multipleBirth[x] の複数型指定。HAPI は 認識できないプロパティ "
            "'multipleBirthInteger' 等で弾く。"
        ),
        "pattern": r"(認識できないプロパティ.*'multipleBirth|Unrecognized property.*multipleBirth|Cannot have more than one value.*multipleBirth|value\[x\].*multipleBirth)",
    },
    "address-invalid-use-enum": {
        "desc": "Address.use に enum 外の値",
        "pattern": r"(Address\.use|AddressUse).*(ValueSet|でなければ|is not (in|a valid)|に含まれていません)|address-use.*(not.*valid|でなければ|含まれていません)",
    },
    "humanname-invalid-use-enum": {
        "desc": "HumanName.use に enum 外の値",
        "pattern": r"(HumanName\.use|name\.use|NameUse).*(ValueSet|でなければ|is not (in|a valid)|に含まれていません)|name-use.*(not.*valid|でなければ|含まれていません)",
    },
    "identifier-invalid-use-enum": {
        "desc": "Identifier.use に enum 外の値",
        "pattern": r"(Identifier\.use|IdentifierUse).*(ValueSet|でなければ|is not (in|a valid)|に含まれていません)|identifier-use.*(not.*valid|でなければ|含まれていません)",
    },
    "quantity-comparator-invalid": {
        "desc": "Quantity.comparator に enum 外の値",
        "pattern": r"Quantity\.comparator|quantity-comparator.*(ValueSet|でなければ|not.*valid)",
    },
    "reference-empty": {
        "desc": (
            "Reference が完全に空 (ref-1 相当、通常は ele-1 が発火)。HAPI は "
            "'オブジェクトには何らかのコンテンツが必要です' (parse-level) で発火。"
        ),
        "pattern": r"(オブジェクトには何らかのコンテンツが必要です|element must have some content|ref-1|Reference.*(reference|identifier|display).*(any|either|いずれか)|SHALL have a contained resource|At least one of|SHALL have.*(reference|identifier|display))",
    },
    "coding-empty": {
        "desc": (
            "Coding が完全に空 (ele-1)。HAPI の Japanese localization では "
            "'オブジェクトには何らかのコンテンツが必要です' (parse-level error) と "
            "して発火。expression が Bundle.entry[N].resource 形式 (type/id 情報 "
            "なし) で出るため、framework 側 parse_errors で attribute できるよう "
            "expression 拡張済 (2026-07-24 fix)。"
        ),
        "pattern": r"(オブジェクトには何らかのコンテンツが必要です|element must have some content|Coding.*(empty|空)|ele-1.*Coding|Coding.*(children|@value))",
    },
    "meta-security-unknown-cs": {
        "desc": "Meta.security の CodeSystem が未知",
        "pattern": r"(security.*(CodeSystem.*(unknown|未知)|not.*(found|supported)))|Meta\.security.*(未知|unknown)",
    },
    "duration-invalid-unit": {
        "desc": "Duration.code が UCUM 時間単位でない",
        "pattern": r"(Duration.*(code|unit)|dur-1|Duration.*(UCUM|time unit)|time-unit)",
    },
    "money-currency-invalid": {
        "desc": "Money.currency が ISO 4217 でない",
        "pattern": r"(Money\.currency|currency.*(ValueSet|ISO 4217|でなければ|is not (in|a valid))|iso4217)",
    },
    "coverage-period-end-before-start": {
        "desc": "Coverage.period.end が start より前 (per-1 適用)",
        "pattern": r"(per-1|Period\.end.*(before|SHALL be on or after).*start|end.*(先|before).*start)",
    },
    "timing-frequency-invalid": {
        "desc": "Timing.repeat.frequency が負の値 (positiveInt binding 違反)",
        "pattern": r"(Timing.*frequency|frequency.*(negative|>=|0以上|>|invalid|positiveInt)|tim-4|許可された最小値.*1.*(下回|below)|below.*minimum|value is below)",
    },

    # === v7 Batch B: Reference target constraint ===
    # 履歴: 元々 reference-target-<resource>-<field>-<wrongtype> という
    # resource type 別 15 slug を定義していたが、実装時に全て generic
    # `reference-type-mismatch` に統合され、resource type 別 slug は未使用の
    # まま残っていた。2026-07-24 に集約削除 (詳細は EXPECTED_ISSUES 末尾の
    # Historical consolidation note 参照)。resource type 別網羅は case 側の
    # 16 file (reference-<resource>-<field>-<wrongtype>.ndjson) で行い、
    # 全て `reference-type-mismatch` slug を使用する。

    # === v7 Batch C: 追加 resource base cardinality ===
    "researchstudy-status-missing": {
        "desc": "ResearchStudy.status 必須欠落",
        "pattern": r"ResearchStudy\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "questionnaire-status-missing": {
        "desc": "Questionnaire.status 必須欠落",
        "pattern": r"Questionnaire\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "questionnaireresponse-status-missing": {
        "desc": "QuestionnaireResponse.status 必須欠落",
        "pattern": r"QuestionnaireResponse\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "consent-status-scope-missing-multi": {
        "desc": "Consent の scope + status + category + patient/dateTime 必須",
        "pattern": r"Consent\.(scope|status|category|patient|dateTime).*(最小必要値.*1|minimum required.*1)",
    },
    "communication-status-missing": {
        "desc": "Communication.status 必須欠落",
        "pattern": r"Communication\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "supplyrequest-status-missing": {
        "desc": "SupplyRequest — 実際は 0..1 だが item と requester が必要",
        "pattern": r"SupplyRequest\.(item|requester).*(最小必要値.*1|minimum required.*1)",
    },
    "appointment-status-missing": {
        "desc": "Appointment.status 必須欠落",
        "pattern": r"Appointment\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "appointment-participant-missing": {
        "desc": "Appointment.participant 必須欠落",
        "pattern": r"Appointment\.participant.*(最小必要値.*1|minimum required.*1)",
    },
    "flag-status-code-missing": {
        "desc": "Flag.status/code/subject 必須欠落",
        "pattern": r"Flag\.(status|code|subject).*(最小必要値.*1|minimum required.*1)",
    },
    "list-status-mode-missing": {
        "desc": "List.status/mode 必須欠落",
        "pattern": r"List\.(status|mode).*(最小必要値.*1|minimum required.*1)",
    },

    # === v7 Batch D: JP Core 追加 profile ===
    "jp-media-content-missing": {
        "desc": "Media.content 必須欠落",
        "pattern": r"Media\.content.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-medication-code-missing": {
        "desc": "JP_Medication: code が期待される場所で欠落 (Medication.code は 0..1 base だが JP profile が要求)",
        "pattern": r"Medication\.code.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-imagingstudy-radiology-no-status": {
        "desc": "JP_ImagingStudy_Radiology: status 欠落 (base R4)",
        "pattern": r"ImagingStudy\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-imagingstudy-endoscopy-no-status": {
        "desc": "JP_ImagingStudy_Endoscopy: status 欠落",
        "pattern": r"ImagingStudy\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-dr-labresult-no-required": {
        "desc": "JP_DiagnosticReport_LabResult: status/code 欠落 (base)",
        "pattern": r"DiagnosticReport\.(status|code).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-dr-radiology-no-required": {
        "desc": "JP_DiagnosticReport_Radiology: status/code 欠落 (base)",
        "pattern": r"DiagnosticReport\.(status|code).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-consent-status-missing": {
        "desc": "JP_Consent (通常): status/scope/category/patient/dateTime のいずれか欠落",
        "pattern": r"Consent\.(status|scope|category|patient|dateTime).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-careplan-jp-no-required": {
        "desc": "JP_CarePlan (通常): status/intent/subject 欠落",
        "pattern": r"CarePlan\.(status|intent|subject).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-documentreference-jp-no-required": {
        "desc": "JP_DocumentReference: status/content 欠落 (base)",
        "pattern": r"DocumentReference\.(status|content).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-servicerequest-jp-no-required": {
        "desc": "JP_ServiceRequest_Common: status/intent/subject 欠落 (base)",
        "pattern": r"ServiceRequest\.(status|intent|subject).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-familymemberhistory-jp-status-missing": {
        "desc": "JP_FamilyMemberHistory: status/patient/relationship 欠落 (base)",
        "pattern": r"FamilyMemberHistory\.(status|patient|relationship).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-condition-registered-diagnosis-basic": {
        "desc": "JP_Condition_Diagnosis: subject 欠落 (base Condition)",
        "pattern": r"Condition\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-medication-ingredient-drugno-basic": {
        "desc": "JP_Medication: 通常は code 0..1 だが JP profile が要求",
        "pattern": r"Medication\.code.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-medreq-jp-no-required": {
        "desc": "JP_MedicationRequest: status/intent/subject/medication 欠落",
        "pattern": r"MedicationRequest\.(status|intent|subject|medication\[x\]).*(最小必要値.*1|minimum required.*1)",
    },
    "jp-medadmin-jp-no-required": {
        "desc": "JP_MedicationAdministration: status/medication/subject/effective 欠落",
        "pattern": r"MedicationAdministration\.(status|medication\[x\]|subject|effective\[x\]).*(最小必要値.*1|minimum required.*1)",
    },

    # === v7 Batch E: JP-CLINS eCS 追加 ===
    "jp-encounter-ecs-identifier-system-missing": {
        "desc": "JP_Encounter_eCS: identifier.system 必須欠落",
        "pattern": r"Encounter\.identifier(\[\d+\]|\.[^:]+)?\.system.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-encounter-ecs-identifier-value-missing": {
        "desc": "JP_Encounter_eCS: identifier.value 必須欠落",
        "pattern": r"Encounter\.identifier(\[\d+\]|\.[^:]+)?\.value.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-encounter-ecs-class-system-missing": {
        "desc": "JP_Encounter_eCS: class.system 必須欠落",
        "pattern": r"Encounter\.class\.system.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-encounter-ecs-class-code-missing": {
        "desc": "JP_Encounter_eCS: class.code 必須欠落",
        "pattern": r"Encounter\.class\.code.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-encounter-ecs-class-display-missing": {
        "desc": "JP_Encounter_eCS: class.display 必須欠落",
        "pattern": r"Encounter\.class\.display.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-careplan-ecs-identifier-system-missing": {
        "desc": "JP_CarePlan_eCS: identifier.system 必須欠落",
        "pattern": r"CarePlan\.identifier(\[\d+\]|\.[^:]+)?\.system.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-careplan-ecs-identifier-value-missing": {
        "desc": "JP_CarePlan_eCS: identifier.value 必須欠落",
        "pattern": r"CarePlan\.identifier(\[\d+\]|\.[^:]+)?\.value.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-careplan-ecs-category-missing": {
        "desc": "JP_CarePlan_eCS: category 必須欠落",
        "pattern": r"CarePlan\.category.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-careplan-ecs-period-start-missing": {
        "desc": "JP_CarePlan_eCS: period.start 必須欠落",
        "pattern": r"CarePlan\.period\.start.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-organization-ecs-medisrecord-slice-missing": {
        "desc": "JP_Organization_eCS: identifier:medicalInstitutionCode slice 必須欠落",
        "pattern": r"Organization\.identifier:medicalInstitutionCode.*minimum required.*1",
    },
    "jp-organization-ecs-type-coding-missing": {
        "desc": "JP_Organization_eCS: type.coding 必須欠落",
        "pattern": r"Organization\.type\.coding.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-patient-ecs-name-text-missing": {
        "desc": "JP_Patient_eCS: name.text 必須欠落",
        "pattern": r"Patient\.name(\[\d+\])?\.text.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-patient-ecs-name-given-missing": {
        "desc": "JP_Patient_eCS: name.given 必須欠落",
        "pattern": r"Patient\.name(\[\d+\])?\.given.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-patient-ecs-address-text-missing": {
        "desc": "JP_Patient_eCS: address.text 必須欠落",
        "pattern": r"Patient\.address(\[\d+\])?\.text.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-practitioner-ecs-qualification-code-coding-missing": {
        "desc": "JP_Practitioner_eCS: qualification.code.coding 必須欠落",
        "pattern": r"Practitioner\.qualification\.code\.coding.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-familymemberhistory-ecs-relationship-coding-code-missing": {
        "desc": "JP_FamilyMemberHistory_eCS: relationship.coding.code 必須欠落",
        "pattern": r"FamilyMemberHistory\.relationship\.coding\.code.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-familymemberhistory-ecs-sex-coding-missing": {
        "desc": "JP_FamilyMemberHistory_eCS: sex.coding 必須欠落",
        "pattern": r"FamilyMemberHistory\.sex\.coding.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-composition-ereferral-identifier-system-missing": {
        "desc": "JP_Composition_eReferral: identifier.system 必須欠落",
        "pattern": r"Composition\.identifier(\[\d+\]|\.[^:]+)?\.system.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-composition-ereferral-type-coding-code-missing": {
        "desc": "JP_Composition_eReferral: type.coding.code 必須欠落",
        "pattern": r"Composition\.type\.coding\.code.*(最小必要値.*1|minimum required.*1)",
    },
    "jp-composition-edischargesummary-category-missing": {
        "desc": "JP_Composition_eDischargeSummary: category 必須欠落",
        "pattern": r"Composition\.category.*(最小必要値.*1|minimum required.*1)",
    },

    # === v7 Batch F: Terminology 追加 ===
    "loinc-code-case-mismatch": {
        "desc": "LOINC は数値ハイフン形式なので case は無関係だが、混入した lowercase alpha が unknown",
        "pattern": r"Unknown code|未知のコード",
    },
    "snomed-code-with-wrong-system-scheme": {
        "desc": "SNOMED code に url 系ではなく urn:oid: system を使うと未知扱い",
        "pattern": r"(Unknown code|未知のコード|CodeSystem.*(is unknown|未知))",
    },
    "codeableconcept-only-text-no-coding": {
        "desc": "CodeableConcept.text のみで coding[] 空 (required binding では通常 error)",
        "pattern": r"(only.*text.*coding|coding.*(0|empty|空)|text-only|text.*(のみ|不足))",
    },
    "coding-code-not-in-preferred-binding": {
        "desc": "Coding.code が preferred binding の ValueSet に含まれない",
        "pattern": r"(is not in.*value set|ValueSet.*に含まれ|not.*in.*value.*set|Preferred)",
    },
    "quantity-negative-value-observation": {
        "desc": "Observation.valueQuantity.value が負 (invariant 未定義でも他所で拒否 期待)",
        "pattern": r"(quantity.*(negative|<\s*0)|obs-3|value.*(必須|invalid)|ele-1)",
    },
    "coding-with-fragment-cs": {
        "desc": "Coding.system がフラグメント記法未対応の場合の warning",
        "pattern": r"(fragment|断片|not.*complete)",
    },
    "ucum-invalid-unit-syntax": {
        "desc": "UCUM 単位に不正な記号",
        "pattern": r"(UCUM|not a valid.*unit|invalid.*unit|Unknown code)",
    },
    "code-with-space-in-value": {
        "desc": "Coding.code に空白が含まれる (通常許容されない)",
        "pattern": r"(code.*(space|whitespace|空白)|Unknown code)",
    },
    "codeableconcept-multiple-codings-none-valid": {
        "desc": "CodeableConcept に複数 coding、いずれも ValueSet に含まれず",
        "pattern": r"(none.*coding.*ValueSet|codingのいずれもが.*ValueSet|none of the.*codings)",
    },
    "coding-display-required-missing": {
        "desc": "profile が Coding.display 必須指定するのに欠落",
        "pattern": r"Coding\.display.*(最小必要値.*1|minimum required.*1)|coding\.display.*(minimum required|必要)",
    },

    # === v7 Batch G: Extensions 追加 ===
    "modifierextension-known-but-forbidden-here": {
        "desc": "modifierExtension として使えない known extension URL を配置",
        "pattern": r"(modifierExtension|is not a modifier|not.*modifier|isModifier.*false)",
    },
    "extension-multiple-same-url-when-max1": {
        "desc": "profile で max=1 の extension slice に複数",
        "pattern": r"(extension.*(最大許容値|maximum.*1|max=1)|extension.*(overflow|multiple))",
    },
    "extension-nested-without-value": {
        "desc": "nested sub-extension の一つが value も extension も持たない (ext-1)",
        "pattern": r"(ext-1|extension.*(either|neither).*(value|extension))",
    },
    "extension-in-primitive-value-extension": {
        "desc": "primitive の _value 上の extension が未知 URL",
        "pattern": r"(extension|拡張).*(未知|unknown|not.*defined)",
    },
    "extension-us-core-birthsex-in-jp": {
        "desc": "US Core birthsex extension を JP context で使用",
        "pattern": r"(extension|拡張).*(未知|unknown|not allowed|型.*不一致|type.*not)",
    },
    "modifierextension-many": {
        "desc": "複数の unknown modifierExtension を配置",
        "pattern": r"(modifierExtension|extension.*未知|unknown extension|拡張.*未知)",
    },
    "extension-context-wrong-element-type": {
        "desc": "extension を許容されない element 型に配置",
        "pattern": r"(extension.*(context|not allowed|許可されて|未知))",
    },
    "extension-jp-known-but-empty-value": {
        "desc": "known JP extension に valueString 等が空",
        "pattern": r"(extension|拡張).*(未知|unknown|not.*defined|value.*(empty|欠落|missing)|ele-1)",
    },
    "extension-inside-modifierextension": {
        "desc": "modifierExtension 内に nested unknown extension",
        "pattern": r"(extension|拡張|modifierExtension).*(未知|unknown|not.*defined)",
    },
    "extension-with-known-url-both-value-and-nested": {
        "desc": "known extension URL で value + nested の両方",
        "pattern": r"(ext-1|extension.*(either|neither|both).*(value|nested))",
    },

    # === v7 fill-up: 追加 base cardinality ===
    "medicationdispense-medication-missing": {
        "desc": "MedicationDispense.medication[x] 必須欠落",
        "pattern": r"MedicationDispense\.medication\[x\].*(最小必要値.*1|minimum required.*1)",
    },
    "medicationdispense-subject-missing": {
        "desc": "MedicationDispense.subject 欠落 (実は 0..1 だが JP profile では 1)",
        "pattern": r"MedicationDispense\.subject.*(最小必要値.*1|minimum required.*1)",
    },
    "chargeitem-status-code-subject-missing": {
        "desc": "ChargeItem status/code/subject いずれか欠落",
        "pattern": r"ChargeItem\.(status|code|subject).*(最小必要値.*1|minimum required.*1)",
    },
    "bodystructure-patient-missing": {
        "desc": "BodyStructure.patient 必須欠落",
        "pattern": r"BodyStructure\.patient.*(最小必要値.*1|minimum required.*1)",
    },
    "communicationrequest-status-missing": {
        "desc": "CommunicationRequest.status 必須欠落",
        "pattern": r"CommunicationRequest\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "endpoint-invalid-status": {
        "desc": "Endpoint.status に enum 外の値",
        "pattern": r"(Endpoint\.status|endpoint-status).*(ValueSet|でなければ|is not (in|a valid)|に含まれていません)",
    },
    "patient-link-required-missing": {
        "desc": "Patient.link の other/type いずれか欠落",
        "pattern": r"Patient\.link\.(other|type).*(最小必要値.*1|minimum required.*1)",
    },
    "explanationofbenefit-no-required": {
        "desc": "ExplanationOfBenefit の複数必須欠落 (status/type/use/patient/created/insurer/provider/outcome/insurance)",
        "pattern": r"ExplanationOfBenefit\.(status|type|use|patient|created|insurer|provider|outcome|insurance).*(最小必要値.*1|minimum required.*1)",
    },
    "invoice-status-missing": {
        "desc": "Invoice.status 必須欠落",
        "pattern": r"Invoice\.status.*(最小必要値.*1|minimum required.*1)",
    },
    "person-inactive-valid": {
        "desc": "Person 有効な最小 - inactive リソースでも profile requires name/telecom 等",
        "pattern": r"Person\.(gender|birthDate|name).*(最小必要値.*1|minimum required.*1)|_gender",
    },

    # --- Tier 2 (Open slicing silent-pass) 分類の case ---
    # 詳細な分類 (benign 3 種 / violation 1 種) と背景は
    # validation-results/2026-07-23_jp_clins_migration_gate_verification/tier2-distribution-v31.md 参照
    "tier2-violation-codeable-slice-unmatched": {
        "desc": (
            "Tier 2-violation: Open slicing の CodeableConcept slice に data の "
            "discriminator が一致しない状態 (真の silent-pass)。JP-CLINS 検体検査 "
            "Observation.code に CoreLabo slice 用の JLAC 17 桁 code を持たず、"
            "LOINC-only で emit した pattern が代表。severity=information のみで "
            "error/warning は出ないため、この case は 「message が確かに出ている」 "
            "ことを assert する (silent-pass の再現)。JLAC 移行完了で Observation "
            "分の 2,523 resource が消え、DiagnosticReport / MedicationRequest / "
            "Condition.bodySite / Procedure 合計 375 resource は捉え続ける — "
            "message 頻度の低下を退行と誤読しないための記録 case。"
        ),
        "pattern": r"どの既知のスライスとも一致しません.*JP_Observation_LabResult_eCS|does not match any (known )?slice.*JP_Observation_LabResult_eCS",
        "expected_type": "info-only-pass",
    },
    "tier2-benign-multi-coding-category": {
        "desc": (
            "Tier 2-benign (a): Observation.category に JP_SimpleObservationCategory "
            "coding と HL7 base observation-category coding の両方を並置する data 設計。"
            "JP_Observation_Common profile 視点で HL7 base coding が unmatched information、"
            "HL7 vital-signs auto-profile 視点で JP coding が unmatched information と "
            "並行報告される。data 側の非準拠ではなく、両 profile の要求を意図的に両立 "
            "させた設計の副作用。この case は 「information のみで pass する」 = "
            "benign が誤って error/warning 化していないことを assert。"
        ),
        "pattern": r"どの既知のスライスとも一致しません.*(JP_Observation_Common|heartrate\|4\.0\.1|vitalsigns\|4\.0\.1)|does not match any (known )?slice.*(JP_Observation_Common|heartrate\|4\.0\.1|vitalsigns\|4\.0\.1)",
        "expected_type": "info-only-pass",
    },
    "vital-signs-auto-profile-active": {
        "desc": (
            "Positive control (PC1): HAPI validator が LOINC vital-sign code を "
            "含む Observation を検出したとき、明示 meta.profile 宣言がなくても "
            "HL7 base vital-signs profile (heartrate|4.0.1 等) を自動適用する挙動が "
            "有効であることの前提条件 check。auto-profile が無効化された場合、"
            "本 slug の pattern に該当する message が消え missing で FAIL する。"
            "Tier 2-benign 分類の 8,491 件が静かに消える failure mode の検出用。"
            "assert は 「profile URL が message に現れる」ことに絞ることで、"
            "同 Observation で並行報告される JP profile 由来 issue と切り分ける。"
        ),
        "pattern": r"defined in the profile http://hl7\.org/fhir/StructureDefinition/(heartrate|oxygensat|bp|bodytemp|resprate|vitalsigns)",
        "expected_type": "positive-control",
    },

    # --- Category-level positive controls (PC-A/B/D/E/F) ---
    # 各 category の検証機構が生きていることの前提条件確認。
    # case は test-cases/positive-controls/pc-<category>-*.ndjson に単独配置。
    # 他 case と同居させない (失敗時の切り分けを保つため)。
    "pc-a-cardinality-active": {
        "desc": (
            "Positive control (PC-A): base R4 cardinality check が生きている "
            "ことを、Observation.status を意図的に欠落させた最小 case で "
            "確認。この slug の発火 = A.cardinality カテゴリの検証機構が有効。"
            "発火しない場合、Observation profile 解決失敗 or validator 構成問題を疑う。"
        ),
        "pattern": r"Observation\.status.*(最小必要値.*1|minimum required.*1)",
        "expected_type": "positive-control",
    },
    "pc-b-invariant-active": {
        "desc": (
            "Positive control (PC-B): FHIRPath invariant 評価が生きている "
            "ことを、dom-6 (narrative missing) 相当の Best Practice が発火する "
            "case で確認。B.invariant-base の evaluator が生きている裏取り。"
        ),
        "pattern": r"dom-6.*narrative",
        "expected_type": "positive-control",
    },
    "pc-d-slice-eval-active": {
        "desc": (
            "Positive control (PC-D): slice 評価機構が生きていることを、"
            "既存 slice に intentionally 不一致な coding を持つ最小 case で "
            "確認。V1 (tier2-violation-codeable-slice-unmatched) と同居させず、"
            "独立 case で assert する。V1 が pass しても本 PC が missing なら "
            "slice 評価そのものが停止している。"
        ),
        "pattern": r"どの既知のスライスとも一致しません|does not match any (known )?slice",
        "expected_type": "positive-control",
    },
    "pc-e-terminology-lookup-active": {
        "desc": (
            "Positive control (PC-E): fhirserver への tx call が通っている "
            "ことを、LOINC の既知 code (2951-2 Sodium) の Wrong Display で "
            "確認。tx call が届けば Wrong Display Name error が発火する。"
            "この slug が missing = fhirserver 未接続 or HAPI_TX=n/a 運用中、"
            "その場合 E カテゴリの case 全てが無効化されているサイン。"
        ),
        "pattern": r"(Wrong Display Name|表示名.*正しくありません).*(2951-2|LOINC)",
        "expected_type": "positive-control",
    },
    # --- JP 層 case (依頼 B、C-1〜C-5、2026-07-24) ---
    # 公開リファレンスなし、fhir-jp-validator の付加価値領域

    # C-1: JP profile 独自 constraint (1 case、他 2 は SD 確認で不在と判明)
    "jp-observation-lab-value-type-restriction": {
        "desc": (
            "JP_Observation_LabResult_eCS が Observation.value[x] の型を "
            "[Quantity, CodeableConcept, string] に制限。data が valueRange を "
            "使うと 'valueRange の型が未知' error。base R4 では valueRange は "
            "許容だが JP profile で型を絞っている実例。"
        ),
        "pattern": r"(valueRange.*型.*未知|type.*(Range|valueRange).*(unknown|not.*valid|invalid)|value.*(Range|Ratio|Period).*not.*(allowed|permitted|valid))",
        "expected_type": "error-warning",
    },

    # C-2: profile 解決の silent no-op (優先度高)
    "unknown-profile-silent-no-op": {
        "desc": (
            "meta.profile に架空 URL を宣言した場合、HAPI は「Canonical URL "
            "解決不能」info と「URL は未知のため確認されていません」warning を "
            "出し、profile が要求するはずの構造 check は silent に skip する。"
            "本 case は挙動が変わったら (error 化 or 完全 silent 化) 即座に "
            "気づくための positive control。"
            "架空 URL は http://example.invalid/... で明示的に fake だと分かる形。"
        ),
        "pattern": r"(is not known to the FHIR validator|URL.*未知のため.*確認されて|Canonical URL.*解決できません|Canonical URL.*could not be resolved)",
        "expected_type": "positive-control",
    },

    # C-3: JP-CLINS Fixed/Pattern (3 case、slice 外の Fixed を狙う)
    "fixed-string-mismatch": {
        "desc": (
            "Composition.section の code.coding.display には patternString で "
            "日本語 fixed 値 (`紹介元情報セクション` 等) が定義されている。"
            "data が異なる文字列で emit すると pattern 不一致で error。"
        ),
        "pattern": r"(Wrong Display|表示名.*正しく|The display .*is not a valid.*|display.*(mismatch|一致しません|不一致)|section.*title.*not|pattern.*not.*match|patternString)",
        "expected_type": "error-warning",
    },
    "fixed-code-mismatch": {
        "desc": (
            "profile の Fixed value / patternCoding で code が指定されている "
            "要素に別 code を emit した場合の error。実測では 'system X で "
            "未知のコード Y' として発火することが多い (Fixed slice の system 内で "
            "未定義 code 扱い)。"
        ),
        "pattern": r"(system.*で未知のコード|Unknown code.*in.*CodeSystem|fixed value|Fixed value|patternCoding|is not a valid.*code)",
        "expected_type": "error-warning",
    },
    "pattern-codeableconcept-mismatch": {
        "desc": (
            "Practitioner.qualification.code の patternCodeableConcept 制約に "
            "反する CodeableConcept を emit した場合の error。"
        ),
        "pattern": r"(patternCodeableConcept|slice.*qualification|pattern-value.*not match|pattern.*(一致|match))",
        "expected_type": "error-warning",
    },

    # C-4: 階層 CS descendent-of (Gate 1 で実測済)
    "descendent-of-vs-expansion": {
        "desc": (
            "JLAC10 CoreLabo CS は hierarchyMeaning=is-a の階層 CS。ValueSet "
            "は descendent-of フィルタで子 code のみを含む (自己除外)。data が "
            "親 code (WBC 等) を使うと VS 範囲外で error。Gate 1 (2026-07-23) "
            "で実測: 親 `K` `WBC` は VS に含まれない、子 17 桁 code が正解。"
            "tx 必須 (HAPI_TX=n/a では発火せず)。"
        ),
        "pattern": r"(is not in the value set|ValueSet.*に含まれていません|コード.*ValueSet.*外|not.*in.*value.*set)",
        "expected_type": "error-warning",
    },

    # C-5: Tier 3 散文規定 (4 機構、各 compliant/violation ペアで case 8 本)
    # expected_type=record-only-spec-not-encoded で reconcile は逆判定
    # (発火しないほうが PASS、将来検出化されたら FAIL で alarm)
    "prose-half-width-katakana-display": {
        "desc": (
            "Tier 3 散文規定: display / text に半角カタカナを含めてはならない "
            "(JP_Observation_LabResult_eCS の comment 記述、FHIR spec に "
            "符号化されていない)。HAPI は文字種 check を実装しないため、"
            "違反 data を渡しても error 0 が正常。custom check 実装時に発火 "
            "するようになれば本 slug が FAIL 化し、実装完了を検出できる。"
        ),
        "pattern": r"(半角カタカナ|half.?width|prose-charset|character.*(class|type).*(violation|invalid))",
        "expected_type": "record-only-spec-not-encoded",
    },
    "prose-localcode-with-space": {
        "desc": (
            "Tier 3 散文規定: LocalCode の display に空白を含めてはならない "
            "(なるべく長い文字列名称推奨)。HAPI 未検出。"
        ),
        "pattern": r"(LocalCode.*space|LocalCode.*空白|prose-code-format)",
        "expected_type": "record-only-spec-not-encoded",
    },
    "prose-designated-labtest-no-jlac": {
        "desc": (
            "Tier 3 散文規定: 指定検査 43 項目に該当する検体検査には "
            "JLAC10/11 CoreLabo code が必須。data が LocalCode のみで JLAC 無し "
            "でも HAPI は error 化しない (指定検査項目リストと突き合わせる "
            "custom check なし)。"
        ),
        "pattern": r"(指定検査.*JLAC|designated.*labtest|prose-coding-rules)",
        "expected_type": "record-only-spec-not-encoded",
    },
    "prose-hasmember-in-5info-mode": {
        "desc": (
            "Tier 3 散文規定: 電子カルテ情報共有サービス 5 情報送信時、"
            "Observation.hasMember は使用禁止。HAPI は「5情報送信 mode」の "
            "概念を validation context として持たず、hasMember が存在しても "
            "error 化しない。"
        ),
        "pattern": r"(hasMember.*(5情報|not allowed|禁止)|prose-usage-condition)",
        "expected_type": "record-only-spec-not-encoded",
    },

    "pc-f-reference-eval-active": {
        "desc": (
            "Positive control (PC-F): Reference target type 制約評価が生きて "
            "いることを、Encounter.subject に Practitioner (許容型外) を "
            "参照させた最小 case で確認。HAPI は single-resource validation "
            "でも Reference target type 制約を profile ベースで evaluate する "
            "ため、observable。Reference resolution (Bundle 内 resolve) は "
            "single-resource mode で発火しないためここでは使わない。"
        ),
        "pattern": r"タイプ\s*'Practitioner'\s*は.*有効なターゲットではありません|Reference.*Practitioner.*not.*valid.*target|is not a valid target.*Practitioner",
        "expected_type": "positive-control",
    },
}

# --- Historical consolidation note (2026-07-24) -----------------------------
# reference-target-* を resource type 別に 15 slug 定義していた
# (reference-target-encounter-subject-practitioner ... reference-target-
# medstatement-subject-practitioner) が、いずれも case で使われず、既存 16 case
# は全て generic slug `reference-type-mismatch` を使用していた。sweep 検証で
# 「機構は 1 つ (Reference.targetProfile 照合) で resource type に依存しない」
# ことを確認したため、15 slug を集約削除した (`reference-target-profile-
# mismatch` は F.reference-target-profile カテゴリの別機構のため残す)。
#
# resource type 別に分けた当初の判断は「Reference target は resource type
# ごとに挙動が違うのでは」という懸念に基づくものと推定される。実測で
# `reference-type-mismatch` の pattern が全 resource type で match することが
# 確認済のため、resource type ごとの slug は不要。resource type 別網羅は
# case ファイル側 (16 個の別 data) で行えば十分。
#
# 将来、resource type 依存の Reference target 挙動が発見された場合のみ、
# 該当 slug を追加する。resource type 別に slug を増やすアプローチには
# 戻らないこと。
# ----------------------------------------------------------------------------


def slug_exists(slug: str) -> bool:
    return slug in EXPECTED_ISSUES


def pattern_for(slug: str):
    entry = EXPECTED_ISSUES.get(slug)
    if not entry:
        return None
    return re.compile(entry["pattern"], re.IGNORECASE)
