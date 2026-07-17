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
        "desc": "modifierExtension が未知で無視できない",
        "pattern": r"(modifierExtension.*(未知|unknown|cannot be ignored|must be recognized)|Unknown modifierExtension|変更子拡張.*(未知|unknown))",
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
}


def slug_exists(slug: str) -> bool:
    return slug in EXPECTED_ISSUES


def pattern_for(slug: str):
    entry = EXPECTED_ISSUES.get(slug)
    if not entry:
        return None
    return re.compile(entry["pattern"], re.IGNORECASE)
