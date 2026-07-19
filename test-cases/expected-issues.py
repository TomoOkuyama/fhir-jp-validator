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
        "desc": "Patient.deceased[x] の複数型指定 (choice violation)",
        "pattern": r"(deceased.*(2|multiple).*value|deceased.*(only|複数.*禁止)|One or more elements are unrecognized.*deceased|Cannot have more than one value.*deceased|value\[x\].*deceased)",
    },
    "patient-multiple-multiplebirth": {
        "desc": "Patient.multipleBirth[x] の複数型指定",
        "pattern": r"(multipleBirth.*(2|multiple).*value|Cannot have more than one value.*multipleBirth|value\[x\].*multipleBirth)",
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
        "desc": "Reference 全 element 空 (ref-1)",
        "pattern": r"(ref-1|Reference.*(reference|identifier|display).*(any|either|いずれか)|SHALL have a contained resource|At least one of|SHALL have.*(reference|identifier|display))",
    },
    "coding-empty": {
        "desc": "Coding が完全に空",
        "pattern": r"(Coding.*(empty|空)|ele-1.*Coding|Coding.*(children|@value))",
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
    "reference-target-encounter-subject-practitioner": {
        "desc": "Encounter.subject が Practitioner (許容型外)",
        "pattern": r"(Encounter\.subject|resource\.subject).*(Practitioner|valid target|有効なターゲット|profile violates|not.*type|型.*不一致)|Reference.*Practitioner.*not.*valid|target.*Encounter\.subject",
    },
    "reference-target-immunization-patient-org": {
        "desc": "Immunization.patient が Organization (許容型外)",
        "pattern": r"(Immunization\.patient|resource\.patient).*(Organization|valid target|有効なターゲット)|target.*Immunization\.patient",
    },
    "reference-target-coverage-beneficiary-practitioner": {
        "desc": "Coverage.beneficiary が Practitioner (許容型外)",
        "pattern": r"Coverage\.beneficiary.*(Practitioner|valid target|有効なターゲット)|target.*Coverage\.beneficiary",
    },
    "reference-target-medadmin-subject-org": {
        "desc": "MedicationAdministration.subject が Organization (許容型外)",
        "pattern": r"MedicationAdministration\.subject.*(Organization|valid target|有効なターゲット)|target.*MedicationAdministration\.subject",
    },
    "reference-target-condition-subject-endpoint": {
        "desc": "Condition.subject が Endpoint (許容型外)",
        "pattern": r"Condition\.subject.*(Endpoint|valid target|有効なターゲット)|target.*Condition\.subject",
    },
    "reference-target-diagnosticreport-subject-practitioner": {
        "desc": "DiagnosticReport.subject が Practitioner (許容型外)",
        "pattern": r"DiagnosticReport\.subject.*(Practitioner|valid target|有効なターゲット)|target.*DiagnosticReport\.subject",
    },
    "reference-target-allergyintolerance-patient-location": {
        "desc": "AllergyIntolerance.patient が Location (許容型外)",
        "pattern": r"AllergyIntolerance\.patient.*(Location|valid target|有効なターゲット)|target.*AllergyIntolerance\.patient",
    },
    "reference-target-servicerequest-subject-practitioner": {
        "desc": "ServiceRequest.subject が Practitioner (許容型外)",
        "pattern": r"ServiceRequest\.subject.*(Practitioner|valid target|有効なターゲット)|target.*ServiceRequest\.subject",
    },
    "reference-target-careplan-subject-location": {
        "desc": "CarePlan.subject が Location (許容型外)",
        "pattern": r"CarePlan\.subject.*(Location|valid target|有効なターゲット)|target.*CarePlan\.subject",
    },
    "reference-target-goal-subject-endpoint": {
        "desc": "Goal.subject が Endpoint (許容型外)",
        "pattern": r"Goal\.subject.*(Endpoint|valid target|有効なターゲット)|target.*Goal\.subject",
    },
    "reference-target-medreq-subject-practitioner": {
        "desc": "MedicationRequest.subject が Practitioner (許容型外)",
        "pattern": r"MedicationRequest\.subject.*(Practitioner|valid target|有効なターゲット)|target.*MedicationRequest\.subject",
    },
    "reference-target-documentreference-subject-practitioner": {
        "desc": "DocumentReference.subject が Practitioner (許容型外)",
        "pattern": r"DocumentReference\.subject.*(Practitioner|valid target|有効なターゲット)|target.*DocumentReference\.subject",
    },
    "reference-target-composition-subject-coverage": {
        "desc": "Composition.subject が Coverage (許容型外)",
        "pattern": r"Composition\.subject.*(Coverage|valid target|有効なターゲット)|target.*Composition\.subject",
    },
    "reference-target-encounter-participant-patient": {
        "desc": "Encounter.participant.individual が Patient (許容型外)",
        "pattern": r"Encounter\.participant.*(Patient|valid target|有効なターゲット)|target.*Encounter\.participant",
    },
    "reference-target-medstatement-subject-practitioner": {
        "desc": "MedicationStatement.subject が Practitioner (許容型外)",
        "pattern": r"MedicationStatement\.subject.*(Practitioner|valid target|有効なターゲット)|target.*MedicationStatement\.subject",
    },

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
}


def slug_exists(slug: str) -> bool:
    return slug in EXPECTED_ISSUES


def pattern_for(slug: str):
    entry = EXPECTED_ISSUES.get(slug)
    if not entry:
        return None
    return re.compile(entry["pattern"], re.IGNORECASE)
