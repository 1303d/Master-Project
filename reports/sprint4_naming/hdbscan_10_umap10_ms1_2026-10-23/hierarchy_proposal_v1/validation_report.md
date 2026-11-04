# Proposed topic hierarchy — hierarchy_proposal_v1

> **AI-GENERATED, UNREVIEWED (pending human approval).** A proposed first parent level above the 374 frozen leaf topics. No topic, name, membership, alias, embedding or clustering output was changed. Every parent, label and placement needs human review.

## Method

1. **Eligibility.** Topics the validity screen marks `exclude_until_reclustered` or the Phase 2/3 audit marks `INVESTIGATE_CLUSTER` (incl. T0104, user-approved) are not placed (`UNRESOLVED_EXCLUDED`). Split candidates (`hold_split_candidate` / `POTENTIAL_SPLIT`) are placed but flagged low confidence.
2. **Distance** = 0.7·(1 − centroid cosine) + 0.15·(1 − member affinity) + 0.15·(1 − ESCO profile cosine). Member affinity = share of a topic's assigned members whose nearest other centroid is the other topic (scaled by 0.2). ESCO profile = histogram of ESCO v1.2.1 level-2 groups of confidently linked members (needs ≥ 3; else the term is dropped).
3. **Average-linkage** agglomerative clustering of eligible topics; cut = smallest grid threshold with singleton share ≤ 0.1 and parent size ≤ 30 (sweep in `cut_threshold_sweep.csv`). Chosen: **0.335**.
4. **Labels** come only from children: ESCO level-2 group if ≥ 50% of ≥ 8 linked members share it, else the medoid child's provisional name + "(and related topics)".

**Trade-offs.** Centroid similarity dominates (embedding geometry); member affinity and ESCO profiles damp word-form look-alikes but cannot remove them. ESCO links are automatic and partly wrong (see the Phase 2/3 audit), so ESCO-based labels are broad. Average linkage can chain; parent coherence and suspicious groups are reported below.

## Results

| Measure | Value |
|---|---|
| topics | 374 |
| eligible_topics | 335 |
| parents | 90 |
| placed | 303 |
| placed_high | 251 |
| placed_low_confidence | 52 |
| unresolved | 71 |
| unresolved_excluded | 39 |
| unresolved_singleton | 32 |
| parent_size_min_med_max | [2, 3.0, 14] |
| parent_coherence_median | 0.8569 |
| inter_parent_nearest_cos_median | 0.9002 |
| inter_parent_pairs_ge_0.95 | 2 |
| children_closer_to_other_parent | 6 |
| labels_esco | 18 |
| labels_medoid | 72 |
| esco_used | True |

## Structural validation

Checks: topic coverage (374, no duplicates), every placed child has an existing parent, no single-child parents, disjoint parent/topic ID namespaces (no cycles; depth 2), parent-child lists consistent, unresolved topics have no parent.

**Problems: none**

## Suspicious parent groups

Flagged when child-centroid coherence is in the lowest 10%, the ESCO top-group share is < 0.30 (with ≥ 8 links), ≥ 2 children are split candidates, or the nearest other parent has cosine ≥ 0.95.

| Parent | Label (AI) | Children | Coherence | ESCO top share | Split-pending children | Child names |
|---|---|---:|---:|---:|---:|---|
| P002 | Team Leadership (and related topics) | 2 | 0.8775 | 0.2857 | 0 | Team Leadership | Cross-Functional Collaboration |
| P003 | Creative and Strategic Thinking (and related topics) | 2 | 0.8081 | 0.2069 | 1 | Creative and Strategic Thinking | Storytelling and Storyboarding |
| P004 | information and communication technologies (icts) — Software Application Usage | 14 | 0.8111 | 0.5943 | 3 | Microsoft Software Proficiency | Desktop Computer Operations | Shell Scripting | Mobile Device Technologies | Software Application Usage | Data Entry Software | |
| P005 | Speech Language Pathology (and related topics) | 3 | 0.8718 | 0.2 | 2 | Verbal Communication | Multilingual Communication | Speech Language Pathology |
| P010 | Web Front-End Development (and related topics) | 6 | 0.8678 | 0.3333 | 2 | Web Front-End Development | REST API Development | User Interface Design | Web Application Development | Site and User Journey Design | SharePoint |
| P012 | General Analytical Methods (and related topics) | 6 | 0.8588 | 0.2353 | 0 | General Analytical Methods | Financial and Sales Analysis | Computational Modeling | Statistical Analysis | Valuation and Business Modeling | Regression Modelin |
| P013 | Project Implementation Planning (and related topics) | 6 | 0.8146 | 0.4667 | 0 | Project Management Methodologies | Agile Development Methodologies | CRM and CAD Systems | Project Implementation Planning | Business Operations Management | Co |
| P014 | Software Testing (and related topics) | 4 | 0.8824 | 0.2344 | 0 | Software Testing | Quality Inspection | Diagnostic Testing Equipment Operation | Diagnostic Testing |
| P017 | Information Security Management (and related topics) | 3 | 0.8591 | 0.2182 | 1 | Information Security Management | Fire Protection Systems | Cyber Threat Analysis |
| P021 | Technical Documentation (and related topics) | 5 | 0.8446 | 0.1692 | 1 | Technical Documentation | Medical Record Documentation | Master Data Management | Document Management Systems | Product Labeling Compliance |
| P022 | Operational Planning (and related topics) | 5 | 0.8588 | 0.2586 | 1 | Operational Planning | Strategic Planning | Case Management | Corrective Action Planning | Project Scoping |
| P023 | Performance Analysis and Monitoring (and related topics) | 2 | 0.8592 | 0.1471 | 0 | Performance Analysis and Monitoring | Business Metrics Analysis |
| P024 | Training Program Development (and related topics) | 3 | 0.8757 | 0.2558 | 0 | Training Program Development | Instructional Design and Pedagogy | Rapid Learning Ability |
| P025 | Data Validation and Verification (and related topics) | 2 | 0.7685 | 0.4074 | 0 | Risk Management | Data Validation and Verification |
| P027 | Cardiac Monitoring (and related topics) | 7 | 0.8454 | 0.4655 | 4 | Cardiac Monitoring | Medical and Surgical Procedures | Diagnostic Radiography | Renal and Medical Specialty Knowledge | Airway and Ventilation Management | IV a |
| P028 | Clinical and Educational Assessment (and related topics) | 4 | 0.8345 | 0.2041 | 0 | Clinical and Educational Assessment | Feedback and Needs Analysis | Screening Procedures | Survey Design and Site Surveying |
| P031 | Equipment Repair (and related topics) | 2 | 0.8784 | 0.2353 | 0 | Preventive Maintenance Planning | Equipment Repair |
| P032 | Order Processing (and related topics) | 4 | 0.8355 | 0.2222 | 0 | Inventory Management | Order Processing | Ticketing Systems | Retail Operations Management |
| P033 | Digital Advertising Platforms (and related topics) | 2 | 0.8268 | 0.2857 | 0 | Social Media Management | Digital Advertising Platforms |
| P034 | Instrument Calibration and Measurement (and related topics) | 2 | 0.905 | 0.1481 | 0 | Instrument Calibration and Measurement | Mechanical and Thermal Testing |
| P035 | Hand and Power Tool Operation (and related topics) | 5 | 0.8588 | 0.197 | 4 | Hand and Power Tool Operation | Garment and Lens Fitting | Quantity Take-Offs and Restructuring | Rigging and Surface Finishing | Pallet Jack Operation |
| P039 | System Integration Architecture (and related topics) | 8 | 0.8307 | 0.3099 | 0 | Product Lifecycle Management | System Integration Architecture | ERP System Administration | System Architecture Design | Architectural Design Patterns | Epicor |
| P040 | Material Handling Equipment Operation (and related topics) | 2 | 0.8641 | 0.2857 | 1 | Material Handling Equipment Operation | Fleet and Transportation Management Systems |
| P041 | Therapeutic Treatment Planning (and related topics) | 3 | 0.8519 | 0.2656 | 0 | Therapeutic Treatment Planning | Medication Management | Clinical Nutrition Therapy |
| P042 | Industry Standards Compliance (and related topics) | 5 | 0.8571 | 0.1786 | 0 | Technical Specifications Development | Industry Standards Compliance | ISO Standards Compliance | Qualification and Eligibility Determination | Regulatory and C |
| P043 | Cleaning and Sanitization (and related topics) | 4 | 0.8383 | 0.3559 | 2 | Cleaning and Sanitization | Dental Hygiene and Restorative Care | Sanitation Standards Compliance | Infection and Disease Prevention |
| P046 | SAP ERP Modules (and related topics) | 2 | 0.7947 | 1.0 | 0 | SAP ERP Modules | SD-Prefixed Acronyms |
| P051 | Structural Engineering Design (and related topics) | 3 | 0.8117 | 0.275 | 1 | Structural Engineering Design | IT Infrastructure Architecture | Welding Processes and Equipment |
| P052 | IT Service Desk Support (and related topics) | 2 | 0.8661 | 0.1875 | 0 | IT Service Desk Support | Food and Beverage Service |
| P053 | Technical Drawing Interpretation (and related topics) | 2 | 0.8275 | 0.2903 | 0 | Reading Comprehension | Technical Drawing Interpretation |
| P057 | Layout and Spatial Design (and related topics) | 4 | 0.8642 | 0.2667 | 1 | Digital Visual Design | Layout and Spatial Design | Decorative Styling and Decorating | Software Customization |
| P058 | performing administrative activities | 5 | 0.8105 | 0.5909 | 0 | Cash Handling Operations | Billing Processes | Payment Processing | Invoice Processing | Transaction Processing |
| P059 | Crisis and Emergency Response (and related topics) | 2 | 0.8743 | 0.1905 | 0 | Crisis and Emergency Response | Incident Investigation and Reporting |
| P061 | Laboratory Testing Operations (and related topics) | 3 | 0.8712 | 0.2059 | 0 | Laboratory Testing Operations | Biological Assay Development | Cell Culture Techniques |
| P062 | engineering and engineering trades — Hydraulic and Brake Systems | 6 | 0.8059 | 0.5625 | 0 | Mechanical Engineering Knowledge | HVAC and Refrigeration Systems | Engineering Practices and Reliability | Parts Catalog Management | Hydraulic and Brake Syste |
| P063 | Issue and Project Tracking (and related topics) | 3 | 0.8317 | 0.2727 | 0 | KPI Dashboarding | Issue and Project Tracking | Clinical Charting |
| P064 | Media Strategy and Planning (and related topics) | 3 | 0.8774 | 0.2 | 0 | Media Strategy and Planning | Content Strategy and Distribution | News Writing and Monitoring |
| P069 | Freight Forwarding Operations (and related topics) | 2 | 0.8401 | 0.2581 | 0 | Freight Forwarding Operations | Warehouse Operations Management |
| P070 | Recruitment and Hiring (and related topics) | 2 | 0.7995 | 0.5714 | 0 | Recruitment and Hiring | Onboarding Processes |
| P072 | Strategic Supplier Sourcing (and related topics) | 3 | 0.8601 | 0.2917 | 0 | Vendor Relationship Management | Strategic Supplier Sourcing | Procurement Management |
| P078 | Asset Management Systems (and related topics) | 2 | 0.8997 | 0.2727 | 0 | Asset Management Systems | Investment Portfolio Management |
| P081 | Equipment Setup and Handling (and related topics) | 4 | 0.8818 | 0.1667 | 1 | Equipment Setup and Handling | Industrial Machinery Operation | Medical Equipment and Devices | Specialized Equipment Operation |
| P082 | Pipeline Development and Management (and related topics) | 2 | 0.8626 | 0.2857 | 0 | Pipeline Development and Management | Pipe Fabrication and Fitting |
| P085 | HMI and EDI Systems (and related topics) | 2 | 0.7837 | 1.0 | 0 | HMI and EDI Systems | RFP Response Preparation |
| P089 | Landscaping Products and Installation (and related topics) | 2 | 0.8597 | 0.1579 | 1 | Landscaping Products and Installation | Coating and Insulation Materials |

## Remaining work (not done here)

- Human review of every parent, label and placement; record over- and under-merging (brief, Sprint 4).
- Re-cluster or reassign the excluded topics, then place them.
- Decide split candidates before fixing their parents.
- Upper levels (grandparents) are not proposed in v1.
- Correction: the Phase 2/3 audit column `esco_purity_level2` used the first group under the ESCO pillar, which is ESCO skills-hierarchy **Level 1**; this proposal uses true **Level 2** (from `skillsHierarchy_en.csv`). The audit files were not changed.
- Nearest-neighbour agreement / purity are audit metrics only; not yet part of a hierarchy evaluation pipeline.