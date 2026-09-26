__PERIOPERATIVE  
CONVERSATIONAL AI__

Full Project Specification and Technical Design

__Version 1\.0 | 26 September 2026__

*Patient\-facing conversational history acquisition for perioperative assessment  
with deterministic clinical state, safety and workflow control*

__Document status  
__Integrated design specification consolidating the scoping review, Clinical Dataset v1\.0, clinical interviewing model, interoperability architecture, provenance and reconciliation model, gap engine, conversation orchestrator, safety boundaries, executable architecture and canonical data model\. This is a development and governance specification, not a clinical guideline or approval for deployment\.

# Document control

__Field__

__Value__

Document

Perioperative Conversational AI Full Project Specification and Technical Design

Version

1\.0

Date

26 September 2026

Scope

Adults undergoing elective or semi\-elective surgery/procedures requiring anaesthesia or sedation

Initial exclusions

Paediatrics, obstetrics and immediate emergency surgery

Primary users

Patients, anaesthetists/perioperative clinicians, preassessment services, clinical governance, digital health and engineering teams

Status

Working specification for design, validation and governance

Companion artefacts

Clinical Dataset v1\.0 workbook; executable technical specification workbook; canonical JSON schemas; PostgreSQL reference DDL

## How to use this specification

This document is the human\-readable system specification\. The machine\-readable workbook and JSON schemas remain the authoritative implementation artefacts for atomic concepts, rules, mappings and object validation\. Where this document summarises a table, the corresponding workbook register should be used for implementation and test generation\.

# Executive summary

The project proposes a patient\-facing conversational AI system that obtains a comprehensive perioperative history through natural dialogue, reconciles patient\-reported information with available clinical records, identifies missing or conflicting information and produces a structured, provenance\-bearing summary for clinician review\. The system is deliberately designed not as an autonomous anaesthetist but as a governed clinical information acquisition and synthesis platform\.

__Core architectural principle  
__The language model manages language\. Deterministic, version\-controlled services own clinical requirements, information states, reconciliation, safety escalation, workflow, closure and write\-back\.

- Clinical Dataset v1\.0 contains 343 atomic concepts across 20 domains\. Each concept has a requirement class, triggers, patient wording, follow\-up logic, uncertainty handling, escalation behaviour, permitted inference, provenance and evidence metadata\.
- The interview is state\-based rather than a fixed questionnaire\. It uses open\-to\-closed micro\-funnels, active listening, cue recognition, signposting, summarisation and dual tracking of the clinical agenda and the patient agenda\.
- Pre\-interview synthesis uses existing data to avoid repetitive questioning, identify conflicts and construct a prioritised information\-gap queue\.
- The LLM never directly writes authoritative clinical state\. It produces candidate assertions or candidate language which must pass deterministic validation\.
- FHIR is a governed interoperability projection of a richer internal semantic model\. The target Australian environment includes FHIR R4, AU Core/AU Base, AUCDI, SNOMED CT\-AU and AMT\.
- The system never autonomously declares a patient fit, cleared or safe for surgery\. Diagnosis, anaesthetic planning, personalised treatment changes and final proceed/postpone decisions remain clinician\-owned\.
- Every assessment pins a ReleaseManifest so the exact clinical dataset, rules, terminology, prompts, models, validators and FHIR mappings can be reconstructed later\.

# 1\. Project purpose and problem definition

## 1\.1 Clinical problem

Preoperative assessment requires broad clinical, functional, medication, anaesthetic, psychosocial and patient\-preference information\. Conventional paper or digital questionnaires are often long, repetitive and insensitive to information already known in the record\. Clinician interviews are adaptive but vary between practitioners and settings\. A conversational system offers the possibility of combining adaptive interviewing with deterministic completeness and safety controls\.

The design challenge is not to make an LLM sound like a clinician\. It is to ensure that the clinically required information is reliably resolved, uncertainty is represented correctly, important discrepancies remain visible and the interaction preserves the behaviours that make clinical history\-taking effective\.

## 1\.2 Intended purpose

To elicit, structure, reconcile and summarise perioperative clinical history and identify information requiring healthcare\-professional review for adults undergoing elective or semi\-elective surgery or procedures requiring anaesthesia or sedation\.

## 1\.3 Explicit non\-goals

- Autonomous determination of fitness or clearance for surgery
- Autonomous diagnosis of new clinical conditions
- Autonomous selection of anaesthetic technique
- Autonomous ASA Physical Status assignment in routine clinical use
- Autonomous medication cessation, initiation or modification unless a separately governed deterministic protocol explicitly authorises a narrow function
- Replacement of physical examination
- Replacement of clinician\-led consent or shared decision\-making
- Unsupervised self\-modification of clinical rules or safety thresholds

## 1\.4 Initial population and deployment boundary

Initial scope is adults aged 18 years and older undergoing elective or semi\-elective procedures requiring general anaesthesia, regional anaesthesia, monitored anaesthesia care or procedural sedation\. Paediatric, obstetric and immediate emergency pathways require separate datasets, safety rules and communication design\.

# 2\. Evidence and requirements development

## 2\.1 Review method

The requirements programme was framed as a PRISMA\-ScR aligned scoping review because the purpose is to map clinical concepts, validated instruments, guidelines, workflow and implementation evidence rather than estimate a single intervention effect\. General preoperative literature was scoped from 1995 to September 2026 and conversational AI/LLM literature from 2018 to September 2026, with backward citation searching for seminal work\.

## 2\.2 Evidence sources

- MEDLINE/PubMed, Embase, CINAHL, Cochrane Library, Scopus and Web of Science
- IEEE Xplore and ACM Digital Library for conversational AI, clinical NLP and LLM literature
- Professional guidance from ANZCA, ASA, ESAIC, RCoA/CPOC, Association of Anaesthetists, ACC/AHA, SASM, ERAS and ESPEN
- Australian interoperability, terminology, safety and regulatory sources including the Australian Digital Health Agency and Therapeutic Goods Administration

## 2\.3 Evidence hierarchy and traceability

Every clinical concept and deterministic rule should retain evidence provenance\. Higher weight is given to current professional standards and guidelines, validated instruments and consensus datasets, with observational and implementation literature used to inform workflow, usability and completeness\. The system must be able to identify the evidence source, jurisdiction, owner, approval date, effective date, review date, version and superseded version for governed rules\.

## 2\.4 Key evidence\-derived design consequences

- Several hundred atomic concepts may be needed even though an individual patient should experience a short adaptive interview\.
- Validated score inputs should be collected explicitly rather than replaced by novel AI\-derived scores\.
- Medication history and medication management are separate concerns\. The latter must be versioned independently from the LLM\.
- Important perioperative risks frequently depend on details that a binary questionnaire cannot represent, including timing, severity, phenotype, treatment, recency, adherence and previous outcomes\.
- Conversational quality is itself a safety feature: active listening, clarification, summaries and opportunities for correction reduce omission and misinterpretation\.

# 3\. Clinical Dataset v1\.0

__Prefix__

__Domain__

__Concept count__

__M0__

__M1__

__Conditional/Optional__

__Key derived construct__

CTX

Patient, procedure and communication

17

15

0

2

CUR

Current health and recent change

14

10

0

4

CARD

Cardiovascular

25

16

0

9

RCRI/cardiovascular risk inputs where applicable

FUNC

Functional capacity and exercise tolerance

16

11

0

5

DASI\-compatible functional capacity; METs proxy

RESP

Respiratory

17

9

0

8

ARISCAT\-related respiratory risk inputs where applicable

OSA

Sleep and obstructive sleep apnoea

16

7

1

8

STOP\-Bang

NEURO

Neurological and neuromuscular

13

8

0

5

RENAL

Renal and urological

12

3

0

9

ENDO

Endocrine and metabolic

14

5

0

9

GI

Gastrointestinal, hepatic and aspiration risk

15

7

0

8

HAEM

Haematology, bleeding, thrombosis and transfusion

15

10

0

5

Bleeding/VTE/PBM review flags

ANAES

Previous surgery and anaesthesia

18

10

0

8

FAM

Family anaesthetic history

8

4

0

4

AIR

Airway, dental and anatomical history

14

9

0

5

MED

Medications and therapies

26

17

1

8

Medication class flags; perioperative medication rules engine inputs

ALL

Allergy and perioperative hypersensitivity

15

6

0

9

Perioperative hypersensitivity risk flag

RES

Frailty, cognition, nutrition and functional independence

27

1

21

5

Frailty/cognitive/nutritional risk inputs

PSY

Pain, psychological health and substance use

31

16

0

15

AUDIT\-C inputs where alcohol items complete; OME/day where opioid medication data complete

SOC

Social circumstances, recovery and discharge

14

0

10

4

GOAL

Patient priorities, goals, advance care planning and reproductive considerations

16

4

8

4

Shared decision\-making/goals\-of\-care context

The current dataset contains 343 atomic concepts across 20 domains\. Requirement classes are M0 universal mandatory, M1 mandatory where applicable, C1 condition\-triggered, C2 procedure\-triggered, C3 medication\-triggered, C4 risk/demographic\-triggered and O optional/contextual\.

## 3\.1 Atomic concept schema

__Concept\_ID__

__Domain__

__Concept__

__Clinical\_definition__

__Requirement\_class__

__Trigger__

__Patient\_question__

__Alternative\_prompts__

__Response\_type__

__Positive\_follow\_up__

__Negative\_resolution__

__Uncertainty\_handling__

__Red\_flag\_rule__

__Clinician\_review\_rule__

__Permitted\_AI\_inference__

__Derived\_variable__

CTX\-001

Patient, procedure and communication

Identity confirmed

Identity confirmed

M0

All patients

Can you tell me your full name and date of birth?

Use plain\-language synonyms and examples if the patient is unsure\.

text

Clarify if incomplete or ambiguous\.

Not applicable; capture value or explicit unknown\.

Record PATIENT\_UNSURE/NOT\_KNOWN; do not convert to negative\. Seek corroborating source where clinically important\.

None

Review as part of completed assessment\.

None: do not infer a diagnosis or negative finding\.

CTX\-002

Patient, procedure and communication

Preferred name

Preferred name

O

Conversational preference; ask early where useful

What would you like me to call you?

Use plain\-language synonyms and examples if the patient is unsure\.

text

Clarify if incomplete or ambiguous\.

Not applicable; capture value or explicit unknown\.

Record PATIENT\_UNSURE/NOT\_KNOWN; do not convert to negative\. Seek corroborating source where clinically important\.

None

Review as part of completed assessment\.

None: do not infer a diagnosis or negative finding\.

Each concept also carries evidence and versioning metadata in the machine\-readable dataset\. The atomic concept is the unit of testability, not necessarily the unit of questioning: one patient utterance may resolve multiple concepts and one concept may require several conversational turns\.

## 3\.2 Key domain requirements

### Cardiovascular and functional capacity

Separate diagnoses from current symptom burden\. Capture functional capacity independently and support DASI\-compatible inputs rather than inferring capacity from vague narrative alone\.

### Respiratory and sleep

Capture respiratory disease, current symptoms and full STOP\-Bang inputs\. Known OSA, suspected OSA, severity, sleep\-study results, PAP prescription, settings and adherence remain distinct\.

### Previous anaesthesia and family history

Capture difficult airway, awareness, severe PONV, delayed emergence, unexpected ventilation/ICU admission, perioperative hypersensitivity, malignant hyperthermia and prolonged paralysis/apnoea in relatives\.

### Medication reconciliation

Capture actual use including name/ingredient, dose, formulation, route, frequency, indication, adherence, last dose and recent changes\. Deliberately probe for commonly omitted high\-risk therapies\.

### Allergy and hypersensitivity

Capture agent, reaction phenotype, timing, severity, treatment, subsequent exposure, testing and perioperative context\. Include latex, chlorhexidine and adhesive exposures\.

### Frailty, cognition and nutrition

Capture baseline independence, mobility, falls, supports, cognitive concerns, prior delirium, weight trajectory, appetite and intake\.

### Pain, psychological health and substances

Capture chronic pain, opioid exposure/OME inputs, mental health, anxiety, smoking/vaping, alcohol and recreational substances using non\-judgemental framing\.

### Goals, recovery and discharge

Capture patient priorities, important functions, home supports, discharge barriers, advance care planning and relevant reproductive considerations\.

## 3\.3 Validated instruments

The system may collect inputs and deterministically calculate configured validated instruments, but score calculation is distinct from authority to interpret or act\. Candidate instruments include STOP\-Bang, DASI, AUDIT\-C, validated frailty tools, Mini\-Cog where appropriate, nutritional screening, Apfel PONV score, RCRI inputs, ARISCAT inputs and oral morphine equivalent calculations\.

# 4\. Information semantics, provenance and reconciliation

## 4\.1 Information states

__ENUM__

__VALUE__

__Meaning / rule__

InformationState

KNOWN\_CONFIRMED

Current, semantically adequate and appropriately verified

InformationState

KNOWN\_UNCONFIRMED

Plausible/current but required verification absent

InformationState

PARTIAL

Required subcomponents unresolved

InformationState

STALE

Fails configured freshness requirement

InformationState

CONFLICTING

Material assertions disagree

InformationState

UNKNOWN

Question/source addressed but answer unavailable to source

InformationState

NOT\_ASKED

No adequate assertion sought/found

InformationState

DECLINED

Patient/source explicitly declines

InformationState

NOT\_APPLICABLE

Requirement inactive/not relevant under rule

InformationState

UNAVAILABLE

Expected source cannot currently be accessed

InformationState

DEFERRED

Intentionally postponed with return obligation

InformationState

SAFETY\_ESCALATED

Human/safety pathway owns resolution

__Safety invariant  
__Unknown, not asked, declined, unavailable, not applicable and explicitly negative are different clinical states\. None may be silently converted into another\.

## 4\.2 Assertion model

Every source statement becomes an immutable Assertion with source, speaker, time, certainty and provenance\. Assertions are not clinical truth\. Reconciliation creates a WorkingFact representing the current governed interpretation while preserving all supporting and dissenting assertions\.

Source event → Assertion\(s\) → terminology/temporal normalisation → reconciliation → WorkingFact → RequirementState → InformationGap

## 4\.3 Conflict handling

The system surfaces rather than hides clinically important disagreement\. Conflict classes include value, negation, temporal, identity, terminology, source and procedure conflicts\. Materiality is graded and high/critical conflicts cannot be silently auto\-resolved except by an explicitly approved deterministic rule\.

## 4\.4 Correction semantics

A patient or clinician correction creates a new assertion linked to the earlier assertion\. The earlier statement remains auditable\. The WorkingFact may change after reconciliation but the historical evidence is never destructively overwritten\.

## 4\.5 Source authority

Authority is datatype\-specific\. A medication order is authoritative evidence of an order but not proof that the patient is taking the medicine\. A patient is often authoritative for current symptoms and actual medicine use\. A diagnostic result system is authoritative for the measured result\. The reconciliation engine therefore evaluates semantic type, source, recency, verification and context rather than applying a single global source hierarchy\.

# 5\. Pre\-interview synthesis and information\-gap engine

Before speaking with the patient, the system should assemble permitted existing information, convert it into assertions, reconcile it and evaluate the active requirements for the planned procedure\. This produces a prioritised information\-gap map so the conversation does not simply rediscover the record\.

Clinical sources → assertions → working state → activate requirements → evaluate information states → create gaps → prioritise → conversation plan

## 5\.1 Gap types and resolution

- Missing information
- Partial information
- Stale information
- Unverified information
- Conflicting information
- Unavailable source information
- Deferred information
- Safety\-escalated information

Resolution options include asking the patient, confirming an existing fact, focused clarification, retrieving another source, creating a human task or escalating\. A gap is resolved only when the requirement reaches its configured minimum information state\.

## 5\.2 Ask, confirm and suppress logic

- SUPPRESS when current adequate information already satisfies the requirement and reconfirmation is not clinically required\.
- CONFIRM when a known fact is clinically important but needs patient verification or is time\-sensitive\.
- ASK when required information is absent, partial or can reasonably be resolved by the patient\.
- RETRIEVE when the patient cannot safely resolve a material issue but another source may\.
- HANDOFF when the issue requires clinical judgement, communication support or a safety pathway\.

## 5\.3 Gap prioritisation

Prioritisation should be deterministic and based on safety criticality, decision impact, time sensitivity, dependency on later questions, probability the patient can resolve the gap and conversational burden\. Safety\-critical gaps can interrupt the planned sequence\.

# 6\. Clinical interviewing and conversation design

The agent is required to reproduce the process of good clinical history\-taking, not merely ask database questions\. Clinical interviewing is therefore modelled as its own computable layer\.

## 6\.1 Open\-to\-closed micro\-funnel

Open invitation → listen/extract → focused clarification → structured characterisation → safety screen → summary/confirmation → signposted transition

- Begin substantial domains with an open invitation where appropriate\.
- Allow the patient to complete a narrative before forcing a checklist\.
- Extract multiple facts from one answer and suppress questions that have already been answered\.
- Use focused and closed questions only to resolve defined gaps, safety screens or ambiguities\.
- Reflect clinically or emotionally salient cues before moving on\.
- Use summaries as error\-detection and correction opportunities\.
- Signpost transitions between major domains and explain unexpected questions when useful\.
- End major domains with an invitation to add information and end the assessment with a final open question\.

## 6\.2 Dual agenda and cue stack

The orchestrator maintains both the clinical agenda and the patient agenda\. Concerns, expectations, fears, goals and recovery priorities are stored as PatientAgendaItems and revisited before closure\. A cue stack can interrupt the planned sequence for safety\-critical, clinically salient, emotional or communication cues\.

## 6\.3 Sensitive and accessible interviewing

Questions concerning alcohol, substances, mental health, reproductive health, weight and social circumstances require neutral, non\-judgemental framing\. The architecture supports text/voice choice, interpreter and proxy workflows, slower/easy\-read modes, accessibility needs, asynchronous pause/resume and multimodal source uploads\. The system must preserve the original wording of safety\-critical patient reports\.

## 6\.4 Conversation states and action vocabulary

__ENUM__

__VALUE__

__Meaning / rule__

ActionType

OPEN\_INVITATION

Invite broad narrative

ActionType

FACILITATE

Encourage continuation without new topic

ActionType

REFLECT

Reflect content/emotion

ActionType

SUMMARISE

Summarise and check understanding

ActionType

AGENDA\_SOLICIT

Ask for concerns/goals/questions

ActionType

SIGNPOST

Orient transition/topic

ActionType

FOCUSED\_PROBE

Ask targeted missing component

ActionType

CLOSED\_SCREEN

Closed safety/screening question

ActionType

CONFIRM

Confirm known but unverified/time\-sensitive fact

ActionType

CLARIFY

Resolve ambiguity/conflict

ActionType

EXPLAIN\_REASON

Briefly explain relevance

ActionType

REQUEST\_SOURCE

Seek collateral/source

ActionType

CREATE\_TASK

Create workflow obligation

ActionType

INTERRUPT\_FOR\_SAFETY

Pre\-empt routine conversation

ActionType

HANDOFF

Transfer to human

ActionType

RETURN\_TO\_TOPIC

Return to deferred/agenda topic

ActionType

FINAL\_OPEN

Final invitation before closure

ActionType

TEACH\_BACK

Check patient understanding where appropriate

# 7\. Conversation orchestrator

The orchestrator selects what the system should do next\. It does not generate the wording itself\. It combines clinical state, gap queue, patient agenda, conversation state, cues and safety policy to produce an InterviewAction contract\.

Clinical state \+ GapQueue \+ PatientAgenda \+ ConversationState \+ Cues \+ SafetyPolicy → Orchestrator → InterviewAction → LLM realisation → Validator → Patient

## 7\.1 Policy hierarchy

1. Immediate safety and identity/procedure integrity
2. Clinical boundary and escalation rules
3. Required clinical information and unresolved critical gaps
4. Patient agenda and salient cues
5. Interview\-process policy and domain sequencing
6. Communication/accessibility preferences
7. Language generation and style

## 7\.2 InterviewAction contract

An InterviewAction specifies action type, purpose, target requirements/gaps/concepts, priority, permitted content, prohibited content, question form, maximum number of questions, fallback action and provenance\. The LLM receives this bounded contract rather than an instruction such as “take a perioperative history”\.

## 7\.3 Turn\-processing pipeline

1. Receive patient input and preserve exact turn
2. Speech\-to\-text confidence/modality checks where relevant
3. Extract candidate assertions, corrections, questions, agenda items and cues
4. Validate extraction schema
5. Attach source and provenance
6. Normalise terminology and time without increasing certainty
7. Reconcile candidate assertions into working state
8. Re\-evaluate active requirements and gaps
9. Evaluate safety interrupts
10. Update conversation working memory and deferred topics
11. Select governed InterviewAction
12. Assemble minimum necessary model context
13. Generate candidate utterance
14. Run validator stack
15. Deliver approved turn and append audit event

# 8\. Safety, escalation and clinical boundaries

## 8\.1 Functional boundaries

__BOUNDARY\_ID__

__Function__

__Default AI permission__

__Prohibited autonomous behaviour__

__Human review trigger__

SB\-001

History elicitation

ALLOW

Diagnose solely from conversational history

Any diagnostic conclusion affecting care

SB\-002

Record synthesis

ALLOW\_WITH\_GUARDRAILS

Invent missing facts or collapse conflicts

Material unresolved discrepancy

SB\-003

Clinical terminology normalisation

ALLOW\_WITH\_GUARDRAILS

Silently commit ambiguous/high\-risk mapping

Ambiguous mapping with clinical consequence

SB\-004

Risk\-factor identification

ALLOW

Convert risk\-factor presence into independent diagnosis or clearance

Risk factor triggers management decision

SB\-005

Validated score calculation

ALLOW\_WITH\_GUARDRAILS

Impute missing score inputs or use unvalidated LLM estimate

Missing/ambiguous input or score changes management

SB\-006

Clinical alerts

ALLOW\_WITH\_GUARDRAILS

Give patient definitive diagnosis/treatment instruction from alert alone

High\-severity alert or uncertainty

SB\-007

Patient education

ALLOW\_LIMITED

Provide personalised treatment recommendation beyond approved pathway

Patient asks what they personally should do where answer changes treatment

SB\-008

Medication reconciliation

ALLOW\_WITH\_GUARDRAILS

Tell patient to start/stop/alter medicine unless explicitly authorised deterministic protocol exists

Any medication change or unresolved critical medicine issue

SB\-009

Investigation recommendation

CLINICIAN\_ONLY by default

Order or recommend patient\-specific test autonomously outside governed protocol

Potential need for new investigation

SB\-010

Diagnosis

CLINICIAN\_ONLY

Tell patient they have a new diagnosis

Any new diagnostic inference

SB\-011

Anaesthetic technique selection

CLINICIAN\_ONLY

Select GA/regional/sedation technique

Any technique recommendation

SB\-012

Surgical fitness / clearance

NEVER\_AUTONOMOUS

Declare 'fit', 'cleared', 'safe for surgery' or equivalent

Always clinician\-owned

SB\-013

ASA Physical Status

CLINICIAN\_ONLY by default

Assign authoritative ASA class

Always before clinical use/write\-back

SB\-014

Consent to procedure/anaesthesia

CLINICIAN\_ONLY

Obtain or attest informed consent for anaesthesia/procedure unless legally/governance\-approved workflow explicitly permits

Consent decision

SB\-015

Procedure/site verification

ESCALATE

Resolve laterality/procedure discrepancy

Any material discrepancy

SB\-016

Urgent symptom triage

ESCALATE

Provide reassurance that urgent symptom is benign

Configured red flag

SB\-017

Discharge/fasting/medication instructions

APPROVED\_CONTENT\_ONLY

Generate novel instructions from general knowledge

Instruction absent, conflicting or patient\-specific modification needed

SB\-018

Write\-back to longitudinal record

GOVERNED

Write unverified or materially conflicted AI inference as authoritative fact

Verification threshold unmet

SB\-019

Clinical handoff summary

ALLOW\_WITH\_GUARDRAILS

State that clinician has reviewed/accepted content when they have not

High\-risk unresolved item

SB\-020

Research/secondary use

SEPARATE\_GOVERNANCE

Assume care consent covers research/model training

Any secondary\-use proposal

__Absolute boundary  
__Information complete ≠ perioperative risk acceptable ≠ fit for procedure ≠ proceed with surgery\. The system may determine information completeness but never autonomously makes the latter decisions\.

## 8\.2 Escalation framework

__ESC\_ID__

__Escalation class__

__Example triggers__

__Immediate AI behaviour__

__Destination/owner__

__Closure rule__

ESC\-001

Immediate clinical safety

Severe current chest pain, severe dyspnoea, collapse, major bleeding or other locally configured emergency symptom

Interrupt; concise direct assessment only if protocol requires; summon immediate human response

Local urgent/emergency clinical pathway

Cannot mark routine complete

ESC\-002

Identity/procedure safety

Wrong patient, uncertain identity, procedure/site/laterality discrepancy

Stop affected synthesis; explain need for staff verification

Administrative/clinical identity and procedural verification pathway

Blocks completion

ESC\-003

Anaesthetic safety history

Possible difficult airway, malignant hyperthermia, severe previous anaesthetic reaction, awareness with major concern

Acknowledge, collect minimum useful history, create visible flag/task

Anaesthetist/pre\-anaesthesia clinic

Complete\-with\-open\-action only if owner explicit

ESC\-004

Medication safety

Unresolved anticoagulant, insulin, SGLT2, GLP\-1 or other configured high\-risk medication issue

Clarify actual use/last dose; do not issue novel medication instruction

Anaesthetist/pharmacist/prescriber/local pathway

Critical unresolved issue blocks autonomous closure

ESC\-005

Allergy safety

Potential anaphylaxis/severe drug reaction or conflict with NKDA

Clarify phenotype/agent/timing; preserve unverified alert

Clinician/allergy/anaesthetic pathway

Must remain visible until verified/refuted

ESC\-006

New significant symptom

New chest pain, dyspnoea, syncope, infection or deterioration that may alter plan

Characterise according to approved rule then refer

Pre\-op clinician/anaesthetist or urgent pathway by severity

No clearance statement

ESC\-007

Communication/capacity

Interpreter required, repeated misunderstanding, cognitive impairment, unreliable ASR, proxy issues

Switch modality, interpreter or human interviewer

Appropriate communication/human pathway

Cannot complete from unreliable interaction

ESC\-008

Patient request/distress

Patient asks for human, becomes significantly distressed or does not want AI

Acknowledge and handoff/stop

Human clinician/staff

Record stop/handoff, not failure

ESC\-009

Data conflict

Material conflict cannot be safely reconciled

Explain neutral discrepancy if appropriate; create review task

Datatype\-appropriate clinician

Conflict remains open

ESC\-010

System/model failure

Repeated schema, retrieval, terminology, generation or validation failure

Fail closed; preserve state; handoff

Human workflow/technical incident process

No silent fallback to unvalidated free text

ESC\-011

Safeguarding/other serious risk

Locally defined safeguarding or serious risk disclosure

Follow approved minimum\-disclosure/escalation protocol

Designated safeguarding/clinical pathway

Human ownership mandatory

ESC\-012

Governance/regulatory uncertainty

Feature would diagnose, recommend treatment or materially change intended purpose beyond approved boundary

Disable feature in production until assessed

Product clinical safety/regulatory governance

Release gate

## 8\.3 Patient\-facing language guardrails

Generated language must preserve the certainty and source of the underlying data\. The system must not convert a patient report into a diagnosis, an abnormality into a prediction that surgery will be cancelled or a complete history into clearance\. Where approved authoritative instructions exist, the system may communicate them but must not modify them\.

## 8\.4 Fail\-closed behaviour

- Repeated schema failure → no clinical mutation and human/modality fallback\.
- Source\-system outage → UNAVAILABLE, not a negative clinical finding\.
- Terminology ambiguity → retain source text and mapping uncertainty\.
- Repeated response\-validation failure → do not deliver unsafe free text; regenerate within a bounded budget then hand off\.
- Critical task without owner → closure blocked\.
- Identity or procedure/site discrepancy → affected workflow blocked until verification\.

# 9\. Australian interoperability and FHIR design

FHIR alignment is a design requirement, not a downstream export function\. The internal model remains optimised for clinical reasoning and provenance, while externally meaningful concepts have governed FHIR mappings\.

## 9\.1 Standards target

- HL7 FHIR R4 / 4\.0\.1 baseline
- AU Core and AU Base profiles where applicable
- AUCDI alignment for relevant clinical data elements
- SNOMED CT\-AU for clinical terminology
- Australian Medicines Terminology \(AMT\) for medicines
- FHIR Questionnaire and QuestionnaireResponse with Structured Data Capture\-compatible logic where feasible
- FHIR Provenance for clinical lineage and AuditEvent for operational/security audit
- SMART on FHIR contextual launch where supported; event\-driven/CDS mechanisms considered later

## 9\.2 Canonical\-to\-FHIR mapping

__Map\_ID__

__Canonical object / concept__

__FHIR R4 resource__

__Preferred AU profile / layer__

__Write\-back status__

__Perioperative modelling note__

FHIR\-001

Patient identity/context

Patient

AU Core Patient

Read/write subject to identity governance

Use EMR identity as authoritative; conversational agent must never create a new identity from free text

FHIR\-002

Encounter / assessment context

Encounter

AU Core Encounter

Read; create/update depending host workflow

Separate perioperative assessment encounter from planned surgical encounter when systems distinguish them

FHIR\-003

Planned procedure

ServiceRequest \+ Procedure when performed

Core FHIR / AU Core Procedure for completed procedure

Primarily read ServiceRequest; Procedure write after event is source\-system responsibility

Do not represent a planned procedure as completed Procedure

FHIR\-004

Current medical condition

Condition

AU Core Condition

Candidate write\-back only after governed verification

Patient\-reported condition can exist with explicit verification/source state; do not silently upgrade certainty

FHIR\-005

Current symptom

Observation primarily; Condition if established diagnosis/problem

AU Core Diagnostic Result Observation where suitable, otherwise core/AU Base Observation

Usually assessment\-local; selective write\-back

Symptoms need onset, trajectory, severity, associated features and negation in internal model

FHIR\-006

Negative symptom / absence

Observation or Condition with appropriate status/code; QuestionnaireResponse for exact answer

AU Core where profile fits

Usually do not create persistent Condition for every negative screen

Distinguish NOT\_ASKED, UNKNOWN, DENIED and NOT\_APPLICABLE internally

FHIR\-007

Medication use reported by patient

MedicationStatement \+ Medication

AU Core MedicationStatement \+ AU Core Medication

Reconciled write\-back only under medication governance

MedicationStatement is assertion of use, not prescription or administration

FHIR\-008

Prescription/order

MedicationRequest

AU Core MedicationRequest

Read primarily

Do not infer current use solely from an active order

FHIR\-009

Dispensing evidence

MedicationDispense

AU Core MedicationDispense

Read

Dispense supports reconciliation but is not proof of ingestion/adherence

FHIR\-010

Medication administration evidence

MedicationAdministration

AU Base/core FHIR unless downstream profile

Read

Useful for recent inpatient/perioperative exposure and reaction investigation

FHIR\-011

Allergy/intolerance

AllergyIntolerance

AU Core AllergyIntolerance

Governed write\-back after verification

Capture phenotype, severity, timing, treatment, testing and suspected agent separately

FHIR\-012

Previous operation/procedure

Procedure

AU Core Procedure

Selective read/write

Patient recollection can be represented but must remain source\-labelled

FHIR\-013

Previous anaesthetic event

Procedure \+ Observation \+ Condition/AllergyIntolerance \+ DocumentReference as appropriate

AU Core resources where available

Assessment\-local plus governed longitudinal safety facts

Model event as a bundle/graph: anaesthetic procedure context \+ airway event \+ reaction \+ outcome \+ source

FHIR\-014

Difficult airway history

Observation/Condition \+ prior Procedure/DocumentReference context

Core/AU Core where applicable

High\-value governed write\-back candidate

Never collapse 'they had trouble with the tube' directly into a definitive difficult\-intubation diagnosis

FHIR\-015

Family history

FamilyMemberHistory

Core FHIR

Assessment\-local usually

Important for malignant hyperthermia and inherited conditions

FHIR\-016

Functional capacity

Observation

Core/AU Base Observation; AU Core if suitable profile emerges

Assessment\-local; selective longitudinal reuse

Keep free activity narrative plus derived/validated score separate

FHIR\-017

Frailty score

Observation

Core/AU Base Observation

Assessment\-local or longitudinal

Do not derive CFS from LLM unless validated workflow explicitly allows it

FHIR\-018

Smoking status

Observation

AU Core Smoking Status

Read/write where governed

Retain amount, duration, cessation date and vaping separately if required

The complete mapping register contains 38 mappings in the companion workbook\. Projection must preserve source, verification and uncertainty and must not increase certainty\. MedicationStatement represents actual use and must not be collapsed into MedicationRequest, which represents an order\.

## 9\.3 Write\-back policy

FHIR output is generated first as a candidate Bundle and validated\. Authoritative write\-back is governed by datatype\-specific verification thresholds and, for the MVP, clinician approval\. Unverified or materially conflicted AI\-derived interpretations must not be written as authoritative facts\.

# 10\. Executable technical architecture

__LAYER\_ID__

__Layer__

__Responsibility__

__Primary components__

__Safety boundary__

ARCH\-001

Experience

Patient and clinician interaction

Voice/text patient UI; clinician review UI

UI must expose AI role, uncertainty and handoff

ARCH\-002

Session Orchestrator

Own conversational state and select next governed action

State machine; policy hierarchy; action planner

Cannot bypass safety gates

ARCH\-003

Clinical State

Maintain assertions, working facts, conflicts and requirements

Assertion graph; reconciliation engine; gap engine

No destructive reconciliation

ARCH\-004

Clinical Rules

Deterministic activation, freshness, escalation and closure rules

Rules service; versioned rule packs

LLM cannot override critical rules

ARCH\-005

Terminology

Normalise clinical concepts

SNOMED CT\-AU/AMT terminology adapter; value sets

Ambiguous mappings remain ambiguous

ARCH\-006

LLM Runtime

Language understanding and realisation

Extractor model; response generator; optional summariser

No direct write to authoritative clinical state

ARCH\-007

Validation

Validate model outputs before state mutation/delivery

Schema; semantic; safety; certainty; action\-contract validators

Fail closed on critical violations

ARCH\-008

Interoperability

Read/write healthcare data

FHIR adapter; source\-system adapters

Projection cannot increase certainty

ARCH\-009

Workflow

Human tasks, escalation and ownership

Task service; notifications; clinician review queue

Critical action requires explicit owner

ARCH\-010

Persistence

Durable clinical and operational state

Transactional DB; object store; audit/event store

Append\-only audit/provenance

ARCH\-011

Observability

Safety, quality and technical monitoring

Metrics; traces; audit; model telemetry; incident feed

No PHI in unrestricted telemetry

ARCH\-012

Governance

Control versions and releases

Prompt/rule/model/terminology registry; feature flags

Material scope change triggers governance review

## 10\.1 Service catalogue

__SERVICE\_ID__

__Service__

__Owns__

__Key operations__

__Failure mode__

SVC\-001

API Gateway

Authentication, routing, rate limiting

startSession; submitTurn; getSession; resumeSession

Reject safely; no state loss

SVC\-002

Session Service

Session lifecycle and episode context

create; pause; resume; close

Session remains resumable

SVC\-003

Orchestrator Service

Conversation state/action selection

planNextAction; transitionState

No free\-form fallback

SVC\-004

Clinical State Service

Assertions/facts/conflicts

addAssertion; reconcile; getWorkingState

Reject incomplete mutation

SVC\-005

Requirement & Gap Service

Activation and gap queue

evaluateRequirements; calculateGaps; prioritise

Critical gap cannot disappear

SVC\-006

Safety Service

Safety gates/escalations

evaluateSafety; createEscalation; closureGate

Fail safe/handoff

SVC\-007

LLM Extraction Service

Structured semantic extraction

extractEvents

Return invalid/low\-confidence, never clinical truth

SVC\-008

LLM Language Service

Natural\-language realisation

realiseAction; summariseForPatient

Regenerate bounded times then handoff

SVC\-009

Response Validator

Pre\-delivery validation

validateSchema; validateActionFidelity; validateClaims

Block delivery

SVC\-010

Terminology Service

Coding and value\-set operations

lookup; map; subsumes; validateCode

Return unmapped/ambiguous

SVC\-011

FHIR Adapter

FHIR read/project/write

search; read; transaction; provenanceBundle

Queue/retry; no certainty inflation

SVC\-012

Retrieval Service

Clinical source retrieval

fetchMeds; fetchAllergies; fetchDocs; fetchLabs

Mark source unavailable

SVC\-013

Workflow Task Service

Human ownership and escalation

createTask; assign; acknowledge; resolve

Critical unowned task blocks closure

SVC\-014

Audit & Provenance Service

Immutable lineage

appendEvent; getLineage

Clinical mutation fails if provenance unavailable

SVC\-015

Configuration Registry

Pinned runtime artefacts

getReleaseManifest; resolveVersion

Session cannot start without valid manifest

## 10\.2 Bounded LLM calls

__CALL\_ID__

__Call__

__Model task__

__Input allowed__

__Clinical authority__

__Fallback__

LLM\-001

Turn extraction

Extract candidate assertions, negations, corrections, questions, goals and cues

Current turn; bounded recent context; relevant known concepts

None: candidates only

Schema retry then human/modality fallback

LLM\-002

Semantic relation

Assess SAME/COMPLEMENTARY/POSSIBLE\_CONFLICT relationship when deterministic terminology insufficient

Small assertion pair/set \+ coded context

Advisory only

Mark unresolved

LLM\-003

Question realisation

Turn InterviewAction into natural patient\-facing language

Action contract; minimal permitted facts; communication prefs

None beyond action

Validator reject/regenerate

LLM\-004

Patient summary realisation

Explain captured information back to patient

Approved fact subset \+ uncertainty labels

No new inference

Template fallback

LLM\-005

Clinician summary drafting

Draft structured summary from governed state

Working facts; conflicts; gaps; agenda; actions

Draft only

Deterministic structured view

LLM\-006

Document extraction

Extract candidate facts from unstructured clinical documents

Document chunk \+ metadata

None

Leave unextracted/manual review

__LLM authority  
__No LLM call has authority to establish clinical truth\. Extraction creates candidates, semantic relation calls are advisory and language generation is constrained by an already\-selected InterviewAction\.

## 10\.3 Validator stack

__VAL\_ID__

__Validator__

__Checks__

__Block conditions__

__Action on failure__

VAL\-001

JSON/schema

Required fields, enums, types, IDs

Malformed structured output

Retry bounded times

VAL\-002

Action fidelity

Response serves target action/gap only

Unrelated question/topic or wrong action

Regenerate

VAL\-003

Question count

Number of interrogatives/clinical asks

Exceeds action max\_questions

Regenerate

VAL\-004

Claim grounding

Every clinical claim maps to permitted fact/source

Unsupported claim

Regenerate; repeated failure handoff

VAL\-005

Certainty preservation

Wording does not strengthen assertion/verification

Possible→confirmed or unknown→negative

Block

VAL\-006

Clinical boundary

No diagnosis/clearance/treatment outside permission

Any prohibited autonomous behaviour

Block \+ safety log

VAL\-007

Medication instruction

Instruction exactly matches authorised source when allowed

Novel or modified medication instruction

Block \+ handoff

VAL\-008

Safety interrupt

No routine response emitted when interrupt active

Routine question during critical interrupt

Block

VAL\-009

Privacy/minimisation

No irrelevant sensitive/source detail exposed

Unnecessary disclosure

Regenerate

VAL\-010

Language quality

Plain language, no unexplained jargon, no coercion

Unsafe ambiguity/coercive phrasing

Regenerate

VAL\-011

Source attribution

Where required, statement distinguishes record vs patient report

False attribution

Block

VAL\-012

Closure language

No implication of fitness/clearance

'all clear', 'safe for surgery' etc

Block

# 11\. API and event architecture

## 11\.1 REST\-style API contracts

__API\_ID__

__Method__

__Path__

__Purpose__

__Idempotency / safety__

API\-001

POST

/v1/sessions

Create perioperative interview session

Idempotency\-Key required

API\-002

POST

/v1/sessions/\{id\}/synthesise

Run pre\-interview synthesis

Repeatable against source snapshot

API\-003

POST

/v1/sessions/\{id\}/turns

Submit patient/agent turn

Exactly\-once state mutation via turn\_id

API\-004

GET

/v1/sessions/\{id\}/next\-action

Return governed InterviewAction

Never returns free\-form response alone

API\-005

POST

/v1/sessions/\{id\}/responses:realise

Generate language from approved action

Action ID and manifest pinned

API\-006

POST

/v1/sessions/\{id\}/confirmations

Record patient confirmation/correction

Append\-only provenance

API\-007

POST

/v1/sessions/\{id\}/tasks

Create retrieval/human task

Critical tasks cannot remain ownerless at closure

API\-008

POST

/v1/sessions/\{id\}/clinician\-review

Record clinician verification/edit

Requires authorised clinician identity

API\-009

GET

/v1/sessions/\{id\}/summary

Clinician\-facing state summary

Must label unverified/conflicted data

API\-010

POST

/v1/sessions/\{id\}/fhir:project

Create candidate FHIR bundle

No authoritative write by default

API\-011

POST

/v1/sessions/\{id\}/fhir:commit

Commit approved FHIR output

Write\-back gate enforced

API\-012

POST

/v1/sessions/\{id\}:pause

Pause resumably

State and obligations persisted

API\-013

POST

/v1/sessions/\{id\}:handoff

Transfer to human

Does not imply completion

API\-014

POST

/v1/sessions/\{id\}:complete

Attempt closure

Closure gate deterministic

## 11\.2 Event contracts

__EVENT__

__Producer__

__Consumers__

__Purpose__

__Delivery semantics__

session\.created

Session Service

Orchestrator; Audit

Initialise workflow

At least once \+ dedupe

source\.snapshot\.created

Retrieval Service

Clinical State; Audit

Freeze evidence used for synthesis

At least once

assertion\.created

Clinical State

Reconciliation; Gap; Audit

Add sourced clinical statement

Exactly\-once logical

assertion\.corrected

Clinical State

Reconciliation; Audit

Preserve correction lineage

Exactly\-once logical

conflict\.detected

Reconciliation

Safety; Workflow; UI

Trigger resolution/escalation

At least once \+ dedupe

requirements\.changed

Gap Service

Orchestrator; Audit

Re\-plan information needs

At least once

gap\.queue\.updated

Gap Service

Orchestrator; UI

Drive next action

Latest\-state event

safety\.interrupt

Safety Service

Orchestrator; Workflow; UI

Pre\-empt routine flow

High\-priority durable

interview\.action\.selected

Orchestrator

Language Service; Audit

Constrain generation

Exactly\-once per action\_id

response\.rejected

Validator

Language Service; Audit

Bounded regeneration

Durable for safety metrics

turn\.delivered

Experience

Clinical State; Audit

Record what patient received

Exactly\-once logical

task\.created

Workflow

UI; Closure Gate; Audit

Human/retrieval ownership

Durable

task\.resolved

Workflow

Clinical State; Gap; Audit

Update state and re\-plan

Durable

session\.handoff

Orchestrator

Workflow; UI; Audit

Human continuation

Durable

session\.completed

Session Service

FHIR Adapter; Reporting; Audit

Finalise episode output

Durable

## 11\.3 Idempotency and state consistency

Clinical state mutations must be serialised per session and retried safely\. Patient turns use stable turn identifiers so transport retries cannot create duplicate assertions\. Session creation uses idempotency keys\. Durable events use logical exactly\-once behaviour through deduplication where infrastructure delivery is at\-least\-once\.

# 12\. Canonical data model

__ENTITY__

__Primary key__

__Purpose__

__Core relationships__

__Authoritative?__

Session

session\_id

One perioperative conversational assessment

1:N Turn, Assertion, RequirementState, Gap, Cue, AgendaItem, Task; 1:1 ReleaseManifest snapshot

Operational

Assertion

assertion\_id

Atomic sourced statement without reconciliation

N:1 Session; N:M WorkingFact; self\-relations for correction/support/conflict

Source truth only

WorkingFact

fact\_id

Governed current interpretation of one clinical concept/value

N:M Assertion; 1:N Conflict/RequirementState references

Derived

Conflict

conflict\_id

Material disagreement among assertions/facts

N:M Assertion; optional Task

No

RequirementState

requirement\_state\_id

State of an activated clinical information requirement

N:1 Session; references Requirement definition; 1:N Gap

No

InformationGap

gap\_id

Unresolved information need

N:1 RequirementState; optional target Assertion/Fact/Task

No

InterviewAction

action\_id

Governed next conversational action

N:1 Session; N:M Gap/Requirement; 1:N generated candidate response

Policy decision

Turn

turn\_id

Actual patient/agent/human interaction

N:1 Session; optional action\_id; 1:N Assertion/Cue

Observed interaction

Task

task\_id

Human or retrieval obligation

N:1 Session; optional Conflict/Gap; owner reference

Workflow

Cue

cue\_id

Clinical, emotional or communication cue

N:1 Turn/Session

Observed/derived

PatientAgendaItem

agenda\_item\_id

Patient concern, question, goal or preference

N:1 Session; optional source turn

Patient\-sourced

ReleaseManifest

manifest\_id

Immutable versions governing a session

1:N Session logically, but snapshot/pin per session

Configuration

## 12\.1 Key invariants

__INV\_ID__

__Invariant__

__Enforcement point__

__Failure behaviour__

__Critical?__

INV\-001

Every Assertion has traceable source and provenance

Schema \+ Clinical State Service

Reject assertion

Yes

INV\-002

Patient correction never deletes prior assertion

Clinical State Service

Create new assertion \+ supersedes link

Yes

INV\-003

WorkingFact cannot exist without supporting assertion

DB constraint/service validation

Reject fact update

Yes

INV\-004

A material conflict remains visible until governed resolution

Reconciliation \+ UI

Keep CONFLICTED state/open conflict

Yes

INV\-005

NOT\_ASKED, UNKNOWN, DECLINED and NEGATED are distinct

Schemas/rules/tests

Reject invalid state conversion

Yes

INV\-006

NOT\_APPLICABLE requirement cannot generate an active gap

Gap Engine

Drop/error and safety log

Yes

INV\-007

InterviewAction exists before LLM patient\-facing generation

Orchestrator/API

Reject generation call

Yes

INV\-008

Delivered agent Turn references exact approved content/action

Experience \+ Audit

Fail delivery/audit incident

Yes

INV\-009

Critical safety interrupt pre\-empts routine action

Safety/Orchestrator

Cancel routine action

Yes

INV\-010

Critical Task must have explicit owner before closure

Closure Gate

Reject completion

Yes

INV\-011

FHIR projection cannot increase certainty

FHIR Adapter

Reject projection

Yes

INV\-012

Session runtime versions remain pinned

Configuration Registry

Reject incompatible mutation/migrate explicitly

Yes

INV\-013

Raw model candidate output cannot directly mutate clinical truth

API/service boundary

Reject direct write

Yes

INV\-014

High\-priority patient agenda item needs disposition before closure

Closure Gate

Reject completion

No

INV\-015

Stale fact may remain historical but cannot satisfy current requirement

Gap Engine

Generate freshness gap

Yes

INV\-016

Source outage maps to UNAVAILABLE, never negative

Retrieval/Gap Engine

Create source gap

Yes

## 12\.2 ReleaseManifest

clinical\_dataset\_version  
rules\_version  
terminology\_version  
prompt\_version  
extractor\_model\_id  
language\_model\_id  
validator\_version  
fhir\_mapping\_version  
site\_configuration\_version

The manifest is immutable for a session except through an explicit governed migration\. It is central to reproducibility, incident review and safe rollback\.

## 12\.3 Machine\-readable schemas

Draft 2020\-12 JSON Schemas exist for Session, Assertion, WorkingFact, Conflict, RequirementState, InformationGap, InterviewAction, Turn, Task, Cue, PatientAgendaItem and ReleaseManifest\. The companion package also includes PostgreSQL\-oriented reference DDL\. Cross\-object clinical invariants remain service\-level controls because they cannot all be expressed safely in JSON Schema alone\.

# 13\. Persistence, security and privacy

## 13\.1 Data stores

__STORE__

__Contents__

__Technology characteristic__

__Retention__

__Encryption/access__

__Notes__

Clinical State DB

Sessions, assertions, facts, conflicts, requirements, gaps, agenda, actions

Transactional relational/document hybrid; strong consistency for session mutations

Clinical record policy

Encrypted at rest/in transit; least privilege

Canonical operational source of truth

Event/Audit Store

Append\-only state transitions, delivered turns, validator failures, rule decisions

Immutable/WORM\-capable event log

Audit/legal policy

Separate privileged access

Supports replay and incident investigation

Object Store

Audio where permitted, source document snapshots, generated artefacts

Versioned encrypted object storage

Data\-minimised; audio may have shorter retention

Restricted service identities

Avoid storing raw audio if not required

Terminology Cache

Codes, value sets, mapping artefacts

Read\-optimised cache

Version\-pinned

No patient data

Cache keyed by terminology release

Configuration Registry

Rules, prompts, schemas, release manifests

Versioned signed artefact repository

Indefinite release history

Governance\-controlled writes

Every session pins manifest

Analytics Store

De\-identified/approved operational metrics

Separated from production clinical store

Governed

No direct identifiers where not needed

Never use for model training by default

## 13\.2 Security requirements

- Strong authentication and least\-privilege authorisation for patient, clinician and service identities\.
- Encryption in transit and at rest, with managed secrets and key rotation\.
- Patient text, uploaded documents and retrieved content are untrusted input\. Defences must address prompt injection, malicious documents and attempts to alter rules or system instructions\.
- Model context must be minimised to the facts required for the current action\.
- Production telemetry must not leak identifiable clinical content into unrestricted logs\.
- Audit and provenance stores require access controls distinct from general analytics\.
- Secondary use, research and model training require separate governance and must not be inferred from consent to clinical care\.

## 13\.3 Retention

Retention should be purpose\-specific\. Clinical facts and governed outputs follow clinical record requirements\. Raw audio, full transcripts and intermediate model artefacts should only be retained where there is a defined clinical, safety or legal purpose\. The design should support shorter retention or non\-retention of raw audio while preserving the clinical record and audit chain required for safe operation\.

# 14\. Observability and clinical safety assurance

__METRIC\_ID__

__Metric__

__Level__

__Definition__

__Alert / review trigger__

__Purpose__

OBS\-001

Critical escalation sensitivity

Safety

Critical synthetic/live\-reviewed triggers correctly escalated / all critical triggers

Any confirmed miss; pre\-release target 100% synthetic

Release/safety

OBS\-002

Silent critical conflict resolution

Safety

Critical conflicts closed without governed evidence/human owner

Any event

Never\-event metric

OBS\-003

Unsupported claim rate

Language

Delivered responses with unsupported clinical claim / sampled responses

Any critical claim; trend threshold for minor

Generation safety

OBS\-004

Question redundancy rate

Conversation

Questions asked for already adequate non\-reconfirmable requirements / total questions

Trend above target

Burden/listening quality

OBS\-005

Patient correction rate

Clinical state

Patient corrections of AI summary/extraction / sessions

Monitor by domain/model

Extraction quality

OBS\-006

Medication extraction error

Clinical

Incorrect medicine/dose/frequency/last\-dose extraction

Any serious medication error

Medication safety

OBS\-007

Unowned critical task

Workflow

Critical open tasks without accepted owner

Any

Closure/workflow safety

OBS\-008

Handoff rate

Workflow

Sessions handed to human / started

Stratify by reason

Capability planning

OBS\-009

Completion with open actions

Workflow

Completed assessments with explicit open actions

Monitor type/age

Operational quality

OBS\-010

Turn latency p50/p95

Technical

Submit patient turn to delivered agent response

SLO breach

User experience

OBS\-011

Schema failure rate

Model

Invalid model outputs / calls

Trend threshold

Model reliability

OBS\-012

Validator rejection rate

Model/safety

Candidate responses rejected / generated

Trend by validator

Prompt/model drift

OBS\-013

Retrieval availability

Integration

Successful source retrieval / attempted

Source\-specific SLO

Integration reliability

OBS\-014

FHIR projection failures

Interoperability

Invalid candidate resources/bundles / projections

Any critical mapping failure

Interface quality

OBS\-015

Abandonment/pause rate

Experience

Patient stops/pauses before closure

Review by reason

Usability

OBS\-016

Patient agenda closure

Patient\-centred

High\-priority agenda items disposed before closure / raised

Target near 100%

Patient\-centred quality

## 14\.1 Release\-blocking safety case

A clinical pilot requires a structured safety case covering content validity, deterministic rules, conversation behaviour, extraction safety, reconciliation, escalation, response fidelity, FHIR/provenance integrity, medication safety, equity/accessibility, cyber/privacy, human factors, workflow, model/version governance, incident learning and regulatory readiness\.

## 14\.2 Never\-event style controls

- Missed critical escalation in the synthetic critical test set
- Silent resolution of a critical conflict
- Novel unsafe medication instruction
- Unsupported diagnostic/clearance claim delivered to a patient
- Critical task lost or closed without ownership
- FHIR projection that materially increases certainty or removes critical provenance

# 15\. Human factors, equity and accessibility

Evaluation must measure more than completeness\. The system should be tested across health literacy, language, speech patterns, age, disability/access needs, proxy histories and different levels of clinical complexity\. Conversation quality metrics should include unnecessary questioning, interruptions, abandonment, patient corrections, agenda closure, trust and ability to understand why information is being requested\.

The design should allow a patient to request a human at any time\. Withdrawal from the AI interaction is not a failure and must not result in loss of already collected information\. A clinician should be able to continue from the same structured state\.

# 16\. Regulatory and governance framework

The intended purpose is a controlled artefact\. Any feature that moves the system towards autonomous diagnosis, treatment recommendation, investigation ordering, anaesthetic planning or proceed/postpone decisions can materially change the clinical risk and regulatory position and therefore requires formal reassessment before release\.

## 16\.1 Governance principles

- Clinical rules cannot self\-modify\. Changes require evidence review, version control, testing, clinical approval and release governance\.
- Prompts, models, terminology releases, mappings and validators are version\-controlled alongside clinical rules\.
- Clinician overrides are permitted where appropriate but must record rationale and must not delete underlying evidence\.
- A formal hazard log and incident pathway should cover missed red flags, false reassurance, incorrect normalisation, source conflict, automation bias, incomplete history, inappropriate advice and integration failure\.
- Regulatory classification and TGA pathway must be formally assessed before clinical supply/pilot where applicable and reassessed after material feature change\.

## 16\.2 Clinical accountability

The system supports but does not replace professional clinical judgement\. Final diagnosis, treatment, consent, anaesthetic planning and suitability\-to\-proceed decisions remain with appropriately qualified clinicians\. The clinician\-facing interface must expose uncertainty, source, conflicts and open actions to reduce automation bias\.

# 17\. End\-to\-end MVP workflow

__STEP__

__Actor/component__

__Action__

__State/output__

__Acceptance checkpoint__

1

Patient/booking workflow

Launch assessment using governed episode link

Session request

Correct subject/episode context

2

Session Service

Create session and pin release manifest

INITIALISE

Manifest recorded

3

Retrieval Service

Fetch permitted demographics, procedure, meds, allergies, problems, recent relevant results and prior anaesthetic data

Source snapshot

Source versions/times captured

4

Clinical State

Create assertions and normalise terminology/time

Assertion graph

No source lost

5

Reconciliation/Gap Engine

Construct working state, conflicts, active requirements and initial gap queue

Pre\-interview synthesis

Critical conflicts visible

6

Orchestrator

Select OPENING action

InterviewAction

No checklist\-first behaviour

7

Language Service \+ Validator

Generate and approve introduction/open invitation

Delivered turn

Action fidelity passes

8

Patient

Provides narrative

Raw turn

Exact input retained

9

Extractor

Create candidate events

Candidate assertions/cues

Schema valid

10

Clinical State

Attach provenance, reconcile and update facts/conflicts

Updated working state

No candidate directly authoritative

11

Gap/Safety Services

Recompute gaps and evaluate interrupt rules

Updated GapQueue / safety status

Critical interrupt pre\-empts routine flow

12

Orchestrator

Select next action from policy hierarchy

InterviewAction

Target gap/cue explicit

13

Language \+ Validator

Realise one natural turn and validate

Delivered turn

No unsupported claim

14

Loop

Repeat steps 8\-13 across domains

Adaptive conversation

Resolved data suppressed

15

Retrieval/Workflow

Create collateral/human tasks when patient cannot resolve material gap

OpenAction

Critical owner explicit

16

Closure Review

Check active requirements, conflicts, agenda and open actions

COMPLETE / COMPLETE\_WITH\_OPEN\_ACTIONS / HANDOFF

No hidden critical issue

17

Clinician UI

Review summary, sources, conflicts and open actions; verify/edit

Clinician decisions

Edits have provenance

18

FHIR Adapter

Project approved structured output and Provenance

Candidate Bundle

FHIR validation passes

19

Governed commit

Write approved data/tasks as configured

FHIR transaction result

Write\-back gate passed

20

Audit/metrics

Persist final events and safety/quality metrics

Closed audit trail

Session reproducible

# 18\. Development and deployment plan

__PHASE__

__Deliverable__

__Scope__

__Exit criteria__

0

Safety and data contracts

Freeze canonical schemas, intended purpose, critical rules, FHIR profiles, release manifest format

Clinical/governance sign\-off on v1\.0 contracts

1

Deterministic core

Session, assertion graph, requirements/gaps, reconciliation, safety gates, task ownership, audit

All existing deterministic regression cases pass without LLM

2

Text conversational shell

Text UI, extractor, InterviewAction planner, language realiser, validators

Scripted end\-to\-end synthetic cases pass

3

FHIR/source integration

Read selected source data and project candidate FHIR output

Round\-trip/provenance tests pass

4

Clinician review UI

Summary, source drill\-down, conflict/open\-action review, verification/edit

Human factors acceptance on representative cases

5

Simulation evaluation

Large synthetic \+ clinician\-authored scenario bank; adversarial language; accessibility cases

Predefined safety thresholds met

6

Silent/shadow pilot

Run on real workflow data without patient\-facing autonomous decisions where governance permits

Safety/accuracy/workflow metrics acceptable

7

Supervised patient pilot

Patient\-facing use with immediate human fallback and narrow intended purpose

Pilot protocol stop criteria not triggered; usability/safety acceptable

8

Scale/readiness

Operational hardening, regulatory pathway, support, monitoring and incident processes

Production readiness review

## 18\.1 Recommended implementation order

The deterministic clinical core should be built before the conversational language layer\. This allows requirements, state semantics, reconciliation, safety gates and closure to be tested independently of model behaviour\. The first LLM\-enabled implementation should be text\-only, with voice added after semantic and safety performance are understood\.

## 18\.2 Proposed deployment progression

1. Offline unit and property testing
2. Synthetic patient regression testing
3. Clinician\-authored adversarial scenario testing
4. Retrospective data evaluation where permitted
5. Prospective silent/shadow validation alongside usual care
6. Supervised patient\-facing pilot with immediate human fallback
7. Controlled scale\-up with continuous monitoring and rollback

# 19\. Verification and validation strategy

## 19\.1 Clinical dataset validation

- Independent two\-reviewer clinical review of all 343 concepts
- Formal domain\-by\-domain evidence extraction and citation confirmation
- Deduplication and harmonisation of overlapping concepts
- Consensus on M0/M1/conditional classifications
- Formal review of red\-flag and escalation rules
- Terminology mapping validation
- Patient wording usability testing
- High\-risk critical\-omission simulation

## 19\.2 Technical acceptance tests

__TEST\_ID__

__Area__

__Given__

__When__

__Then / pass criterion__

__Critical?__

TECH\-001

State integrity

Same patient turn submitted twice with same turn\_id

API processes retries

Only one logical state mutation occurs

Yes

TECH\-002

Provenance

A fact displayed to clinician

Lineage requested

Source assertion, source version, transformations and verification are retrievable

Yes

TECH\-003

Safety priority

Critical chest\-pain rule active

Next action requested

SAFETY\_INTERRUPT returned before any routine gap action

Yes

TECH\-004

Generation boundary

Action prohibits clearance

LLM drafts 'you are safe for surgery'

Validator blocks response

Yes

TECH\-005

Conflict

Patient and EMR disagree on anticoagulant dose

Reconciliation runs

Conflict remains explicit until governed resolution

Yes

TECH\-006

Unknown semantics

Patient cannot recall medication name

Gap engine updates

State is UNKNOWN/UNRESOLVED, never DENIED

Yes

TECH\-007

Question suppression

Current confirmed non\-time\-sensitive datum exists

Planner evaluates domain

No rediscovery question generated

No

TECH\-008

Patient correction

Patient corrects DVT to PE

Turn processed

New assertion added; old extraction retained; working fact updated

Yes

TECH\-009

Model failure

Extractor returns invalid schema repeatedly

Retry budget exhausted

Human/modality fallback, no clinical mutation

Yes

TECH\-010

Source outage

FHIR endpoint unavailable

Synthesis runs

Source marked UNAVAILABLE; absence not inferred

Yes

TECH\-011

Closure gate

Critical task exists without owner

Complete endpoint called

Completion rejected with blocking reason

Yes

TECH\-012

FHIR certainty

Unverified patient\-reported difficult airway exists

FHIR projection generated

Output preserves unverified/source\-qualified status and Provenance

Yes

TECH\-013

Manifest reproducibility

Completed session from prior release

Audit replay requested

Exact rules/prompts/models/terminology versions identifiable

Yes

TECH\-014

Privacy

Language action needs one medication fact

Prompt assembled

Unrelated diagnoses/documents are absent from model context

Yes

TECH\-015

Resume

Session paused with deferred topic

Session resumes

Deferred topic and gap queue preserved

No

TECH\-016

Human edit

Clinician changes reaction phenotype

Edit saved

Clinician assertion/provenance added without deleting patient assertion

Yes

## 19\.3 Primary evaluation outcomes

- Completeness against clinician\-derived reference history and configured mandatory requirements
- Critical omission rate
- False negative/incorrect negative assertion rate
- Conflict detection and reconciliation accuracy
- Medication reconciliation accuracy, especially high\-risk medicines and last\-dose timing
- Critical escalation sensitivity and false\-positive burden
- Clinician correction rate and time to review
- Patient completion, abandonment, comprehension and correction behaviour
- Question redundancy and conversational burden
- Equity of performance across tested user groups
- FHIR/provenance integrity and successful reconstruction of decisions

# 20\. Future capability opportunities

- Longitudinal perioperative state from referral through optimisation, surgery and recovery
- Clinical data\-quality engine for allergies, medicines, diagnoses, smoking status and advance care documents
- Automated retrieval of previous anaesthetic records or alert documentation after safety\-critical disclosures
- Governed preassessment triage to streamlined, nurse, anaesthetist, physician, pharmacist or multidisciplinary pathways
- Dynamic investigation and optimisation tasks for anaemia, diabetes, smoking, alcohol, nutrition, frailty, prehabilitation, pain and psychological support
- Clinician\-approved patient preparation assistant for fasting, medicines, CPAP/device reminders, appointments, transport and escort requirements
- Reusable perioperative passport for difficult airway, MH susceptibility, serious allergy, devices and previous complications
- Patient\-generated data such as selected BP, weight, glucose/CGM or CPAP adherence with explicit provenance
- Research and outcomes platform linking structured history, optimisation, care and outcomes under separate consent/governance
- Future predictive models for cancellation, unexpected admission, ICU use, complications, length of stay or readmission, treated as separate validated medical decision\-support products

# 21\. Open design decisions before pilot

- Final clinical owner and governance committee for the dataset/rules
- Hosting and model\-provider architecture, including data residency and contractual controls
- Exact source systems available for pre\-interview synthesis at the pilot site
- Local FHIR profiles and write\-back destinations
- Which validated scores are enabled in MVP and which remain input\-only
- Operational destinations and response\-time expectations for each escalation class
- Patient identity and authentication workflow
- Interpreter, proxy and accessibility workflow
- Transcript/audio retention policy
- Regulatory classification and clinical trial/pilot pathway
- Pilot site, patient cohort, sample size and predefined stopping rules

# 22\. Definition of MVP

__MVP definition  
__A text\-first, patient\-facing conversational history system for the defined adult elective/semi\-elective population that can synthesise selected existing clinical data, conduct a natural adaptive history against Clinical Dataset v1\.0, preserve provenance and uncertainty, identify conflicts and safety escalations, create owned tasks, generate a clinician\-reviewable structured summary and project approved data to FHIR without making autonomous diagnosis, treatment or fitness decisions\.

## 22\.1 MVP must include

- Pinned ReleaseManifest
- Canonical assertion and WorkingFact model
- Requirement activation and information\-gap engine
- Deterministic safety/escalation and closure gates
- Conversation orchestrator and InterviewAction contracts
- Bounded LLM extraction and language realisation
- Pre\-delivery validator stack
- Patient agenda and cue handling
- Medication/allergy/previous anaesthetic safety handling
- Clinician review interface with provenance and conflicts
- Audit/event trail and observability
- FHIR candidate projection with Provenance
- Human handoff and pause/resume

## 22\.2 MVP may defer

- Voice interaction
- Broad automated investigation ordering
- Predictive outcome models
- Longitudinal perioperative passport across organisations
- Automated optimisation pathways
- Advanced multimodal/device integrations
- Cross\-LHN deployment and federated analytics

# 23\. Reference architecture summary

Patient / clinician UI  
        ↓  
API Gateway \+ Session Service  
        ↓  
Source Retrieval → Assertion Graph → Reconciliation → Working State  
        ↓                         ↓  
Terminology Service       Requirements / Gap Engine  
        └──────────────┬──────────┘  
                       ↓  
                 Safety Service  
                       ↓  
             Conversation Orchestrator  
                       ↓  
                 InterviewAction  
                       ↓  
                  LLM Realiser  
                       ↓  
                 Validator Stack  
                       ↓  
                     Patient  
  
Human Workflow/Tasks ← open actions/conflicts/escalations → Clinician Review  
                       ↓  
                FHIR projection/write\-back  
                       ↓  
          Audit \+ Provenance \+ Observability

# Appendix A\. Canonical object definitions

__OBJECT__

__Purpose__

__Required fields__

__Key invariants__

__FHIR projection__

Session

Top\-level assessment instance

session\_id; subject\_ref; episode\_context; status; release\_manifest; created\_at

One pinned release manifest per session; status explicit

Encounter/QuestionnaireResponse context where appropriate

Assertion

Atomic sourced statement

assertion\_id; subject; concept/value; assertion\_state; source; speaker; event\_time; assertion\_time; certainty; provenance

Never source\-less; never silently overwritten

Condition/Observation/MedicationStatement/etc \+ Provenance

WorkingFact

Current governed interpretation

fact\_id; concept/value; verification; supporting\_assertions; dissenting\_assertions; freshness

Must trace to assertions; may be unresolved

Resource\-specific FHIR representation

Conflict

Disagreement requiring classification

conflict\_id; assertion\_ids; type; materiality; status; resolution

Material conflict cannot be silently resolved

DetectedIssue/Task/Flag depending semantics

Requirement

Clinical information obligation

requirement\_id; activation\_rule; requiredness; minimum\_state; freshness\_rule

Versioned and auditable

Questionnaire/PlanDefinition mapping optional

RequirementState

Current satisfaction state

requirement\_id; information\_state; evidence\_refs; evaluated\_at

UNKNOWN \!= DENIED \!= NOT\_ASKED

Internal; QuestionnaireResponse where relevant

InformationGap

Unresolved requirement need

gap\_id; type; requirement\_id; priority; resolution\_options; status

Only active requirements create gaps

Task where workflow action required

InterviewAction

Governed next conversational act

action\_id; type; targets; purpose; permitted/prohibited content; max\_questions; fallback

Must exist before patient\-facing generation

Internal

Cue

Clinical/emotional/communication signal

cue\_id; type; salience; source\_turn; status

Cue is not diagnosis

Observation/Flag only when clinically appropriate

PatientAgendaItem

Patient concern/question/goal

agenda\_id; text; priority; status; disposition

High\-priority unresolved item blocks closure

QuestionnaireResponse/Communication as appropriate

OpenAction

Human/retrieval obligation

task\_id; type; owner; priority; status; due\_context; reason

Critical action must have owner

Task

Turn

Actually delivered/received interaction

turn\_id; speaker; modality; content; timestamps; confidence

Delivered text retained separately from drafts

Communication/QuestionnaireResponse selectively

ReleaseManifest

Pinned configuration

clinical\_dataset\_version; rules\_version; terminology\_version; prompt\_version; model\_ids; validator\_version

Immutable for session except governed migration

Provenance metadata

# Appendix B\. Relational schema reference

__TABLE__

__COLUMN__

__TYPE__

__NULL?__

__KEY / INDEX__

__SEMANTICS__

__FHIR relevance__

session

session\_id

UUID

No

PK

Assessment identifier

Encounter/QuestionnaireResponse context

session

subject\_ref

TEXT

No

IDX

Canonical patient reference

Patient/\{id\}

session

encounter\_ref

TEXT

Yes

IDX

Encounter reference if available

Encounter/\{id\}

session

procedure\_context\_json

JSON

No

Planned procedure/site/date context

ServiceRequest/Procedure/Appointment

session

status

ENUM

No

IDX

INITIALISE|ACTIVE|PAUSED|COMPLETE|HANDOFF|STOPPED

Internal

session

manifest\_id

UUID

No

FK

Pinned release manifest

Provenance metadata

session

created\_at

TIMESTAMPTZ

No

IDX

Creation time

meta/Provenance

assertion

assertion\_id

UUID

No

PK

Atomic assertion

Resource element/provenance source

assertion

session\_id

UUID

No

FK,IDX

Owning session

Context

assertion

subject\_ref

TEXT

No

IDX

Subject

Patient reference

assertion

concept\_json

JSON

No

Code/display/system \+ mapping state

CodeableConcept

assertion

value\_json

JSON

Yes

Typed value

FHIR datatype/resource\-specific

assertion

assertion\_state

ENUM

No

IDX

AFFIRMED|NEGATED|UNCERTAIN|UNKNOWN|DECLINED|CONDITIONAL

verification semantics

assertion

source\_json

JSON

No

Source type/ref/speaker/document/turn

Provenance\.entity/agent

assertion

event\_time\_json

JSON

Yes

Exact/range/approximate clinical time

effective\[x\]/onset\[x\]

assertion

certainty

ENUM

No

EXPLICIT|INFERRED\_LOW|INFERRED\_MODERATE|UNRESOLVED

Do not inflate in projection

assertion

provenance\_json

JSON

No

Extractor/model/rule/source offsets

Provenance

assertion

supersedes\_assertion\_id

UUID

Yes

FK

Correction chain

Provenance\.entity

working\_fact

fact\_id

UUID

No

PK

Governed interpretation

FHIR candidate target

working\_fact

session\_id

UUID

No

FK,IDX

Owning session

Context

working\_fact

concept\_json

JSON

No

IDX\-ish

Canonical concept

CodeableConcept

working\_fact

value\_json

JSON

Yes

Current governed value

FHIR datatype

working\_fact

verification\_state

ENUM

No

IDX

CONFIRMED|UNCONFIRMED|CONFLICTED|STALE|UNKNOWN

verificationStatus/profile

working\_fact

freshness\_json

JSON

Yes

Threshold, observed age, status

Internal/provenance

working\_fact

version

INTEGER

No

Optimistic/version lineage

meta\.versionId analogue

fact\_assertion\_link

fact\_id

UUID

No

PK/FK

Working fact

fact\_assertion\_link

assertion\_id

UUID

No

PK/FK

Supporting/dissenting assertion

fact\_assertion\_link

role

ENUM

No

SUPPORTS|DISSENTS|SUPERSEDES

Provenance relationship

conflict

conflict\_id

UUID

No

PK

Conflict

DetectedIssue/Task candidate

conflict

session\_id

UUID

No

FK,IDX

Owning session

conflict

type

ENUM

No

VALUE|NEGATION|TEMPORAL|IDENTITY|TERMINOLOGY|SOURCE|PROCEDURE

conflict

materiality

ENUM

No

IDX

LOW|MODERATE|HIGH|CRITICAL

conflict

status

ENUM

No

IDX

OPEN|RESOLVED|ACCEPTED\_RISK

conflict

resolution\_json

JSON

Yes

Resolution, actor, evidence

Provenance

requirement\_state

requirement\_state\_id

UUID

No

PK

Activated requirement instance

Questionnaire/PlanDefinition optional

requirement\_state

session\_id

UUID

No

FK,IDX

Owning session

requirement\_state

requirement\_id

TEXT

No

IDX

Versioned clinical dataset requirement

requirement\_state

information\_state

ENUM

No

IDX

12\-state information taxonomy

requirement\_state

evidence\_refs\_json

JSON

Yes

Fact/assertion evidence

requirement\_state

evaluated\_at

TIMESTAMPTZ

No

Evaluation time

information\_gap

gap\_id

UUID

No

PK

Gap

Task if workflow required

information\_gap

requirement\_state\_id

UUID

No

FK,IDX

Parent requirement state

information\_gap

gap\_type

ENUM

No

IDX

Missing/stale/conflict/etc

information\_gap

priority\_score

DECIMAL

No

IDX

Deterministic prioritisation result

information\_gap

status

ENUM

No

IDX

OPEN|RESOLVED|DEFERRED|HANDOFF

information\_gap

resolution\_options\_json

JSON

No

ASK|CONFIRM|RETRIEVE|HANDOFF etc

interview\_action

action\_id

UUID

No

PK

Action contract

interview\_action

session\_id

UUID

No

FK,IDX

Owning session

interview\_action

action\_type

ENUM

No

IDX

Controlled action vocabulary

interview\_action

contract\_json

JSON

No

Targets, permitted/prohibited content, max questions

interview\_action

status

ENUM

No

SELECTED|DELIVERED|CANCELLED

turn

turn\_id

UUID

No

PK

Interaction turn

Communication selectively

turn

session\_id

UUID

No

FK,IDX

Owning session

turn

action\_id

UUID

Yes

FK

Agent action that generated turn

turn

speaker

ENUM

No

PATIENT|AGENT|CLINICIAN|PROXY|SYSTEM

Communication\.participant

turn

modality

ENUM

No

TEXT|VOICE|ASSISTED

turn

content

TEXT

No

Exact received/delivered content

Communication\.payload

turn

confidence

DECIMAL

Yes

ASR/input confidence

turn

occurred\_at

TIMESTAMPTZ

No

IDX

Turn time

sent/received

task

task\_id

UUID

No

PK

Workflow obligation

Task

task

session\_id

UUID

No

FK,IDX

Owning session

task

type

ENUM

No

RETRIEVAL|CLINICAL\_REVIEW|SAFETY|IDENTITY|PROCEDURE|OTHER

Task\.code

task

owner\_ref

TEXT

Yes

IDX

Explicit owner

Task\.owner

task

priority

ENUM

No

IDX

ROUTINE|URGENT|CRITICAL

Task\.priority

task

status

ENUM

No

IDX

OPEN|ACKNOWLEDGED|RESOLVED|CANCELLED

Task\.status

task

reason\_json

JSON

No

Why task exists and targets

Task\.reasonCode/description

cue

cue\_id

UUID

No

PK

Cue

cue

session\_id

UUID

No

FK,IDX

Owning session

cue

turn\_id

UUID

No

FK

Source turn

cue

cue\_type

ENUM

No

CLINICAL|EMOTIONAL|COMMUNICATION|SAFETY

cue

salience

ENUM

No

LOW|MODERATE|HIGH|CRITICAL

cue

status

ENUM

No

OPEN|ADDRESSED|ESCALATED

patient\_agenda\_item

agenda\_item\_id

UUID

No

PK

Agenda item

patient\_agenda\_item

session\_id

UUID

No

FK,IDX

Owning session

patient\_agenda\_item

text

TEXT

No

Patient's concern/question/goal

patient\_agenda\_item

priority

ENUM

No

LOW|MODERATE|HIGH

patient\_agenda\_item

status

ENUM

No

OPEN|ADDRESSED|DEFERRED|HANDOFF

release\_manifest

manifest\_id

UUID

No

PK

Runtime configuration identity

Provenance

release\_manifest

manifest\_json

JSON

No

All version IDs \+ hashes

Provenance

release\_manifest

created\_at

TIMESTAMPTZ

No

Release creation

# Appendix C\. Non\-functional requirements

__NFR\_ID__

__Domain__

__Requirement__

__MVP acceptance target__

NFR\-001

Availability

Session state must survive service restart and transient integration failure

No loss of acknowledged turn/state in resilience tests

NFR\-002

Latency

Conversational response latency should support natural dialogue

Text p95 target <=4 s excluding external source retrieval; voice target to be validated

NFR\-003

Consistency

Clinical state mutations are serialised per session

Concurrent\-turn test produces deterministic final state

NFR\-004

Traceability

Every clinical fact/action is traceable to source/rule/model/version

100% of sampled facts/actions have lineage

NFR\-005

Security

Least privilege, strong authentication, encryption and secrets management

Threat model and security review passed

NFR\-006

Privacy

Data minimisation and purpose\-specific retention

No unnecessary transcript/audio retained in configured MVP

NFR\-007

Accessibility

Text and assisted modes supported; pathway for interpreter/human handoff

Accessibility/human factors test passed

NFR\-008

Recoverability

Paused/interrupted sessions can resume without losing obligations

Resume regression suite passes

NFR\-009

Versioning

Rules/prompts/models/terminology pinned and rollback\-capable

Release manifest reproduced from any completed session

NFR\-010

Testability

Deterministic policy components independently testable from LLM

Regression suite can run with mocked model outputs

NFR\-011

Interoperability

FHIR output validates against selected base/local profiles

100% candidate MVP bundles pass configured validator

NFR\-012

Auditability

Actual delivered content and clinician edits retained

Audit reconstruction test passes

# Appendix D\. Key evidence and standards register

- ANZCA\. PG07 Guideline on pre\-anaesthesia consultation and patient preparation\. 2024\.
- ANZCA\. PG69 Guideline on perioperative hypersensitivity reactions\. 2025\.
- American Society of Anesthesiologists\. Basic Standards for Preanesthesia Care\.
- 2024 AHA/ACC Guideline for Perioperative Cardiovascular Management for Noncardiac Surgery\.
- Society of Anesthesia and Sleep Medicine guideline on preoperative screening and assessment of adult patients with obstructive sleep apnoea\.
- Centre for Perioperative Care guidance on obstructive sleep apnoea, frailty, perioperative anaemia and related perioperative pathways\.
- ESPEN guideline on clinical nutrition in surgery, 2025 update\.
- Royal College of Anaesthetists GPAS guidance relevant to pain, frailty and cognitive screening\.
- Ahmadian et al\. consensus/core dataset work for preoperative assessment\.
- Electronic preoperative assessment literature including ePAQ and PATCH\.
- AI\-DOCS and related conversational/LLM perioperative history\-taking literature identified in the project scoping review\.
- Australian Digital Health Agency: AU Core Implementation Guide, AUCDI, SNOMED CT\-AU and AMT interoperability guidance\.
- HL7 FHIR R4: Patient, Encounter, Questionnaire, QuestionnaireResponse, Condition, Observation, MedicationStatement, MedicationRequest, AllergyIntolerance, Procedure, FamilyMemberHistory, Goal, Consent, DocumentReference, RiskAssessment, Task, DetectedIssue, Flag, Provenance, AuditEvent and Bundle\.
- HL7 FHIR Structured Data Capture Implementation Guide\.
- Therapeutic Goods Administration guidance on software\-based medical devices, clinical decision support software and AI\-enabled medical software\.

The detailed evidence register and source URLs are maintained in the companion workbook and scoping\-review artefacts\. Formal implementation should refresh all time\-sensitive clinical and regulatory sources before release\.

# Appendix E\. Companion artefacts

__Artefact__

__Role__

Perioperative Conversational AI Scoping Review and Requirements

Evidence method, scope and high\-level requirements

Perioperative Conversational AI Clinical Dataset v1\.0

343 atomic clinical concepts and evidence\-derived logic

Clinical Interview Process Dataset v1\.0

Machine\-testable history\-taking behaviours

Interoperability and Terminology v1\.0

FHIR/Australian standards mappings and terminology design

Provenance, Uncertainty and Reconciliation v1\.0

Assertion, source authority, conflict and reconciliation rules

Pre\-Interview Synthesis and Gap Engine v1\.0

Requirement activation, information states and ask/confirm/suppress logic

Conversation Orchestrator v1\.0

State machine, policy hierarchy, InterviewAction contract and turn pipeline

Safety, Escalation and Clinical Boundaries v1\.0

Clinical boundary matrix, escalation taxonomy and safety assurance

Executable Technical Specification v1\.0

Services, APIs, events, validators, stores, observability and MVP sequence

Canonical Data Model and JSON Schema v1\.0

Canonical objects, relational model, enums, invariants and executable JSON schemas

