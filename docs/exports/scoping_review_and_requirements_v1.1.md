Clinical Information Requirements for a Conversational AI Agent Undertaking Preoperative Patient History

__Scoping Review Protocol and Requirements Specification__

Working document | Version 0\.1 | 26 September 2026

__Purpose\. __This document establishes a proposed scoping review methodology and translates the emerging evidence base into an initial clinical, conversational, safety and software requirements framework for a patient\-facing AI agent that takes a preoperative history\. The intended role is to collect, clarify, reconcile, structure and summarise patient\-reported information for subsequent clinician review, not to replace clinician\-led pre\-anaesthesia assessment\.

# 1\. Background and rationale

Preoperative assessment requires a broad set of clinical, functional, medication, anaesthetic, psychosocial and patient\-preference information\. The published literature is heterogeneous: previous work has identified hundreds of candidate preoperative data items with limited agreement on a universal dataset\. More recent reviews continue to show variation in how pre\-anaesthesia assessment is organised and delivered\.

Conversational AI creates an opportunity to obtain this information dynamically rather than through a fixed questionnaire\. However, emerging perioperative AI studies also demonstrate clinically important risks, particularly omission of significant information, unsupported assertions and reduced reliability as patient complexity increases\. The design problem is therefore not simply whether an LLM can conduct a plausible interview, but how to ensure that mandatory information is reliably resolved, uncertainty is preserved, discrepancies are surfaced and clinicians remain responsible for assessment and decision\-making\.

The proposed system should therefore be based on an evidence\-derived clinical information model and deterministic completeness and safety rules, with an LLM used primarily for natural\-language interaction\.

# 2\. Review objectives

## 2\.1 Primary review question

What patient\-reported information should a conversational AI system systematically elicit to provide a safe, comprehensive and clinically useful preoperative history for adults undergoing surgery or procedures requiring anaesthesia or sedation?

## 2\.2 Secondary questions

1. Which information is universally required and which should be conditionally elicited?
2. Which validated perioperative screening or risk instruments can be derived from conversational history?
3. Which findings require immediate escalation, clinician review, optimisation or further investigation?
4. What safety, usability, governance and software requirements arise when history\-taking is performed by conversational AI rather than a clinician or conventional questionnaire?

# 3\. Intended scope

Initial scope: adults aged 18 years and older undergoing elective or semi\-elective surgery or procedures requiring general anaesthesia, regional anaesthesia, monitored anaesthesia care or procedural sedation\.

Initial exclusions: paediatrics, obstetrics and immediate emergency surgery\. These populations should be considered for subsequent dedicated modules because they introduce materially different clinical and communication requirements\.

## 3\.1 Intended function

A patient\-facing conversational system for collection, clarification, reconciliation, structuring and summarisation of the preoperative history to support subsequent assessment and decision\-making by appropriately qualified clinicians\.

## 3\.2 Functions outside the initial intended use

- Autonomous determination that a patient is fit or cleared for surgery\.
- Autonomous anaesthetic planning\.
- Autonomous ASA Physical Status classification\.
- Autonomous medication cessation or modification unless delivered through a separately governed deterministic protocol\.
- Replacement of physical examination\.
- Replacement of clinician\-led consent or shared decision\-making\.

# 4\. Review methodology

A PRISMA\-ScR aligned scoping review is proposed because the objective is to map clinical concepts, information requirements, validated instruments, guidelines and implementation evidence rather than estimate a single intervention effect\.

## 4\.1 Information sources

- MEDLINE/PubMed
- Embase
- CINAHL
- Cochrane Library
- Scopus
- Web of Science
- IEEE Xplore and ACM Digital Library for conversational AI, clinical NLP and LLM literature
- Grey literature and professional guidance from ANZCA, ASA, ESAIC, RCoA/CPOC, Association of Anaesthetists, ACC/AHA, Society of Anesthesia and Sleep Medicine, ERAS Society, ESPEN and relevant Australian safety and regulatory bodies

## 4\.2 Proposed date ranges

- General preoperative assessment literature: 1995 to September 2026\.
- Conversational AI and LLM literature: 2018 to September 2026\.
- Earlier seminal studies identified through backward citation searching may be included\.

## 4\.3 Search concepts

The core search will combine preoperative/pre\-anaesthetic terminology with assessment, evaluation, history\-taking, screening, questionnaire and interview concepts, together with anaesthesia and surgery terms\. Targeted searches will then address AI/conversational agents and individual clinical domains\.

- Artificial intelligence, conversational agent, chatbot, large language model, natural language processing, digital questionnaire and patient\-reported assessment\.
- Cardiovascular disease and functional capacity\.
- Respiratory disease and obstructive sleep apnoea\.
- Frailty, cognition and delirium\.
- Nutrition and anaemia/patient blood management\.
- Diabetes and perioperative medication management\.
- Anticoagulation, antiplatelet therapy and bleeding\.
- Allergy and previous perioperative hypersensitivity\.
- Previous anaesthesia, difficult airway and malignant hyperthermia\.
- Smoking, alcohol and other substances\.
- Chronic pain and opioid use\.
- Shared decision\-making, goals of care and discharge planning\.

# 5\. Evidence hierarchy

Each requirement should retain evidence provenance\. A proposed hierarchy is:

Level

Evidence source

A

Regulatory or professional requirement, e\.g\. ANZCA, ASA, TGA, NSQHS

B

Evidence\-based clinical guideline, e\.g\. ESAIC, ACC/AHA, SASM, ESPEN, CPOC

C

Validated clinical instrument, e\.g\. DASI, STOP\-Bang, AUDIT\-C

D

Systematic review or meta\-analysis

E

Primary clinical study

F

Expert consensus or established clinical practice

G

Design or safety requirement derived during system engineering

# 6\. Proposed clinical information model

The review should extract every candidate concept into a master clinical dataset\. The patient\-facing conversation may be short and adaptive, while the underlying dataset can contain several hundred atomic concepts\.

Domain

Examples

Patient and context

Identity, communication needs, procedure, indication, site/laterality, timing and source of history

Patient concerns and priorities

Patient\-identified concerns, expectations and information needs

Present health

Current illness, recent deterioration, infection and recent hospitalisation

Cardiovascular

Hypertension, IHD, heart failure, arrhythmia, valvular disease, devices and symptoms

Functional capacity

Activities, exertional limitation and DASI\-compatible inputs

Respiratory

Asthma, COPD, respiratory infection, oxygen therapy and current symptoms

Sleep

OSA diagnosis, PAP therapy and STOP\-Bang\-compatible inputs

Neurological

Stroke/TIA, epilepsy, neuromuscular disease, deficits and cognitive disease

Renal

CKD, dialysis, AKI and relevant fluid/electrolyte issues

Endocrine/metabolic

Diabetes, insulin/devices, thyroid, adrenal and chronic steroid exposure

Gastrointestinal/hepatic

Reflux, dysphagia, aspiration risk, gastroparesis and liver disease

Haematological

Anaemia, bleeding, thrombosis, transfusion and blood\-product preferences

Previous surgery and anaesthesia

Prior techniques, difficult airway, PONV, awareness, delayed emergence and complications

Family anaesthetic history

Malignant hyperthermia, prolonged paralysis/apnoea and unexplained peri\-anaesthetic death

Airway and dental

Prior airway difficulty, mouth/neck/jaw issues and vulnerable dentition

Medication

Complete reconciliation including prescription, OTC, supplements and high\-risk classes

Allergy/adverse reaction

Agent, reaction phenotype, severity, timing, treatment and subsequent exposure

Physiological reserve

Nutrition, frailty, cognition, mobility and functional independence

Lifestyle and psychosocial

Smoking/vaping, alcohol, other substances, mental health and anxiety

Pain

Chronic pain, analgesics, opioid exposure and previous postoperative pain problems

Social and recovery

Home environment, carers, transport, escort, supports and discharge barriers

Goals and preferences

What matters to the patient, advance care planning and treatment limitations

Reproductive considerations

Pregnancy possibility, breastfeeding and relevant reproductive therapies where clinically appropriate

# 7\. Atomic concept specification

Each clinical concept should be represented as an individually testable requirement rather than merely a field name\. Example:

Property

Example: Heart failure

Concept ID

CV\-014

Domain

Cardiovascular

Universal question?

Yes

Trigger

All patients

Initial wording

Have you ever been told you have heart failure or a weak heart?

Recognised lay terms

Cardiac failure, CHF, weak heart

Positive follow\-up

Diagnosis, timing, cause and treatment

Severity

LVEF if known

Current status

Stable, improving or worsening

Symptoms

Exertional dyspnoea, orthopnoea, PND and oedema

Recent events

Admission or decompensation

Source

Patient, carer, EMR, medication record or previous anaesthetic record

Information state

Confirmed, uncertain, incomplete, conflicting etc\.

Escalation

Active or worsening symptoms require clinician review

AI inference permitted?

No autonomous diagnostic inference

Clinician verification

Required if positive

Evidence

Linked guideline/study references

# 8\. Mandatory core and conditional branching

Every data item should be classified according to when it must be resolved:

Class

Definition

M0

Mandatory universal: must be resolved in every interview\.

M1

Mandatory where applicable, e\.g\. reproductive or age\-related screening\.

C1

Condition\-triggered, e\.g\. heart failure activates symptom and severity questions\.

C2

Procedure\-triggered, e\.g\. higher\-risk surgery activates additional assessment\.

C3

Medication\-triggered, e\.g\. an SGLT2 inhibitor activates diabetes/medication logic\.

C4

Demographic or risk\-triggered, e\.g\. age/frailty activates cognition and delirium screening\.

O

Optional or contextual\.

# 9\. Validated instruments

Where possible, the system should collect inputs for established instruments rather than create novel AI\-derived scores\. Candidate instruments include STOP\-Bang, DASI, AUDIT\-C, Clinical Frailty Scale or alternative validated frailty tools, Mini\-Cog where appropriate, validated nutritional screening, Apfel PONV score, RCRI inputs, ARISCAT inputs and oral morphine equivalent calculations\.

Collection of score inputs should be distinguished from authority to interpret or act upon the resulting score\. A system may collect and calculate a score while still requiring clinician interpretation\.

# 10\. Proposed system architecture

A hybrid architecture is recommended\. The LLM should control natural\-language understanding and how questions are phrased, while a deterministic clinical state and requirements engine controls which information must be resolved\.

__Patient__

↓

Conversational interface

↓

LLM layer: understanding and natural dialogue

↓

__Clinical state engine ↔ EMR reconciliation__

↓

__Requirements engine: missing data | conflicts | trigger rules__

↓

__Safety engine__

↓

Structured clinical dataset

↓

Clinician\-facing summary

↓

__Clinician__

# 11\. Information\-state model

No clinical concept should be represented simply as yes/no\. Each should retain value, status, source, timestamp, confidence and verification status\.

- CONFIRMED\_PRESENT
- CONFIRMED\_ABSENT
- PATIENT\_UNSURE
- NOT\_KNOWN
- NOT\_ASKED
- NOT\_APPLICABLE
- INCOMPLETE
- CONFLICTING
- DECLINED
- REQUIRES\_CLINICIAN\_REVIEW

Key safety principle: 'patient does not know', 'not mentioned' and 'not asked' must never be converted into a negative finding\.

# 12\. Core safety requirements

__REQ\-SAF\-001: __The system SHALL NOT generate a negative clinical assertion unless the underlying concept has been explicitly resolved by patient response or another identified authoritative source\.

__REQ\-SAF\-002: __The system SHALL retain contradictory clinical information rather than silently reconcile it\.

__REQ\-SAF\-003: __The system SHALL retain provenance for clinically relevant assertions\.

__REQ\-SAF\-004: __The system SHALL identify mandatory high\-risk concepts that remain incomplete before interview completion\.

__REQ\-SAF\-005: __The system SHALL support explicit patient uncertainty and refusal without coercing a binary response\.

__REQ\-SAF\-006: __The system SHALL require clinician review before the output is treated as a completed pre\-anaesthetic assessment\.

# 13\. Contradiction handling

The system should surface rather than resolve discrepancies\. Example: if a patient reports no cardiac disease while an existing record documents dilated cardiomyopathy with reduced LVEF, both assertions should be retained with their sources and a clinician\-verification flag generated\.

# 14\. Medication reconciliation subsystem

Medication collection should progressively establish name, active ingredient, dose, formulation, route, frequency, indication, last dose, adherence, recent changes and source\. The system should deliberately probe for commonly omitted therapies including insulin, injections, inhalers, patches, anticoagulants, antiplatelets, steroids, biologics, chemotherapy, contraceptives/HRT, supplements, herbal products, over\-the\-counter medicines and weight\-loss therapies\.

Perioperative medication knowledge and management rules should be versioned separately from the LLM\. The LLM should not act as the authoritative source for medication cessation or continuation instructions\.

# 15\. Escalation framework

Escalation criteria should be explicit, version\-controlled and auditable rather than generated through unconstrained LLM reasoning\.

## 15\.1 Red: potentially prompt clinician assessment

- Current or rest chest pain\.
- Severe or new dyspnoea\.
- Recent concerning syncope\.
- Recent stroke or TIA\.
- Severe uncontrolled respiratory symptoms\.
- Current serious infection or major recent deterioration\.
- History suggesting severe perioperative hypersensitivity or malignant hyperthermia susceptibility\.
- Potentially unsafe anticoagulant or antiplatelet issue\.
- Inability to establish essential medication or clinical information\.

## 15\.2 Amber: clinician review or optimisation

- Poor functional capacity\.
- Suspected obstructive sleep apnoea\.
- Anaemia\.
- Frailty, cognitive vulnerability or malnutrition\.
- Poorly controlled diabetes\.
- Chronic opioid use\.
- Recent respiratory infection\.
- Problematic alcohol use\.
- Previous severe postoperative nausea and vomiting\.
- Social or discharge barriers\.

# 16\. Conversational requirements

- Begin with an open\-ended invitation and allow the patient to identify concerns\.
- Ask one concept at a time where practical\.
- Recognise common lay terminology and explain unfamiliar medical terms\.
- Avoid unnecessary jargon and judgemental wording\.
- Allow 'I don't know', uncertainty and refusal\.
- Avoid repeatedly asking information already supplied\.
- Use sensitive transitions for alcohol, drugs, mental health and reproductive questions\.
- Distinguish patient, proxy and imported\-source information\.
- Support interpreter, accessibility and communication needs\.
- Recognise when conversational interaction is failing and provide an alternative pathway\.
- Periodically summarise and allow correction\.
- Conclude with a patient confirmation step and a final open question about anything important not yet discussed\.

# 17\. Patient confirmation

Before completion, the agent should present a concise patient\-readable summary and ask the patient to correct misunderstandings\. A final open\-ended question should invite disclosure of any important health, medication, surgery or anaesthesia information not already covered\.

# 18\. Clinician\-facing output

The default clinician view should be a structured summary rather than a transcript\. It should prioritise perioperative issues, incomplete or conflicting information and provenance\.

- Procedure and context\.
- Key perioperative issues and escalation flags\.
- System\-based medical history and current stability\.
- Functional capacity and relevant validated instrument inputs/scores\.
- Previous anaesthetic and family anaesthetic history\.
- Medication and allergy reconciliation\.
- Frailty, cognition, nutrition, pain and psychosocial factors where relevant\.
- Social/discharge issues\.
- Patient priorities and goals\.
- Explicit incomplete, uncertain or conflicting data\.
- Data provenance and interview timestamp\.
- Access to the full transcript/audit trail when required\.

# 19\. AI\-specific safety constraints

__SAF\-01: __No autonomous clearance for surgery\.

__SAF\-02: __No autonomous anaesthetic plan\.

__SAF\-03: __No autonomous medication cessation/change unless delivered by a separately governed deterministic protocol\.

__SAF\-04: __Mandatory clinician review\.

__SAF\-05: __Mandatory high\-risk dataset completion check\.

__SAF\-06: __Explicit representation of missing data\.

__SAF\-07: __Source provenance\.

__SAF\-08: __Contradiction preservation\.

__SAF\-09: __Full audit trail\.

__SAF\-10: __Model and knowledge\-base version logging\.

__SAF\-11: __Deterministic escalation rules\.

__SAF\-12: __Fail\-safe behaviour when the LLM or integration is unavailable\.

__SAF\-13: __No unlabelled diagnostic inference from ambiguous patient language\.

__SAF\-14: __Patient correction mechanism\.

__SAF\-15: __Clinician override with reason capture\.

# 20\. Australian clinical governance and regulatory considerations

Clinical implementation should occur within the organisation's clinical governance, digital health, privacy, cybersecurity, safety and quality frameworks\. The intended use and claims made for the software will materially influence whether it falls within Australian medical device regulation\. The narrow initial function should therefore remain collection, clarification, structuring, flagging and summarisation with clinician verification\.

Development should include formal clinical risk assessment, software lifecycle controls, model and prompt/version management, change control, validation after material updates, auditability, privacy\-by\-design, cybersecurity review, equity/accessibility assessment and defined accountability for clinical content\.

# 21\. Evaluation framework

The primary evaluation outcome should focus on safety and clinical completeness rather than usability alone\.

__Proposed primary outcome: __Proportion of clinically important preoperative information captured compared with a reference\-standard clinician assessment, with separate analysis of critical omissions\.

## 21\.1 Secondary outcomes

- Critical omission rate\.
- False\-positive clinical assertions\.
- Unsupported negative assertions\.
- Contradiction detection performance\.
- Medication reconciliation completeness\.
- Allergy characterisation completeness\.
- Validated\-score input completeness\.
- Interview duration and abandonment rate\.
- Clinician review time\.
- Number and type of clinician corrections\.
- Patient and clinician acceptability\.
- Patient comprehension\.
- Accessibility and equity\.
- Performance stratified by age, language, health literacy, frailty, clinical complexity/ASA class and surgical specialty\.

# 22\. Proposed development outputs

Output

Purpose

A\. Scoping Review

Academic evidence synthesis using PRISMA\-ScR methodology\.

B\. Evidence Matrix

Source × clinical domain × recommendation × evidence strength\.

C\. Perioperative Clinical Dataset v1\.0

Atomic data elements, definitions, provenance, mandatory status and evidence\.

D\. Conversational Clinical Logic Specification

Question triggers, branching, clarification, completion criteria, contradiction handling and escalation\.

E\. Clinical Safety and Software Requirements Specification

Functional and non\-functional requirements, AI constraints, human oversight, auditability, security, validation and governance\.

# 23\. Proposed development pathway

__Literature search and scoping review__

↓

__Evidence matrix__

↓

__Clinical Dataset v1\.0__

↓

__Conversation logic and safety rules__

↓

__Requirements specification__

↓

__Prototype__

↓

__Retrospective/simulated validation__

↓

__Prospective silent trial__

↓

__Clinician\-supervised patient pilot__

# 24\. Immediate next work package

The next work package should develop the full review protocol and extraction framework\. This should include database\-specific search strategies, inclusion and exclusion criteria, screening rules, PRISMA\-ScR reporting plan, critical appraisal approach where appropriate and a structured extraction table designed to translate each source into atomic clinical and software requirements\.

Following protocol finalisation, searches should be conducted domain by domain and used to populate the Perioperative Conversational AI Clinical Dataset v1\.0\. This approach provides a traceable pathway from published evidence to conversation logic, safety controls, prototype design and subsequent clinical validation\.

# 25\. Key sources identified in preliminary review

- Australian and New Zealand College of Anaesthetists \(ANZCA\)\. PG07: Guideline on pre\-anaesthesia consultation and patient preparation\. 2024\.
- American Society of Anesthesiologists\. Basic Standards for Preanesthesia Care\.
- Recent scoping review of adult pre\-anaesthesia assessment models and processes \(2026\)\.
- Systematic review of preoperative assessment data items identifying substantial heterogeneity in reported datasets\.
- Consensus work defining a core preoperative dataset\.
- Society of Anesthesia and Sleep Medicine guideline on preoperative screening and assessment of obstructive sleep apnoea\.
- 2024 ACC/AHA guideline for perioperative cardiovascular management for noncardiac surgery\.
- Centre for Perioperative Care guidance on frailty and perioperative anaemia\.
- European Society of Anaesthesiology and Intensive Care guideline on postoperative delirium\.
- PATCH digital pre\-anaesthesia assessment study\.
- ePAQ electronic preoperative assessment literature\.
- AI\-DOCS conversational LLM preoperative history\-taking feasibility study \(2026\)\.
- Recent literature addressing safety and reliability of LLMs and AI chatbots in perioperative assessment\.
- Australian Government and Therapeutic Goods Administration guidance concerning artificial intelligence and software\-based medical devices\.

# 26\. Expanded architecture, interoperability and future capability requirements

The following requirements are incorporated into the project scope and should be treated as part of the target architecture\. They are not all required for the first deployable MVP, but the MVP must avoid design choices that prevent their later implementation\.

## Clinical Interview Process Model

- Treat clinical interviewing as a separate design layer from the clinical information model and rules engine\. The agent must reproduce core clinical interviewing behaviours rather than operate as a sequence of database questions\.
- Use repeated open\-to\-closed micro\-funnels: open narrative invitation, active listening and extraction, focused clarification, structured characterisation, safety screening, summary confirmation and signposted transition\.
- Support interview modes including narrative discovery, open domain exploration, focused clarification, structured characterisation, safety screening, sensitive enquiry, reconciliation, summary confirmation, transition and closure\.
- Active listening requirements include allowing narrative completion, extracting multiple facts from one answer, recognising clinical and emotional cues, selective reflection, clarification, periodic summarisation, invitation to correct and avoidance of repetitive questioning\.
- Maintain both a clinical agenda and patient agenda\. Patient concerns, expectations, fears and recovery priorities must be captured and revisited before closure\.
- Implement a cue stack that can interrupt the planned interview for safety\-critical, clinically salient or emotional disclosures\. The agent should explore the cue before returning to the prior thread\.
- Use explicit signposting when moving between major domains, including a brief reason for clinically unexpected transitions where useful\.
- Use summary checks as a safety mechanism\. Patient confirmation, correction and additions should be recorded as provenance\-bearing information events\.
- Use sensitive, non\-judgemental framing for alcohol, substance use, mental health, reproductive health, weight and social circumstances\.
- End substantial domains with an opportunity to add information and end the assessment with a final open question plus unresolved\-item review\.

## FHIR and Australian interoperability

- FHIR alignment is a design requirement, not a downstream export function\. The internal perioperative semantic model should remain optimised for clinical reasoning while every externally meaningful concept has a defined FHIR mapping\.
- Target the Australian interoperability environment, including AU Core/AU Base and AUCDI where applicable, with SNOMED CT\-AU for clinical terminology and Australian Medicines Terminology \(AMT\) for medicines\.
- Maintain mappings from canonical objects to appropriate FHIR resources, including Patient, Encounter, ServiceRequest, Condition, Observation, MedicationStatement, Medication, AllergyIntolerance, Procedure, FamilyMemberHistory, Goal, Consent, DocumentReference, RiskAssessment, Task, DetectedIssue/Flag and Provenance as appropriate\.
- Represent the computable interview using FHIR Questionnaire and QuestionnaireResponse, with Structured Data Capture\-compatible logic where feasible\. Preserve the question wording and response separately from clinical facts extracted from the response\.
- Retain source\-level provenance from question/answer through extracted clinical facts, normalisation, patient confirmation, clinician verification and any subsequent write\-back\.
- Support FHIR\-based workflow actions such as record retrieval, investigation requests, optimisation referrals and unresolved\-item tracking using Task/ServiceRequest and related resources\.
- Design for SMART on FHIR launch and contextual integration where supported\. Consider CDS Hooks or equivalent event\-driven mechanisms later for reassessment after new results, medication changes or other relevant events\.
- Use a terminology service rather than static lookup tables so synonyms, hierarchy, subsumption, code\-system versions and terminology updates can be governed centrally\.
- Version the FHIR profiles, terminology releases, clinical rules and mapping specifications used for every assessment so an assessment can be reproduced and audited\.

## Extended functional opportunities

- Pre\-interview synthesis: assemble available EMR/FHIR information before speaking with the patient, identify what is already resolved, detect conflicts and create an information\-gap map that drives the interview\.
- Longitudinal perioperative state: treat assessment as a living pathway from referral through optimisation, surgery and recovery rather than a one\-off form\.
- Clinical data\-quality engine: detect and route discrepancies in allergies, medicines, diagnoses, smoking status, advance care documents and other material facts rather than merely documenting them\.
- Automated record retrieval: safety\-critical patient reports such as previous difficult airway, perioperative anaphylaxis, awareness or unexplained prolonged ventilation should be able to create trackable retrieval tasks\.
- Preassessment triage: use structured information and deterministic rules to route patients to streamlined pathways, nurse review, anaesthetist review, physician, pharmacist or multidisciplinary assessment\.
- Dynamic investigation and optimisation workflow: identify missing or stale required information and generate governed tasks/referrals for investigations, anaemia management, diabetes optimisation, smoking cessation, alcohol support, nutrition, frailty, exercise/prehabilitation, pain and psychological support\.
- Patient preparation assistant: after clinician\-approved assessment, provide rules\-derived preparation instructions, outstanding tasks, appointments, CPAP/device reminders, fasting and medication instructions, transport and escort requirements without allowing the LLM to improvise clinical instructions\.
- Question explanations: maintain a patient\-facing explanation for important questions so the agent can explain why information is needed in plain language\.
- Multilingual and accessibility support: support text/voice choice, interpreter workflows, hearing/vision and communication needs, easy\-read or slower modes and health\-literacy\-aware explanations while preserving original wording for safety\-critical information\.
- Proxy histories: support histories provided by relatives, carers or clinicians with fact\-level provenance and explicit identification of the source\.
- Asynchronous completion: allow patients to pause, resume and return after checking medicines, family history or documents without converting unknown information into negative findings\.
- Multimodal acquisition: accept governed uploads such as medication lists, discharge summaries, anaesthetic alert cards, allergy letters, implanted\-device cards, CPAP information and advance care documents\. Extract candidate facts while preserving the source document\.
- Patient\-generated data: permit selected home measurements or device data such as weight, BP, glucose/CGM or CPAP adherence where clinically appropriate, with clear provenance distinct from clinical observations\.
- Structured clinician handover: generate concise problem\-oriented perioperative summaries from canonical facts, not from raw transcript, with drill\-down to source, rule and unresolved information\.
- Patient confirmation: provide a plain\-language summary for review and correction before final submission where appropriate\.
- Reusable perioperative passport: allow verified high\-value facts such as difficult airway, MH susceptibility, serious allergy, implanted devices and previous anaesthetic complications to persist longitudinally rather than being rediscovered each episode\.
- Capacity and consent boundaries: distinguish history acquisition from consent and detect when a reliable history may require proxy input or clinician assessment of capacity\.
- Temporal reasoning and change detection: represent onset, recency, trajectory, last\-known status and differences from previous assessments as first\-class data\.
- Explainability and clinician override: every flag or recommendation must expose the supporting facts, source, rule and rule version\. Clinicians may override a rule with a recorded rationale without deleting the underlying data\.
- Downtime and failure modes: define safe behaviour when the LLM, FHIR service, pathology, medication, identity or terminology services are unavailable\.
- Security: treat patient text and imported documents as untrusted input, including protection against prompt injection, malicious documents and attempts to alter clinical rules\.
- Consumer co\-design and equity monitoring: evaluate usability, trust, disclosure, completion and correction across language, age, disability, rurality and other relevant groups\.
- Clinical safety case: maintain a formal hazard log and safety case covering missed red flags, false reassurance, incorrect normalisation, source conflict, automation bias, incomplete history, inappropriate advice and integration failure\.
- Silent\-mode validation: prospectively run the system alongside usual care before it influences decisions and measure missed information, false alerts and clinician corrections\.
- Synthetic patient regression testing: maintain a computable library of common and rare high\-risk reference cases and run it against every software, model, terminology and rules release\.
- Conversation replay and audit: support reconstruction of the observable basis for each branch, question and action without relying on hidden model reasoning\.
- Controlled learning: use aggregate performance data to identify misunderstood questions, unnecessary questions, abandonment, clinician corrections and useful branches, but require governed review before clinical rules or interview specifications change\.
- Research and outcomes platform: with appropriate consent and governance, link structured preoperative history, optimisation, anaesthetic care, surgery, complications, length of stay, readmission and patient\-reported recovery for evaluation and research\.
- Future predictive decision support: structured longitudinal data may support validated prediction of cancellation, unexpected admission, ICU use, complications, prolonged length of stay or readmission, but predictive models require separate validation, governance and monitoring\.
- Federated/multi\-service architecture: keep the clinical model portable across LHNs and vendors, with local adapters for EMR, PAS, pathology, pharmacy and workflow systems\.

## Governance and lifecycle requirements

- Separate the LLM's role in conversational acquisition, clarification and language generation from deterministic clinical rules, scoring, management instructions and escalation logic\.
- Do not permit autonomous self\-modification of clinical rules\. Changes require version control, clinical governance, evidence review, testing and release approval\.
- Maintain knowledge provenance for each clinical rule: evidence source, jurisdiction, owner, approval date, effective date, review date, version and superseded versions\.
- Retain an auditable chain from original source to normalised fact, derived score, triggered rule, clinician action and final disposition\.
- Design human override, incident review, monitoring for model/rule drift and rollback into the production lifecycle from the outset\.

## Standards references for interoperability design

- Australian Digital Health Agency, AU Core Implementation Guide / Australian interoperability guidance: https://implementer\.digitalhealth\.gov\.au/standards/au\-core\-implementation\-guide
- Australian Digital Health Agency, interoperability standards requirements including AU Core, AUCDI, SNOMED CT\-AU and AMT: https://www\.digitalhealth\.gov\.au/interoperability
- HL7 FHIR Questionnaire: https://hl7\.org/fhir/R4/questionnaire\.html
- HL7 FHIR QuestionnaireResponse: https://hl7\.org/fhir/R4/questionnaireresponse\.html
- HL7 FHIR Structured Data Capture Implementation Guide: https://hl7\.org/fhir/uv/sdc/
- Australian Digital Health Agency Clinical Note Document FHIR Implementation Guide: https://implementer\.digitalhealth\.gov\.au/fhir/cnd/current/index\.html

