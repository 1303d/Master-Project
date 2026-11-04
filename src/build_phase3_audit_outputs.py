"""Write the Sprint 4 Phase 2 closure + Phase 3 taxonomy-evaluation audit outputs (read-only over inputs).

    .venv/bin/python src/build_phase3_audit_outputs.py

Inputs (never modified): the frozen Sprint 4 snapshot, Sprint 4 features, assembled names, the P1 evidence
reconciliation v2, the recovered prepared_mentions.csv and the local ESCO v1.2.1 / O*NET 31.0 libraries.
Outputs go to OUT (refuses to overwrite). Two kinds of content, kept in separate columns / files:
  * computed   deterministic metrics recomputed here from the inputs (hashes in manifest.json)
  * ai_review  judgments written by Claude Code (claude-opus-5-5) after reading the evidence in the audit
               conversation of 2026-11-04. AI-GENERATED, NOT HUMAN-VALIDATED. Every decision is pending approval.
Nothing here changes topics, memberships, aliases, names, links, embeddings or clustering. No API calls.
"""
import hashlib
import itertools
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN = "hdbscan_10_umap10_ms1_2026-10-23"
INP = ROOT / f"data/processed/sprint4_input_{RUN}"
FEAT = ROOT / f"data/processed/sprint4_features_{RUN}"
NAMES = ROOT / f"data/processed/sprint4_naming_{RUN}/assembled_topic_naming_v1_20261104T003642Z/results.csv"
REVIEW = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1"
P1V2 = REVIEW / "p1_review/p1_evidence_reconciliation_v2"
MENTIONS = ROOT / "data/interim/prepared_mentions.csv"
REF = Path(os.path.expanduser("~/Desktop/testing/references"))
OUT = REVIEW / "phase2_phase3_audit_v1"
LABEL = "AI-GENERATED, NOT HUMAN-VALIDATED (pending approval)"
P1 = "T0018 T0040 T0057 T0103 T0104 T0121 T0135 T0140 T0162 T0171 T0172 T0177 T0190 T0192 T0193 T0211 T0229 T0234 T0239 T0293".split()
L = lambda s: [t for t in s.split("|") if t]

# ----------------------------------------------------------------------------------------------------------
# AI review data (from the audit conversation; see report.md for the reasoning)
# ----------------------------------------------------------------------------------------------------------
LINKS = {  # skill: (verdict, evidence meaning, valid skill?)
    "rt": ("CONFIRMED_INCORRECT", "NDT method list 'PT, MT, UT, RT, ET'", "yes"),
    "sem": ("CONTEXT_DEPENDENT", "3 senses: analytical-technique list / media planning / 'SEO/SEM'", "yes"),
    "dmp": ("CONFIRMED_INCORRECT", "intrusion hardware list; audience data tools", "yes"),
    "dmps": ("CONFIRMED_INCORRECT", "programmatic ad ecosystem 'DSPs, SSPs, DMPs'", "yes"),
    "unity": ("CONFIRMED_INCORRECT", "game engine 'Unreal Engine or Unity'", "yes"),
    "scales": ("CONFIRMED_INCORRECT", "kitchen equipment 'microwaves, and scales'", "equipment mention"),
    "scaling": ("CONFIRMED_INCORRECT", "network scaling", "yes"),
    "ifrs": ("CONFIRMED_INCORRECT", "accounting standards", "yes"),
    "ifsp": ("CONFIRMED_INCORRECT", "special-education plan 'IFSP or IEP'", "yes"),
    "ams": ("LIKELY_INCORRECT", "agency equipment application", "yes"),
    "nam": ("CONFIRMED_INCORRECT", "Cisco product list", "yes"),
    "asa": ("UNVERIFIABLE", "bare 'ASA'", "unclear"),
    "dock carts": ("CONFIRMED_INCORRECT", "warehouse carts", "equipment mention"),
    "box": ("CONFIRMED_INCORRECT", "Box software next to Oracle HCM", "yes"),
    "boating": ("CONTEXT_DEPENDENT", "camp counselor teaching activities (plausible)", "yes"),
    "stocking": ("LIKELY_INCORRECT", "retail 'truck unload, stocking'", "task"),
    "timber": ("LIKELY_INCORRECT", "structural design with wood/timber", "yes"),
    "dressing changes": ("CONFIRMED_INCORRECT", "wound care", "yes"),
    "pressing": ("CONFIRMED_INCORRECT", "garment pressing/steaming", "yes"),
    "garment pressing": ("LIKELY_INCORRECT", "press garments", "yes"),
    "lens options": ("CONFIRMED_INCORRECT", "eyewear lens options", "yes"),
    "extrusion press": ("LIKELY_INCORRECT", "extrusion press machining", "yes"),
    "body assembly": ("CONFIRMED_INCORRECT", "automotive body assembly tooling", "yes"),
    "design experience": ("LIKELY_INCORRECT", "generic 'Must have design experience'", "generic"),
    "site development": ("CONTEXT_DEPENDENT", "'focused on Site development' (sense unclear)", "unclear"),
    "template building": ("LIKELY_INCORRECT", "document templates", "yes"),
    "filtering": ("CONFIRMED_INCORRECT", "DSP 'software channeling, filtering'", "yes"),
    "tdm": ("CONFIRMED_INCORRECT", "telephony 'TDM, VoIP and CTI'", "yes"),
    "formulation": ("CONFIRMED_INCORRECT", "lab informatics, molecule analysis", "yes"),
    "waxing": ("CONFIRMED_INCORRECT", "car detailing; dental wax-up", "yes"),
    "styling": ("LIKELY_INCORRECT", "fashion styling", "yes"),
    "food styling": ("CONFIRMED_INCORRECT", "food photography styling", "yes"),
    "style frames": ("CONFIRMED_INCORRECT", "motion-graphics style frames", "yes"),
    "spray booth": ("LIKELY_INCORRECT", "booth cleaning/maintenance", "yes"),
    "hand sewing": ("CONFIRMED_INCORRECT", "sewing, not knitting", "yes"),
    "classical hand analysis": ("CONFIRMED_INCORRECT", "structural analysis next to NASTRAN/PATRAN", "yes"),
    "milestone": ("CONFIRMED_INCORRECT", "video-surveillance software list", "yes"),
    "logs": ("CONFIRMED_INCORRECT", "IT logs and monitoring", "yes"),
}
UNEXPLAINED_EXACT = {"unity", "scales", "design experience"}

KEYS = {  # key: (senses, problem, treatment, confidence)
    "sem": ("analytical technique list | media planning | SEO/SEM", "2 domains in one key; linked to SEO", "split by context; do not expand sense 1", "High"),
    "dmp": ("intrusion hardware list | audience data tools", "2 domains; dance-therapy link", "split; group sense 2 with dmps", "High"),
    "prisma": ("media tool DDS/Prisma | vulnerability-management tool | bare (unknown)", "2 product senses + 1 unknown", "split senses 1-2; sense 3 needs context", "Medium"),
    "lis": ("SAP reporting system | lab communication system", "2 domains", "split", "High"),
    "google": ("office suite | cloud platform", "productivity vs cloud", "split", "High"),
    "assembly": ("programming language | mechanical assembly", "programming vs manufacturing", "split", "High"),
    "waxing": ("car detailing | dental wax-up", "2 domains; hair-removal link", "split", "High"),
    "painting": ("trade/maintenance painting (9) | fine art (1)", "topic name implies art; key is mostly trade", "treat trade sense as primary; reassign or rename", "Medium"),
    "templates": ("C++ templates/STL | shop fabrication templates", "software vs tooling (R4 alias template->templates)", "split", "Medium"),
}

ACRO = {
    "RESOLVED_WITH_EVIDENCE": "d3:JavaScript visualization library|enil:American Reading Company literacy solution|fsk:modulation scheme|ideal:CRM database product|oas:API contract language|ohs:Occupational Health & Safety (job title)|srm:disaster-recovery tool|tas:ISV product for Dynamics 365|urs:validation document type|waf:security system",
    "DOMAIN_IDENTIFIED_ONLY": "aas:QA batch-record system|ams:agency equipment application|bo:SAP analytics|diee:military intelligence systems|dvoms:automotive diagnostic equipment|e1 ifm:finance system|pds:finance system|eos:management meeting method|h&mbs:chemical process deliverable|hld:network design documentation|ias:structural analysis tool|icief:analytical chemistry technique|mcs:Citrix provisioning|mft:Sterling integration tool|mmrs:SAP module|msd:immunoassay technique|neuro:OR nursing specialty|par:loan-workout credit process|pkms:warehouse system|poss:warehouse system|powm:warehouse system|r&r:quality engineering method|rprm:video-conferencing infrastructure|sqcdm:manufacturing performance aspects|tara:power planning software|tee:cardiac imaging procedure|tmf:clinical trial documentation|toas:legal document tables|topaz:mainframe tool|wds:internal shop system",
    "POSSIBLE_NON_SKILL": "afe:finance document type|asee:standards body/standard|cap:regulatory agency (stated)|cola:regulatory agency (stated)|chap:hospice regulator/program|fdo:parts sourcing channel|hysa:personal-finance product|ib:pharmacovigilance document|pfw:company-internal system|psi:healthcare quality indicator|spine:surgical specialty|tars:nursing record|teoa:company lean program",
    "STILL_AMBIGUOUS": "bob:'BOB utilization'|dmp:2 senses|gpm:clinical app vs Sterling GPM|lis:2 senses|mi:'AI and MI'|ramp:'Assist with Ramp'|s.g.m:retail program",
    "INSUFFICIENT_SOURCE_CONTEXT": "scd's:posting text not found locally",
}

TOPICS54 = {  # topic: (group, coherent core, main issue, proposed action, confidence)
    "T0305": ("A", "ms drg, drgs, hcpcs, mcg", "c/g code mix (cogs, dlg, amag, ukg, cobol, bgp, paga)", "INVESTIGATE_CLUSTER", "High"),
    "T0340": ("A", "", "acronym noise (cato, ciso, qbo, miro, hmo, catv, npv)", "INVESTIGATE_CLUSTER", "High"),
    "T0245": ("A", "air handling units, computer room air handlers", "'air' word cluster (airtable, air mobility command, yardi)", "INVESTIGATE_CLUSTER", "High"),
    "T0209": ("A", "", "'x' letter cluster (nx, idx, fax, rexx, ifix, zabbix, kronos)", "INVESTIGATE_CLUSTER", "High"),
    "T0237": ("A", "evt, pvt, dvt", "3-letter mix (cpt, dbt, mwt, eset, ent, revit)", "INVESTIGATE_CLUSTER", "High"),
    "T0262": ("A", "as9100, ts16949, iatf16949, ich q7/q9", "digit forms (five9, 7ks, rapid7, as400, ca7, j1939)", "INVESTIGATE_CLUSTER", "Medium"),
    "T0338": ("A", "", "acronym noise (ftb, ftp, ftth, bbb, ftir, gasb)", "INVESTIGATE_CLUSTER", "High"),
    "T0155": ("A", "ci/cd, ci/cd tooling, pipelines, gitlab ci/cd, circleci", "c-prefix noise (cics, ce, i2c, cdp, c2ie)", "POTENTIAL_SPLIT", "Medium"),
    "T0287": ("A", "retention and incentive programs", "joint commission, commissioning, document retention", "POTENTIAL_SPLIT", "Medium"),
    "T0251": ("A", "", "-pc/-c acronym noise (poc, ipc, spc, nesc, ipsec)", "INVESTIGATE_CLUSTER", "High"),
    "T0328": ("A", "landscaping", "galvanizing/corrosion; '... products'", "POTENTIAL_SPLIT", "Medium"),
    "T0266": ("A", "network switches", "switchgear, relay settings, AV amps", "POTENTIAL_SPLIT", "Medium"),
    "T0319": ("A", "environmental management; civil plan review", "sustainability/CSR vs plan review; long name", "POTENTIAL_SPLIT", "Low"),
    "T0088": ("A", "GxP family (gmp, glp, gvp, cgmp, galp, gtp)", "gcp = Google Cloud vs Good Clinical Practice; g code, gds, gd&t", "POTENTIAL_SPLIT", "Medium"),
    "T0231": ("A", "", "Q-prefix noise (qms, qdro, qradar, qlik, qtof, qpsk)", "INVESTIGATE_CLUSTER", "High"),
    "T0372": ("A", "40cfr, 21cfr820, 49cfr, 29cfr 1910/1926", "10g/25g/40g, on24, 10 key", "POTENTIAL_SPLIT", "Medium"),
    "T0250": ("A", "document management/control/automation", "category management, taxonomy, category theory, genus", "POTENTIAL_SPLIT", "Medium"),
    "T0214": ("A", "load balancing / F5", "concurrency (software); loaders (equipment)", "POTENTIAL_SPLIT", "Medium"),
    "T0194": ("A", "child/human development", "HR L&D; motivation/self-management traits", "POTENTIAL_SPLIT", "Medium"),
    "T0374": ("A", "cvad, avd, vdi", "lvad, mvpd, ecovadis, cva, ada, icd 10", "INVESTIGATE_CLUSTER", "High"),
    "T0167": ("A", "event planning/logistics/marketing", "event streaming/sourcing/programming; kaizen events", "POTENTIAL_SPLIT", "High"),
    "T0205": ("A", "subcontractor management", "picc/central line, routing, mooring lines", "POTENTIAL_SPLIT", "High"),
    "T0276": ("A", "hlsl, glsl, tcl, caml, raml, jcl, ddl, uml", "bls/acls, dol, aml, mpls, lenel", "POTENTIAL_SPLIT", "Medium"),
    "T0253": ("A", "mq, ibm mq, rabbitmq, amqp, amazon mq, bullmq", "IQ/OQ/PQ; chip/rna/atac seq; apqp; mosaiq", "POTENTIAL_SPLIT", "High"),
    "T0272": ("A", "", "-ms acronyms of different systems (cmms, lms, wms, cms, jms, llms)", "INVESTIGATE_CLUSTER", "High"),
    "T0295": ("A", "xendesktop, xenapp, videsktop, anydesk", "xdsl, xdr, xsd, x, zendesk, chemcad", "POTENTIAL_SPLIT", "Medium"),
    "T0273": ("A", "", "'ad' prefix (active directory, ADLs, Oracle ADF)", "INVESTIGATE_CLUSTER", "High"),
    "T0371": ("A", "", "'ds' prefix (dsc, dsps, dsss, dsur, dsl, dhec)", "INVESTIGATE_CLUSTER", "High"),
    "T0191": ("B", "clinical specialties + lab immunology", "broad; weak 'ach'", "POTENTIAL_SPLIT", "Medium"),
    "T0198": ("B", "emr (5)", "-r acronyms: AP/AR, irr, cvr, ctr, ibnr", "INVESTIGATE_CLUSTER", "High"),
    "T0012": ("B", "web front-end", "few misfits (webex, kotlin/swift, generic navigation)", "KEEP_CANDIDATE", "High"),
    "T0058": ("B", "forklift/lift/truck operation", "none material", "KEEP_CANDIDATE", "High"),
    "T0132": ("B", "fire protection/alarms", "surveillance; EMI/EMC; other 'protection'", "POTENTIAL_SPLIT", "High"),
    "T0050": ("B", "hand/power tools, machining", "capcut, raiser's edge, kitchen knives, excavators", "KEEP_CANDIDATE", "Medium"),
    "T0039": ("B", "cardiac monitoring", "phlebotomy; ultrasound; polysomnography", "POTENTIAL_SPLIT", "Medium"),
    "T0137": ("B", "sop", "-p acronyms (abap, osp, iep, arp 4754, usp 800)", "INVESTIGATE_CLUSTER", "High"),
    "T0084": ("B", "structural/construction", "part design; metals; metal/c; WBS", "POTENTIAL_SPLIT", "Medium"),
    "T0255": ("B", "scoping", "motions practice, practicepanther, pointclickcare, range of motion", "POTENTIAL_SPLIT", "Medium"),
    "T0322": ("B", "", "game engines vs runbooks vs IBM RPG vs pitchbooks", "INVESTIGATE_CLUSTER", "High"),
    "T0063": ("B", "cleaning/sterilization", "sauteing, pet grooming, vacuum forming, bed baths", "KEEP_CANDIDATE", "Medium"),
    "T0043": ("B", "telephony/phone support", "telemetry, telehealth, telework, telehandler", "POTENTIAL_SPLIT", "Medium"),
    "T0206": ("B", "airway/ventilation/critical care", "broad but clinical", "KEEP_CANDIDATE", "Medium"),
    "T0003": ("B", "thinking skills", "ladder logic, logical equivalence checking, notion, idea", "KEEP_CANDIDATE", "Medium"),
    "T0077": ("B", "mobile", "generic 'technology' words", "KEEP_CANDIDATE", "Medium"),
    "T0161": ("B", "rpa, jira", "regulation acronyms (rcra, ccpa, cfra, obra)", "INVESTIGATE_CLUSTER", "High"),
    "T0158": ("B", "dental", "hand/personal/sleep hygiene", "KEEP_CANDIDATE", "High"),
    "T0027": ("B", "math", "formulary, calculus removal, advanced directives", "KEEP_CANDIDATE", "Medium"),
    "T0078": ("B", "speech-language pathology", "active listening, dictation, voice picking", "KEEP_CANDIDATE", "Medium"),
    "T0075": ("B", "imaging", "'examination' words (cross examination, pelvic exams)", "KEEP_CANDIDATE", "Medium"),
    "T0187": ("B", "databricks, hadoop, data lake, kafka", "datadog, atlassian, metaverse; near-dup T0098", "POTENTIAL_MERGE", "Low"),
    "T0059": ("B", "personal/investment planning", "corporate finance + accounting principles", "POTENTIAL_SPLIT", "Low"),
    "T0015": ("B", "languages", "language environment (IBM LE), currency translation, textura", "KEEP_CANDIDATE", "High"),
    "T0131": ("B", "storage/backup", "pacs, filevine, hibernate, ram, copy machines", "KEEP_CANDIDATE", "Medium"),
    "T0316": ("B", "", "P-letters (ppap, ppe, ppo) + APIs + ldap/olap", "INVESTIGATE_CLUSTER", "High"),
}

PAIRS = {
    "STRONG_MERGE_CANDIDATE": "T0001~T0005 T0139~T0197 T0204~T0347 T0065~T0147 T0014~T0109",
    "POSSIBLE_MERGE": "T0098~T0284 T0098~T0223 T0098~T0187 T0098~T0173 T0223~T0284 T0187~T0284 T0136~T0179 T0016~T0072 T0006~T0072 T0054~T0085 T0026~T0070 T0277~T0353 T0059~T0317 T0059~T0296 T0080~T0283 T0123~T0181 T0007~T0263",
    "SIMILAR_BUT_DISTINCT": "T0252~T0256 T0079~T0085 T0017~T0033 T0017~T0113 T0042~T0284 T0007~T0098 T0007~T0173 T0031~T0036 T0031~T0119 T0044~T0119 T0056~T0119 T0115~T0336 T0129~T0252 T0252~T0327 T0242~T0259 T0049~T0242 T0054~T0059 T0054~T0064 T0061~T0125 T0012~T0125",
    "DO_NOT_MERGE_CROSS_DOMAIN": "T0020~T0259 T0005~T0078 T0038~T0054 T0086~T0125 T0062~T0308 T0181~T0239 T0193~T0239 T0140~T0293 T0050~T0192 T0050~T0293 T0084~T0190 T0172~T0192",
    "DO_NOT_MERGE_NOISE": "T0162~T0211 T0040~T0211 T0018~T0211 T0018~T0162 T0104~T0211 T0103~T0135 T0040~T0172 T0040~T0162 T0177~T0272 T0121~T0135 T0104~T0234 T0104~T0162 T0211~T0234 T0040~T0229",
    "INSUFFICIENT_UNTIL_P1_CLEANUP": "T0012~T0018 T0018~T0057 T0012~T0057 T0012~T0171 T0125~T0171 T0123~T0171 T0259~T0306",
}

P1_ACTION = {"T0104": "INVESTIGATE_CLUSTER (USER-APPROVED in conversation 2026-11-04; not yet in workbook)",
             **{t: "INVESTIGATE_CLUSTER" for t in "T0211 T0103 T0121 T0135 T0234 T0040 T0162 T0229 T0177 T0018 T0057 T0190 T0193 T0293".split()},
             **{t: "POTENTIAL_SPLIT" for t in "T0172 T0140 T0171 T0192 T0239".split()}}

# Phase 2 P1 membership classification: per-topic default + exceptions (LIKELY = LIKELY_MISASSIGNED)
P1_CLASS = {
    "T0018": ("COHERENT", "argus|bluebeam|bluebeam pdf|bluesky|discord|reddit|meta|hrally portal|blue yonder|electron beam|niosh|radiant|synbio|synchro|composition|opera|pathmatics|unifier|litmus|axure|syncade|identity|io link|token ring|igel|meraki|pki|slack|lucid", "portal|assembly|logs|google|alteryx", "mi|vertex", ""),
    "T0040": ("LIKELY", "", "packing|packing lists|packages", "all scrips|pontoon|spine|plant dynamic behavior", "flexibility|adaptability"),
    "T0057": ("COHERENT", "arc core|arc flash|arc flash analysis|arc flash mitigation|arcsde|plasma arc melt|oasis|delphi|procore|cch prosystem|sage intacct|netsuite|dlse|nist framework|openpath|opentext ecm|solarwinds implementation|netbackup|vcenter|cxone|release notes|openfoam|cpld", "core text|mainframe|open source community|open source technology|open source tools|devops tools|devsecops", "eclipse", ""),
    "T0103": ("QUESTIONABLE", "ansys|ifrs|isdas|ndas|covenants|gaas|isbe|teds|mds|ifsp|family systems|social systems|student information systems|aviation systems|hcss heavybid|ishikawa|roas|pos|pos systems|ams360|submittals", "", "aas|ams|ims|ias|ohs|toas|tars|oas|nam|poss|pds|mcs|eos|urs|wds|tas|aes|h&mbs|pkms|ib|tss/vss|mmrs|lis|asee|jadocs", ""),
    "T0104": ("LIKELY", "", "", "d3|teoa|symphonia|topaz|foundation 6", ""),
    "T0121": ("LIKELY", "", "", "dma edge|mft|waf|dvoms|pfw|tmf|icief|dmp", ""),
    "T0135": ("LIKELY", "", "", "asa|msd|fsk|fdo|afe|hysa|scd's|prisma", ""),
    "T0140": ("COHERENT", "attention to detail|body assembly|dressing changes|drill presses|extrusion press|presses|punch press|form/fit/function|fitment|lens|linen distribution|pap mask fitting|punch down|punch list|san fabric|sheets|steam fitting|textiles|head to toe merchandising", "club fitting|safelite way of fitting", "", ""),
    "T0162": ("LIKELY", "", "", "cap|neuro|r&r|hld", "r|r administration|r shiny"),
    "T0171": ("COHERENT", "arm templates|site experience|site handler|site planning|site start up|site evaluations|route navigation apps|place and route|dynamics 365|multi site management|templates|template development|annotations|go live|page builder|experience cloud", "template building|computer experience|design experience|virtual worlds|tridion sites", "site development|virtual experience|mr experience", ""),
    "T0172": ("LIKELY", "", "consolidations|consolidating adjustments|consolidated eliminations", "ignition|flighting", "quantity take offs|take offs|electronic take offs|door take offs|restructuring"),
    "T0177": ("LIKELY", "", "m2m|ecm", "powm|s.g.m|sqcdm|rprm|srm|gpm|e1 ifm", "bom|bom analysis|bom creation|mbom|plm|plm tools"),
    "T0190": ("COHERENT", "1099 preparation|board materials preparation|build to suit|contrast materials|contrast preparation|drug preparation|explant preparation|soybean transformation|material design guidelines|make ready process|make ready program|time and material|reagent preparation", "formulation|polymerization|packaging methods|material submissions", "", ""),
    "T0192": ("COHERENT", "aliquotting|centrifuging|decapping|suturing|suture cutting|suture removal|splinting|sheath removal|tunneling|cavitation|garnishing|ground support equipment|ground up construction|ground tackle|grounding|excavation|asphalt paving|planting|pruning techniques|roofing|patching|microsegmentation|heat sinking|patience|working under pressure|working at height|effective tonnage|drill out applications|crimping", "shimming|fixturing|lubrication", "", ""),
    "T0193": ("COHERENT", "butterfly method|custom impression trays|digital impressions|impression casts|impression materials|impression pouring|itero digital impressions|makeup application|mock ups|mockups", "artworking|painting|paint application|paint retouching|post paint finishing|color matching|artistic ability", "", ""),
    "T0211": ("LIKELY", "", "", "bo|bob|chap|cola|herness|ideal|par|post mi|psi|tee|diee|enil|tara", ""),
    "T0229": ("LIKELY", "", "", "ramp|tuning", "scaling|scale up"),
    "T0234": ("QUESTIONABLE", "rivnuts|eigrp|ehs|irla|kanban|assa abloy|av systems|akka|eks|avs|vi|gosu|hanwha|avigilon|avaya|avya", "", "", ""),
    "T0239": ("COHERENT", "acetylene|ap style|booth design|crafts|diverse music styles|spray booth|stencil design|style frames|style guides|stylesheets|upholstery", "", "", ""),
    "T0293": ("COHERENT", "braze|brazing|brazing alloy|hand brazing|induction brazing|classical hand analysis|hand to surface method|mouse husbandry|splint fabrication", "", "hand scratches", ""),
}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p, **kw):
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw)


def main():
    if OUT.exists() and any(OUT.iterdir()):
        sys.exit(f"refusing to overwrite {OUT}")
    inputs = {"skills": INP / "skills.csv", "vectors": INP / "vectors.npy", "memberships": INP / "memberships.csv",
              "topics": INP / "topics.csv", "reference_links": INP / "reference_links.csv", "aliases": INP / "aliases.csv",
              "snapshot_manifest": INP / "manifest.json", "similar_topic_pairs": FEAT / "similar_topic_pairs.csv",
              "reference_summary": FEAT / "reference_summary.csv", "names": NAMES, "mentions": MENTIONS,
              "p1_skill_summary_v2": P1V2 / "p1_skill_evidence_summary_v2.csv",
              "p1_extraction_evidence_v2": P1V2 / "p1_extraction_evidence_v2.csv",
              "esco_skills": REF / "esco_v1.2.1/skills_en.csv",
              "esco_broader": REF / "esco_v1.2.1/broaderRelationsSkillPillar_en.csv",
              "esco_skill_groups": REF / "esco_v1.2.1/skillGroups_en.csv",
              "onet_software": REF / "onet_31.0/extracted/db_31_0_text/Software Skills.txt"}
    before = {k: sha256(p) for k, p in inputs.items()}
    snap = json.loads(inputs["snapshot_manifest"].read_text())["files_sha256"]
    for f in ("skills.csv", "vectors.npy", "memberships.csv", "topics.csv", "reference_links.csv", "aliases.csv"):
        assert sha256(INP / f) == snap[f], f"frozen snapshot {f} changed"

    sk = read(inputs["skills"]); V = np.load(inputs["vectors"]).astype(np.float32)
    mem = read(inputs["memberships"]).set_index("skill_key").loc[sk.skill_key].reset_index()
    tp = read(inputs["topics"]); names = read(inputs["names"]).set_index("topic_id")
    RL = read(inputs["reference_links"]); E = read(inputs["esco_skills"]).set_index("conceptUri")
    top = np.array(mem.topic_id.tolist()); state = np.array(mem.state.tolist()); asg = state == "assigned"
    T = sorted(tp.topic_id); ti = {t: i for i, t in enumerate(T)}; lab = np.array([ti[t] for t in top])
    assert len(mem) == 11093 and len(T) == 374 and asg.sum() == 8646

    # ---- topic metrics (computed) -------------------------------------------------------------------------
    C = np.stack([V[(lab == j) & asg].mean(0) for j in range(len(T))]); C /= np.linalg.norm(C, axis=1, keepdims=True)
    CC = C @ C.T; np.fill_diagonal(CC, -1)
    X = V[asg]; la = lab[asg]; D = 1 - X @ X.T
    M = np.stack([D[:, la == j].sum(1) for j in range(len(T))], 1); cnt = np.bincount(la, minlength=len(T)).astype(float)
    a = M[np.arange(len(X)), la] / (cnt[la] - 1); M2 = M / cnt; M2[np.arange(len(X)), la] = np.inf; b = M2.min(1)
    sil = (b - a) / np.maximum(a, b)
    S = V @ V.T; np.fill_diagonal(S, -2); nn = np.argpartition(-S, 10, axis=1)[:, :10]; knn = (top[nn] == top[:, None]).mean(1)
    within = [(lambda Y: ((Y @ Y.T).sum() - len(Y)) / (len(Y) * (len(Y) - 1)))(V[(lab == j) & asg]) for j in range(len(T))]
    br = read(inputs["esco_broader"]); par = br.groupby("conceptUri").broaderUri.first().to_dict()
    grp = read(inputs["esco_skill_groups"]).set_index("conceptUri").preferredLabel

    def level2(u):
        path, seen = [], set()
        while u in par and u not in seen:
            seen.add(u); u = par[u]; path.append(u)
        return (path[-2] if len(path) >= 2 else path[-1]) if path else None
    links = mem[asg].merge(RL, on="skill_key")
    links = links[(links.verdict == "known_skill") & links.source.str.startswith("ESCO")].copy()
    links["g2"] = links.ref_id.map(level2)
    links = links[links.g2.notna()]
    cov = read(inputs["reference_summary"]).set_index("topic_id")
    rep_support = {}
    stem = lambda s: {w[:5] for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3 and w not in {"and", "management", "systems", "skills", "knowledge", "development", "operations"}}
    rows = []
    for j, t in enumerate(T):
        m_a = (lab == j) & asg; m_w = (lab == j) & ~asg
        g = links[links.topic_id == t]
        pur = g.g2.value_counts(normalize=True) if len(g) >= 3 else None
        ns = stem(names.at[t, "provisional_name"])
        keys = mem.skill_key[m_a]
        rows.append({
            "topic_id": t, "provisional_name": names.at[t, "provisional_name"], "is_p1": t in P1,
            "n_assigned": int(m_a.sum()), "n_weak": int(m_w.sum()), "weak_share": round(m_w.sum() / (m_a.sum() + m_w.sum()), 4),
            "within_mean_pairwise_cos": round(float(within[j]), 4),
            "nearest_topic": T[int(CC[j].argmax())], "nearest_centroid_cos": round(float(CC[j].max()), 4),
            "mean_silhouette_cosine_384d": round(float(sil[la == j].mean()), 4),
            "knn10_same_topic_assigned": round(float(knn[m_a].mean()), 4),
            "assigned_nearer_other_centroid": int(((X @ C.T).argmax(1)[la == j] != j).sum()),
            "esco_linked_assigned": int(len(g)),
            "esco_purity_level2": round(float(pur.iloc[0]), 4) if pur is not None else "",
            "esco_top_group_level2": grp.get(pur.index[0], pur.index[0]) if pur is not None else "",
            "coverage_any_existing": cov.at[t, "coverage_any"],
            "name_word_support": round(float(np.mean([bool(stem(k) & ns) for k in keys])), 4) if ns else "",
            "name_surface_form": bool(re.search(r"\b(acronym|acronyms|mixed|miscellaneous|prefixed|terms|codes|abbreviations|branded)\b", names.at[t, "provisional_name"].lower())),
            "duplicate_name": names.provisional_name.str.lower().tolist().count(names.at[t, "provisional_name"].lower()) > 1,
            "llm_confidence": names.at[t, "llm_confidence"],
            "ai_review_action": (P1_ACTION.get(t) or (TOPICS54[t][3] if t in TOPICS54 else "")),
            "ai_review_scope": "P1 member-level (Phase 2)" if t in P1 else ("non-P1 member-level (Phase 3)" if t in TOPICS54 else "metrics only"),
        })
    tm = pd.DataFrame(rows)

    # ---- AI review tables ---------------------------------------------------------------------------------
    p1s = read(inputs["p1_skill_summary_v2"]); ev = read(inputs["p1_extraction_evidence_v2"])
    ref_i = RL.set_index("skill_key")
    lk = []
    for k, (v, meaning, valid) in LINKS.items():
        x = p1s[p1s.canonical_skill_key == k].iloc[0]; e = ev[ev.canonical_skill_key == k]
        r = ref_i.loc[k]
        lib = E.loc[r.ref_id] if r.ref_id in E.index else None
        lk.append({"topic_id": x.topic_id, "canonical_skill_key": k, "original_forms": x.original_skill_forms,
                   "posting_ids": "; ".join(e.posting_id), "evidence": " || ".join(e.evidence)[:500],
                   "ref_source": r.source, "ref_label": r.ref_label, "ref_id": r.ref_id, "ref_score": r.score, "match": r.match,
                   "library_definition": (lib.description[:300] if lib is not None else "O*NET software example (no definition field)"),
                   "exact_flag_unexplained_by_v1.2.1_labels": k in UNEXPLAINED_EXACT,
                   "evidence_meaning": meaning, "ai_verdict": v, "skill_valid": valid, "ai_label": LABEL})
    links_df = pd.DataFrame(lk)
    pm = read(inputs["mentions"]); al = read(inputs["aliases"]); pm["canon"] = pm.skill_key.map(dict(zip(al.alias_key, al.skill_key)))
    mi = mem.set_index("skill_key")
    keys_df = pd.DataFrame([{"skill_key": k, "postings": pm[pm.canon == k].posting_id.nunique(), "records": int((pm.canon == k).sum()),
                             "topic_id": mi.at[k, "topic_id"], "membership_state": mi.at[k, "state"],
                             "evidence": " || ".join(f"{p}: {e}" for p, e in zip(pm[pm.canon == k].posting_id, pm[pm.canon == k].evidence))[:900],
                             "supported_senses": s, "problem": pr, "proposed_treatment": tr, "confidence": c, "ai_label": LABEL}
                            for k, (s, pr, tr, c) in KEYS.items()])
    ac = []
    for status, items in ACRO.items():
        for it in items.split("|"):
            k, meaning = it.split(":", 1)
            e = ev[ev.canonical_skill_key == k]
            ac.append({"topic_id": p1s[p1s.canonical_skill_key == k].topic_id.iat[0], "acronym": k, "status": status,
                       "posting_ids": "; ".join(e.posting_id), "evidence": " || ".join(e.evidence)[:400],
                       "supported_meaning_or_domain": meaning, "expansion_invented": False,
                       "next_action": "fetch full posting text (Supabase/raw Kaggle)" if status in ("STILL_AMBIGUOUS", "INSUFFICIENT_SOURCE_CONTEXT") else
                                      "human ruling on skill vs non-skill" if status == "POSSIBLE_NON_SKILL" else "human confirmation",
                       "ai_label": LABEL})
    acro_df = pd.DataFrame(ac)
    t54 = pd.DataFrame([{"topic_id": t, "group": g, "provisional_name": names.at[t, "provisional_name"],
                         "n_assigned": int(((top == t) & asg).sum()), "n_weak": int(((top == t) & ~asg).sum()),
                         "members_inspected": int((top == t).sum()), "evidence_coverage": "all member names; quotes for short codes only",
                         "coherent_core": core, "main_issue": issue, "ai_proposed_action": act, "confidence": c, "ai_label": LABEL}
                        for t, (g, core, issue, act, c) in TOPICS54.items()])
    simp = read(inputs["similar_topic_pairs"]).set_index(["topic_a", "topic_b"]).cosine.to_dict()
    pr_rows = []
    for verdict, items in PAIRS.items():
        for pairs in items.split():
            x, y = pairs.split("~")
            pr_rows.append({"topic_a": x, "topic_b": y, "centroid_cosine": simp.get((x, y), simp.get((y, x), "")),
                            "name_a": names.at[x, "provisional_name"], "name_b": names.at[y, "provisional_name"],
                            "ai_verdict": verdict, "ai_label": LABEL})
    pairs_df = pd.DataFrame(pr_rows)
    p1rows = []
    for _, x in p1s.iterrows():
        dflt, lik, qu, ins, coh = P1_CLASS[x.topic_id]
        k = x.canonical_skill_key
        c = {"LIKELY": "LIKELY_MISASSIGNED"}.get(dflt, dflt)
        c = "COHERENT" if k in L(coh) else "QUESTIONABLE" if k in L(qu) else "INSUFFICIENT_CONTEXT" if k in L(ins) else "LIKELY_MISASSIGNED" if k in L(lik) else c
        p1rows.append({"topic_id": x.topic_id, "canonical_skill_key": k, "membership_state": x.membership_state,
                       "n_postings": x.n_postings, "ai_membership_class": c,
                       "wrong_reference_link_ai": LINKS.get(k, ("",))[0], "conflicting_meaning_key": k in KEYS,
                       "acronym_status": next((s for s, items in ACRO.items() if any(i.split(":")[0] == k for i in items.split("|"))), ""),
                       "rule_candidate_flags_v2": x.candidate_reasons, "human_review_decision_sprint3": x.human_review_decision,
                       "ai_label": LABEL})
    p1_df = pd.DataFrame(p1rows)
    assert len(links_df) == 38 and len(keys_df) == 9 and len(acro_df) == 61 and len(t54) == 54 and len(pairs_df) == 75 and len(p1_df) == 976
    assert set(pairs_df.topic_a + "~" + pairs_df.topic_b) | set(pairs_df.topic_b + "~" + pairs_df.topic_a) >= {f"{a}~{b}" for a, b in simp}

    # ---- global numbers -------------------------------------------------------------------------------------
    same = tot = 0
    tk = dict(zip(mem.skill_key, top))
    for _, ks in RL[RL.verdict == "known_skill"].groupby("ref_id").skill_key:
        for p, q in itertools.combinations(list(ks), 2):
            tot += 1; same += tk[p] == tk[q]
    esco = RL[RL.source.str.startswith("ESCO")]
    g = {
        "silhouette_cosine_384d_assigned": round(float(sil.mean()), 4), "silhouette_run_json": 0.0929,
        "topics_negative_silhouette": int((tm.mean_silhouette_cosine_384d < 0).sum()),
        "knn10_same_topic_assigned": round(float(knn[asg].mean()), 4), "knn10_same_topic_weak": round(float(knn[~asg].mean()), 4),
        "knn10_random_baseline": round(float((pd.Series(top).value_counts(normalize=True) ** 2).sum()), 4),
        "same_reference_concept_pairs": tot, "same_concept_pairs_same_topic_share": round(same / tot, 4),
        "esco_purity_level2_median": round(float(pd.to_numeric(tm.esco_purity_level2, errors="coerce").median()), 4),
        "topics_with_purity": int(pd.to_numeric(tm.esco_purity_level2, errors="coerce").notna().sum()),
        "pairs_cosine_ge_0.90": len(simp), "esco_link_uris_missing_from_v1.2.1": int((~esco.ref_id.isin(E.index)).sum()),
        "hierarchy_parent_links": int((tp.parent_topic_id != "").sum()), "topic_levels": tp.level.value_counts().to_dict(),
        "membership_class_counts_p1": p1_df.ai_membership_class.value_counts().to_dict(),
        "link_verdicts": links_df.ai_verdict.value_counts().to_dict(), "acronym_statuses": acro_df.status.value_counts().to_dict(),
        "topic54_actions": t54.ai_proposed_action.value_counts().to_dict(), "pair_verdicts": pairs_df.ai_verdict.value_counts().to_dict(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"topic_metrics_374.csv": tm, "reference_link_verification_38.csv": links_df, "conflicting_meaning_keys_9.csv": keys_df,
             "acronym_resolution_61.csv": acro_df, "non_p1_topic_review_54.csv": t54, "topic_pair_review_75.csv": pairs_df,
             "p1_skill_audit_976.csv": p1_df}
    for f, d in files.items():
        d.to_csv(OUT / f, index=False)
    assert before == {k: sha256(p) for k, p in inputs.items()}, "an input changed"
    man = {"schema": "phase2_phase3_audit/1", "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "script": "src/build_phase3_audit_outputs.py", "script_sha256": sha256(__file__), "ai_label": LABEL,
           "inputs": {k: {"path": str(p).replace(str(Path.home()), "~"), "sha256": before[k]} for k, p in inputs.items()},
           "outputs": {f: {"rows": len(d), "sha256": sha256(OUT / f)} for f, d in files.items()}, "global_metrics": g,
           "definitions": {
               "knn10_same_topic": "share of a skill's 10 nearest neighbours (cosine, frozen 384-d vectors, all 11,093 skills) in the same topic",
               "same_concept_pairs_same_topic_share": "pairs of skills whose known_skill link has the same ref_id, share placed in the same topic",
               "esco_purity_level2": "share of a topic's assigned members with a known_skill ESCO link whose second-level ESCO v1.2.1 group (first broader parent path) is the topic's most common one; topics with >=3 links",
               "silhouette": "cosine, 384-d, assigned members only, topic labels; recomputed here (run.json method not stated)"},
           "limitations": ["AI review tables are not human-validated; every proposed action is pending approval",
                           "54-topic review read all member names but evidence quotes only for short codes",
                           "no hierarchy exists (all topics level=topic, no parents); not built in this task",
                           "reference links are automatic; ESCO library copy is ~/Desktop/testing/references (project data/reference/ absent)",
                           "Supabase and raw Kaggle postings not accessed; nearest-neighbour agreement definition is ours (not defined in the project)"]}
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(json.dumps(g, indent=1))


if __name__ == "__main__":
    main()
