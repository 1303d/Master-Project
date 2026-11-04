# Sprint 4 — P1 topic quality review (20 topics)

> **AI-GENERATED, NOT HUMAN-VALIDATED.** Every recommendation below was written by Claude Code from the frozen evidence. None is a reviewer decision. The workbook's reviewer fields were not touched; names, memberships and validity classes were not changed.

Generated 2026-11-04T17:13:49+00:00 by `src/build_p1_review.py`. Sources (sha256): `reports/sprint4_naming/hdbscan_10_umap10_ms1_2026-10-23/topic_quality_review_v1/sprint4_topic_quality_review.xlsx` 4aa2aba9ee3b…; `data/processed/sprint4_input_hdbscan_10_umap10_ms1_2026-10-23/memberships.csv` 0d6854f6a4e7…; `data/processed/sprint4_input_hdbscan_10_umap10_ms1_2026-10-23/reference_links.csv` 1543cb2ce7ee…; `reports/sprint4_naming/hdbscan_10_umap10_ms1_2026-10-23/topic_quality_review_v1/p1_review/p1_ai_recommendations_v1.json` b3db528320ee…

P1 rule: review flags include `low_cohesion` and `near_duplicate_topic`, and model confidence is `low`.

## Summary

AI recommendation counts (ai-generated, not human-validated):

| Recommendation | Topics |
|---|---|
| KEEP | 0 |
| RENAME | 0 |
| INVESTIGATE_CLUSTER | 19 |
| POTENTIAL_MERGE | 0 |
| UNSURE | 1 |

| Evidence sufficiency | Topics |
|---|---|
| sufficient | 13 |
| partial | 6 |
| insufficient | 1 |

| Topic | Name | Validity (rules) | cos_mean | Assigned / weak | AI recommendation | AI conf. | Evidence |
|---|---|---|---|---|---|---|---|
| T0104 | Mixed Technical Codes | surface_form_cluster | 0.764 | 38 / 18 | INVESTIGATE_CLUSTER | high | sufficient |
| T0234 | Branded Software Platforms | surface_form_cluster | 0.775 | 22 / 19 | INVESTIGATE_CLUSTER | high | sufficient |
| T0211 | Miscellaneous Acronyms and Tools | mixed | 0.775 | 23 / 54 | INVESTIGATE_CLUSTER | high | sufficient |
| T0040 | Flexible Adaptability | mixed | 0.775 | 28 / 38 | INVESTIGATE_CLUSTER | high | sufficient |
| T0162 | R Programming Tools | mixed | 0.777 | 25 / 17 | INVESTIGATE_CLUSTER | high | sufficient |
| T0135 | Acronym-Based Technical Standards | surface_form_cluster | 0.785 | 34 / 24 | INVESTIGATE_CLUSTER | high | partial |
| T0172 | Quantity Take-Offs and Restructuring | mixed | 0.788 | 30 / 28 | INVESTIGATE_CLUSTER | medium | sufficient |
| T0121 | Acronym-Based Technical Standards | surface_form_cluster | 0.791 | 40 / 16 | INVESTIGATE_CLUSTER | high | partial |
| T0057 | C++ and .NET Development | mixed | 0.793 | 33 / 28 | INVESTIGATE_CLUSTER | medium | sufficient |
| T0018 | Software Development Tools | mixed | 0.797 | 30 / 39 | INVESTIGATE_CLUSTER | medium | sufficient |
| T0140 | Garment and Lens Fitting | mixed | 0.803 | 33 / 5 | INVESTIGATE_CLUSTER | medium | sufficient |
| T0103 | Enterprise System Acronyms | surface_form_cluster | 0.808 | 40 / 43 | INVESTIGATE_CLUSTER | high | partial |
| T0192 | Rigging and Surface Finishing | mixed | 0.811 | 26 / 22 | INVESTIGATE_CLUSTER | medium | sufficient |
| T0229 | Scaling and Growth Terms | mixed | 0.813 | 14 / 16 | INVESTIGATE_CLUSTER | high | sufficient |
| T0171 | Site and User Journey Design | mixed | 0.818 | 29 / 5 | UNSURE | low | insufficient |
| T0239 | Decorative Styling and Decorating | coherent | 0.827 | 22 / 0 | INVESTIGATE_CLUSTER | medium | partial |
| T0193 | Painting and Art Techniques | coherent | 0.828 | 23 / 2 | INVESTIGATE_CLUSTER | medium | sufficient |
| T0293 | Sewing and Stitching | coherent | 0.829 | 19 / 2 | INVESTIGATE_CLUSTER | medium | sufficient |
| T0177 | Bill of Materials Management | surface_form_cluster | 0.836 | 31 / 24 | INVESTIGATE_CLUSTER | high | partial |
| T0190 | Materials Preparation and Planning | coherent | 0.840 | 27 / 9 | INVESTIGATE_CLUSTER | low | partial |

### Where the evidence is insufficient or partial

- **T0135** (partial): Same name as T0121 (duplicate_name) and centroid cosine 0.905, but both are acronym noise. Merging is not recommended; both names should change after re-clustering. Posting context would be needed to expand ambiguous acronyms (afe, fdo, hysa, mslt).
- **T0121** (partial): Same name as T0135 (duplicate_name); see T0135. Several acronyms are ambiguous without postings (dmm, dmp, dmi, maf, tars).
- **T0103** (partial): Many acronyms are ambiguous without postings (ams, ats, ias, ids, lis).
- **T0171** (insufficient): Near-duplicates T0012 Web Front-End (0.913), T0125 Web Application Development (0.910), T0123 User Interface Design (0.905). If the site members turn out to be web, POTENTIAL_MERGE with T0123 is worth checking; if construction, INVESTIGATE_CLUSTER. Needs supporting postings.
- **T0239** (partial): Near-duplicates T0181 Layout and Spatial Design (0.914) and T0193 Painting and Art (0.907). The rule-based 'coherent' result and this recommendation disagree; a human should decide.
- **T0177** (partial): Near-duplicate T0272 Management System Acronyms (0.912), also a surface-form cluster. Ambiguous acronyms need posting context.
- **T0190** (partial): Borderline: a human could reasonably KEEP it as a broad materials topic. Near-duplicate T0084 Structural Engineering Design (0.900) only for the construction part.

### Evidence gaps that apply to all P1 topics

- No posting counts or supporting posting snippets per member are in the Sprint 4 snapshot, so ambiguous strings (acronyms, 'site', 'scales') cannot be checked against their posting context here.
- `known_skill` reference links are automatic (`review_status = auto`) and some are wrong (e.g. food styling -> hairdressing, classical hand analysis -> read palms, dock carts -> moor vessels). Reference coverage therefore overstates how well some topics are grounded.
- ESCO / O*NET broader-group purity is unavailable in the snapshot.

## Topics

### T0104 — Mixed Technical Codes

*A heterogeneous collection of alphanumeric identifiers including CAD software, project management tools, and quality standards.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic mixes distinct domains such as CAD (Catia), networking (Cat5), project management (Primavera), and quality methodologies (5S, 5 Why).
- **Members:** 38 assigned, 18 weak · **cohesion** cos_mean 0.764 (min 0.714) · transversal false
- **Near-duplicates (centroid cosine):** T0211 (0.918); T0234 (0.905); T0162 (0.903)
- **Reference coverage:** low coverage (<30%): 2/38 assigned skills confidently linked (5%) (ESCO knowledge=1;O*NET software=1)
- **Validity screening:** surface_form_cluster — no shared word (head_word_share 0.08); acronym_share 0.53 >= 0.5; digit_share 0.66 >= 0.5 · hierarchy: exclude_until_reclustered
- **Review flags:** `low_cohesion;near_duplicate_topic;generic_name;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.764 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0211 (0.918); T0234 (0.905); T0162 (0.903))
- generic_name: the name contains a generic word from the naming stage's list
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** cat5 (0.821); cat6 (0.821); catia v5 (0.812); cat5e (0.810); 5s (0.802); ho5 (0.797); catia v6 (0.794); a3 (0.792); ho6 (0.786); p6 (0.783)

**Assigned members (38):** cat5; cat6; catia v5; cat5e; 5s; ho5; catia v6; a3; ho6; p6; p 3; d3; oracle p6; ho3; 3pl; es6; go95; s3; map d; primavera 6; 5 why; primavera p6; ho4; rt; 3wla; enovia; innovus; modus; clia; zia; catia; ispe gamp5; tempus; teoa; foundation 6; symphonia; tekton; primavera

**Weak members (18):** ab initio; opal rt; armis; three lines; pivo; challenger; blackline; fiori elements; empower fr4; a1 finish; ta1; itil; tealium; itero; hyper v; essentus; topaz; advent geneva

**Confident member links:** 3pl -> 3PL Central [O*NET software]; rt -> radiotherapy [ESCO knowledge]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence sufficient
> 
> Members are grouped by characters, not meaning: cat5/cat6 (network cable), catia v5 (CAD), 5s / 5 why (lean), primavera p6 (scheduling), ho3/ho4/ho5/ho6 (unexpanded codes). Validity rules flag surface_form_cluster (digit share 0.66, acronym share 0.53); reference coverage 5%. The name 'Mixed Technical Codes' describes the noise, not a competency, so renaming would not fix it.
> 
> *Also:* Generic name. Near-duplicate partners T0211 / T0234 / T0162 are also noise clusters, so a merge would only make a bigger noise cluster.

### T0234 — Branded Software Platforms

*Recognition of assorted named commercial software products and platforms (e.g., Avaya, Canva, Okta, AVImark) that cluster together mainly by short, similar-sounding product names.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members are unrelated product names (telephony, veterinary, design, identity, tax, security, networking protocols, fasteners) grouped by lexical similarity rather than a shared competency.
- **Members:** 22 assigned, 19 weak · **cohesion** cos_mean 0.775 (min 0.714) · transversal false
- **Near-duplicates (centroid cosine):** T0104 (0.905); T0211 (0.903)
- **Reference coverage:** low coverage (<30%): 2/22 assigned skills confidently linked (9%) (O*NET software=2)
- **Validity screening:** surface_form_cluster — no shared word (head_word_share 0.05); acronym_share 0.59 >= 0.5 · hierarchy: exclude_until_reclustered
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.775 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0104 (0.905); T0211 (0.903))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** avya (0.844); avs (0.828); akka (0.824); avimark (0.805); avaya (0.798); eks (0.792); canva (0.790); asta (0.786); aktana (0.784); astea (0.782)

**Assigned members (22):** avya; avs; akka; avimark; avaya; eks; canva; asta; aktana; astea; ehs; okta; avalara; equis; aspera; magaya; avigilon; eigrp; manta; ekahau; irla; rivnuts

**Weak members (19):** av systems; alation; vi; veeva; omilia; kanban; emass; gosu; aha!; grafana; ariba; verodin; assa abloy; ellucian banner; splunk soar; hanwha; silvaco; kajabi; ecw

**Confident member links:** avimark -> McAllister Software Systems AVImark [O*NET software]; canva -> Canva [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence sufficient
> 
> Unrelated short product names grouped by sound (avaya, avimark, avalara, okta, canva, eigrp, rivnuts). Validity rules: surface_form_cluster (acronym share 0.59); reference coverage 9%. The model's own reason says the grouping is lexical.
> 
> *Also:* Near-duplicate of T0104 / T0211 (also noise); do not merge.

### T0211 — Miscellaneous Acronyms and Tools

*Short acronyms and proper-noun tool or product names (e.g. PLS CADD, Pardot, Snowflake, Tenable) grouped by surface similarity rather than a single shared competency.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members are unrelated short acronyms, software products, a language (ilocano) and equipment brands, so no coherent competency exists.
- **Members:** 23 assigned, 54 weak · **cohesion** cos_mean 0.775 (min 0.648) · transversal false
- **Near-duplicates (centroid cosine):** T0162 (0.926); T0040 (0.925); T0018 (0.925); T0104 (0.918); T0234 (0.903)
- **Reference coverage:** low coverage (<30%): 2/23 assigned skills confidently linked (9%) (ESCO skill=1;O*NET software=1)
- **Validity screening:** mixed — no shared word (head_word_share 0.09) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;weak_exceeds_assigned;near_duplicate_topic;generic_name;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.775 is at or below the 25th percentile of all 374 topics
- weak_exceeds_assigned: 54 weak members > 23 assigned members
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0162 (0.926); T0040 (0.925); T0018 (0.925); T0104 (0.918); T0234 (0.903))
- generic_name: the name contains a generic word from the naming stage's list
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** par (0.846); pls cadd (0.839); pls (0.836); dot (0.812); pic/s (0.810); du (0.807); can (0.806); ot (0.806); bob (0.795); pardot (0.795)

**Assigned members (23):** par; pls cadd; pls; dot; pic/s; du; can; ot; bob; pardot; tenable; snowflake; incopy; stucky; car/capa; accessibility; siprnet; copa; bobcat; ilocano; black duck; katapult; von duprin

**Weak members (54):** mhe; shunt; imageright; tee; i and o; cola; go; concur; im; bridge; it; 4 p's; bo; comscore; mis en place; quoting; oee; walkie; tact; pspice; wins; prime; spring; post mi; chap; fat; par lists; copado; uft; ideal; canbus; rex; psi; comsol; poly; voltus; jungle; enil; mike; sentaurus; sox; rally; ut; diee; herness; tara; clist; nyc dep; personas; judgement; victor; canton; balsamiq; kardin

**Confident member links:** snowflake -> Snowflake [O*NET software]; bobcat -> operate front loader [ESCO skill]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence sufficient
> 
> Weak members (54) are more than double the assigned ones (23). Assigned members are unrelated tokens (par, dot, can, bob, ilocano, snowflake, von duprin). Lowest cos_min among P1 (0.648); reference coverage 9%; validity = mixed. It has the most near-duplicate partners (5), which is typical of a noise sink.
> 
> *Also:* Generic name.

### T0040 — Flexible Adaptability

*The ability to demonstrate flexibility and adaptability in work processes and environments.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic mixes soft skills (flexibility, adaptability) with unrelated physical objects (chutes, doilies) and software names (Hootsuite, Windchill), indicating a low-cohesion cluster.
- **Members:** 28 assigned, 38 weak · **cohesion** cos_mean 0.775 (min 0.732) · transversal true
- **Near-duplicates (centroid cosine):** T0211 (0.925); T0172 (0.917); T0162 (0.912); T0229 (0.901)
- **Reference coverage:** linked: 9/28 assigned skills confidently linked (32%) (ESCO knowledge=4;ESCO skill=4;O*NET software=1)
- **Validity screening:** mixed — no shared word (head_word_share 0.07) and low cohesion · hierarchy: hold_split_candidate · AI-proposed (not human): mixed
- **Review flags:** `low_cohesion;weak_exceeds_assigned;near_duplicate_topic;unsupported_supporting_skills;few_supporting_skills;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.775 is at or below the 25th percentile of all 374 topics
- weak_exceeds_assigned: 38 weak members > 28 assigned members
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0211 (0.925); T0172 (0.917); T0162 (0.912); T0229 (0.901))
- unsupported_supporting_skills: the model cited supporting skills that are not in the evidence it was given
- few_supporting_skills: fewer supporting skills than the prompt asks for
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** containers (0.833); chutes (0.824); flexibility (0.812); dock carts (0.811); assortment (0.810); flexray (0.803); packages (0.801); packing (0.801); pontoon (0.795); free float (0.792)

**Assigned members (28):** containers; chutes; flexibility; dock carts; assortment; flexray; packages; packing; pontoon; free float; doilies; freewheel; box; shaft flex; umbrella; hootsuite; conformal; adaptability; all scrips; windchill; packing lists; boating; alignrt; sponges; gac flex spanset; turbocourt; sunnen rod hone; pole foreman

**Weak members (38):** one piece flow; b roll; stocking; spinning; docketing; spin; timber cruising; timber; holding fixtures; one lines; fillers; non conforming product; nominal tonnage; harness; collections; tray set up; packer; solarwinds; thermocouple; bamboo; plant dynamic behavior; nature activities; spine; recreational fishing; centrifuges; collibra; omnigraffle; genesys; ice collar; crutch walking; cleft; copperleaf; cold chain; cubs; splunk; aspen; ultipro; duck creek

**Confident member links:** containers -> types of containers [ESCO knowledge]; flexibility -> perform services in a flexible manner [ESCO skill]; dock carts -> moor vessels [ESCO skill]; packages -> design package [ESCO skill]; packing -> packaging engineering [ESCO knowledge]; box -> types of boxes [ESCO knowledge]; hootsuite -> Hootsuite [O*NET software]; packing lists -> packaging engineering [ESCO knowledge]; boating -> teach boating principles [ESCO skill]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence sufficient
> 
> Only 2 of 28 assigned members (flexibility, adaptability) match the name 'Flexible Adaptability'. The rest are objects and products (containers, chutes, doilies, sponges, umbrella, hootsuite, windchill), and there are 38 weak vs 28 assigned. The naming stage also flagged unsupported / few supporting skills. Validity = mixed; Claude's earlier validity proposal (pilot_review_v1.json, not human-confirmed) cites extraction noise.
> 
> *Also:* Name is also misleading. The topic is marked transversal, so the 2 soft-skill members may belong elsewhere. Several 'known_skill' links look wrong (dock carts -> moor vessels).

### T0162 — R Programming Tools

*Skills centred on the R language and its ecosystem (Shiny, RWE/RWD, administration), alongside loosely related named tools and platforms such as REDCap and Red Hat.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members mix R-language items with unrelated short tool or brand names (RHEL, REDCap, Crestron, Rubrik, Sabre, Archer) grouped mainly by string similarity.
- **Members:** 25 assigned, 17 weak · **cohesion** cos_mean 0.777 (min 0.714) · transversal false
- **Near-duplicates (centroid cosine):** T0211 (0.926); T0018 (0.923); T0040 (0.912); T0104 (0.903)
- **Reference coverage:** low coverage (<30%): 2/25 assigned skills confidently linked (8%) (ESCO knowledge=1;O*NET software=1)
- **Validity screening:** mixed — no shared word (head_word_share 0.04) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.777 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0211 (0.926); T0018 (0.923); T0040 (0.912); T0104 (0.903))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** r shiny (0.831); r (0.831); redcap (0.818); rhel (0.815); pls pole (0.810); r&r (0.803); redtail (0.801); arm (0.800); rwe (0.797); redhat (0.793)

**Assigned members (25):** r shiny; r; redcap; rhel; pls pole; r&r; redtail; arm; rwe; redhat; cap; rwd; ike; nadcap; rxscala; r administration; sabre; dagger; dovetail; archer; scalatra; crestron; rubrik; erwin; red rides

**Weak members (17):** redis; resonate; sentinel; sage 100; synergi; nastran; hld; svn; nielsen; rs232; patran; ellucian banner hr; neuro; zephyr; rancher; juniper mist; kapton

**Confident member links:** r shiny -> Shiny [O*NET software]; r -> R [ESCO knowledge]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence sufficient
> 
> A small R-language core (r, r shiny, r administration, rwe/rwd) is mixed with tokens that start with 'r' or contain 'red' (redcap, rhel, redhat, redtail, red rides, rubrik, crestron, sabre). Coverage 8%; validity = mixed. The name 'R Programming Tools' fits only about 5 of 25 members.
> 
> *Also:* If kept as a topic after re-clustering, the R core would need a narrower name.

### T0135 — Acronym-Based Technical Standards

*Proficiency in interpreting and applying various industry-specific acronyms, regulatory frameworks, and technical standards.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic is a low-cohesion cluster of unrelated acronyms spanning safety, software, and government regulations, lacking a single specific competency.
- **Members:** 34 assigned, 24 weak · **cohesion** cos_mean 0.785 (min 0.680) · transversal false
- **Near-duplicates (centroid cosine):** T0103 (0.916); T0121 (0.905); T0121 (name)
- **Reference coverage:** low coverage (<30%): 4/34 assigned skills confidently linked (12%) (O*NET software=4)
- **Validity screening:** surface_form_cluster — no shared word (head_word_share 0.06); acronym_share 0.79 >= 0.5 · hierarchy: exclude_until_reclustered
- **Review flags:** `low_cohesion;near_duplicate_topic;duplicate_name:T0121;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.785 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0103 (0.916); T0121 (0.905); T0121 (name))
- duplicate_name:T0121: another topic got the same provisional name (T0121)
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** msa (0.865); jpa (0.849); asa (0.831); fmea (0.829); rma (0.826); soa (0.823); msds (0.811); fmla (0.809); msha (0.809); gsa (0.804)

**Assigned members (34):** msa; jpa; asa; fmea; rma; soa; msds; fmla; msha; gsa; coda; nfpa; msd; fms; pha; afe; capa; msds sheets; flsa; neca; mslt; prisma; afatds; mssp; fme server; dcaa; deia initiatives; fdo; hysa; scd's; asana; fsk; scd boots; akamai

**Weak members (24):** osa/sf; aca; md&a; pfmea; sas; hsa; p 8a; cuda; sar; iata; feac; ueba; teradata; jde; cta links; st micro; hse; bpa; sase; feha; hcfa 1500; eu vol4 annex 11; sara; san

**Confident member links:** asa -> ANSYS ASAS [O*NET software]; fmea -> SKILL FMEA software [O*NET software]; msds sheets -> Material safety data sheet MSDS software [O*NET software]; asana -> Asana [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence partial
> 
> Unrelated three-letter acronyms from safety, HR law and software (msha, fmla, flsa, nfpa, jpa, asana, akamai). Validity rules: surface_form_cluster (acronym share 0.79); coverage 12%. Several acronyms cannot be expanded from the member strings alone.
> 
> *Also:* Same name as T0121 (duplicate_name) and centroid cosine 0.905, but both are acronym noise. Merging is not recommended; both names should change after re-clustering. Posting context would be needed to expand ambiguous acronyms (afe, fdo, hysa, mslt).

### T0172 — Quantity Take-Offs and Restructuring

*Estimating material quantities from plans through take-offs, alongside restructuring, consolidation, adjustment and disassembly or changeover activities.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members mix construction quantity take-offs, financial consolidation and restructuring, and equipment disassembly or changeover, plus loosely related generic words.
- **Members:** 30 assigned, 28 weak · **cohesion** cos_mean 0.788 (min 0.652) · transversal false
- **Near-duplicates (centroid cosine):** T0040 (0.917); T0192 (0.905)
- **Reference coverage:** low coverage (<30%): 7/30 assigned skills confidently linked (23%) (ESCO knowledge=2;ESCO skill=5)
- **Validity screening:** mixed — no shared word (head_word_share 0.13) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.788 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0040 (0.917); T0192 (0.905))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** restructuring (0.849); quantity take offs (0.848); consolidating adjustments (0.845); disassembly (0.844); take offs (0.840); changeovers (0.840); consolidated eliminations (0.822); splitting (0.822); rework (0.817); redundancy (0.817)

**Assigned members (30):** restructuring; quantity take offs; consolidating adjustments; disassembly; take offs; changeovers; consolidated eliminations; splitting; rework; redundancy; consolidations; electronic take offs; terminations; dismantling techniques; adjustment; rooming; door take offs; phasing; working backwards; circulate; obsolescence; less; flighting; unloading devices; lookback; far; technical factor adjustment; feeders; door strikes; farcaster

**Weak members (28):** retraction; product changeovers; compounding; isolved; filtering; retractor handling; expediting; encapsulating; backhauls; resume building; functional decomposition; receivers; demodulation; power phasing; excess of loss; waivers; l3 filtering; l4 filtering; intune; ir drop; skip tracing; isolation; transient suppression; leaves of absence; ambulation; shrink; after effects; ignition

**Confident member links:** consolidating adjustments -> perform adjustments as the work evolves [ESCO skill]; disassembly -> disassemble equipment [ESCO skill]; changeovers -> perform fast changeover [ESCO skill]; rework -> repair patterns [ESCO skill]; dismantling techniques -> decommissioning [ESCO knowledge]; less -> LESS [ESCO knowledge]; unloading devices -> unload equipment [ESCO skill]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence sufficient
> 
> There are at least three meanings: construction quantity take-offs (quantity take offs, electronic take offs, door take offs), financial consolidation (consolidated eliminations, consolidating adjustments), and workforce / equipment changes (restructuring, terminations, redundancy, disassembly, changeovers). Plus generic words (less, far, circulate). Cos_min 0.652; coverage 23%; validity = mixed.
> 
> *Also:* The name joins two unrelated themes with 'and'.

### T0121 — Acronym-Based Technical Standards

*Proficiency in a diverse set of industry-specific acronyms and technical standards, including data management, architecture frameworks, and software tools.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic is a low-cohesion cluster of unrelated acronyms spanning data management, architecture, security, and design tools, with no single unifying competency.
- **Members:** 40 assigned, 16 weak · **cohesion** cos_mean 0.791 (min 0.670) · transversal false
- **Near-duplicates (centroid cosine):** T0135 (0.905); T0135 (name)
- **Reference coverage:** low coverage (<30%): 4/40 assigned skills confidently linked (10%) (ESCO knowledge=2;O*NET software=2)
- **Validity screening:** surface_form_cluster — no shared word (head_word_share 0.05); acronym_share 0.85 >= 0.5 · hierarchy: exclude_until_reclustered
- **Review flags:** `low_cohesion;near_duplicate_topic;duplicate_name:T0135;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.791 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0135 (0.905); T0135 (name))
- duplicate_name:T0135: another topic got the same provisional name (T0135)
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** dfs (0.867); dxf (0.853); dmm (0.848); dfsms/vmtm (0.835); dmp (0.835); dmaic (0.830); poly dma (0.828); dmps (0.824); smf (0.815); dma edge (0.814)

**Assigned members (40):** dfs; dxf; dmm; dfsms/vmtm; dmp; dmaic; poly dma; dmps; smf; dma edge; dmi; dft; srdf; tfs; jamf; efs; dfeh; maf; dfar; pfema; dvoms; iodf; gtfs; dsm; demarc extensions; dcma; abf; sqf; hfm; dsm v; waf; dmz; racf; smp/e; mft; wcf; dodaf; figma; nuovafima; ccc1

**Weak members (16):** tmf; lldp; ecf; nist csf; icief; poly endpoints; fifo; ricefw; silicon labs efm; tsaf; ebpf; pfw; fiori; florence tmf; ngfw; wmi

**Confident member links:** dmp -> dance therapy [ESCO knowledge]; dmps -> dance therapy [ESCO knowledge]; racf -> IBM Resource Access Control Facility RACF [O*NET software]; figma -> Figma [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence partial
> 
> Acronyms that share letters d/f/m/s (dfs, dxf, dmaic, srdf, jamf, dmz, waf, dodaf, figma). Validity rules: surface_form_cluster (acronym share 0.85); coverage 10%.
> 
> *Also:* Same name as T0135 (duplicate_name); see T0135. Several acronyms are ambiguous without postings (dmm, dmp, dmi, maf, tars).

### T0057 — C++ and .NET Development

*Proficiency in C++ and .NET programming languages, including associated frameworks and open-source development tools.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic mixes C++/.NET programming with unrelated ArcGIS electrical safety tools (arc flash) and other miscellaneous terms.
- **Members:** 33 assigned, 28 weak · **cohesion** cos_mean 0.793 (min 0.686) · transversal false
- **Near-duplicates (centroid cosine):** T0018 (0.922); T0012 (0.919)
- **Reference coverage:** linked: 19/33 assigned skills confidently linked (58%) (ESCO knowledge=8;O*NET software=11)
- **Validity screening:** mixed — no shared word (head_word_share 0.18) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.793 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0018 (0.922); T0012 (0.919))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** open source tools (0.852); .net core (0.848); core java (0.833); arc core (0.832); github (0.827); c# (0.820); c++11 (0.820); c++ (0.819); gnu tools (0.817); .net (0.816)

**Assigned members (33):** open source tools; .net core; core java; arc core; github; c#; c++11; c++; gnu tools; .net; arcsde; open source community; open source technology; core text; .net development; procore; dotnet core; c++14; visualforce; vb.net; asp.net; cmake; gradle; arc flash analysis; arc flash; arc flash mitigation; delphi; github actions; perforce helix core; cxone; eclipse; plasma arc melt; oasis

**Weak members (28):** devops tools; mainframe; backend eda tools; vulkan; openfoam; opencl; java build tools; opentext ecm; compilers; terraform; uipath libraries; cch prosystem; netsuite; openpath; devsecops; uipath studio; ni programming; vcenter; netbackup; nist framework; solarwinds implementation; release notes; dlse; sage intacct; synon 2e; spring boot; uipath orchestrator; cpld

**Confident member links:** open source tools -> Software development tools [O*NET software]; github -> GitHub [O*NET software]; c# -> C# [ESCO knowledge]; c++11 -> C++ [ESCO knowledge]; c++ -> C++ [ESCO knowledge]; .net -> Visual Studio .NET [ESCO knowledge]; arcsde -> ESRI ArcSDE [O*NET software]; open source technology -> Open source model [ESCO knowledge]; .net development -> Project.net [O*NET software]; procore -> Procore software [O*NET software]; dotnet core -> Visual Studio .NET [ESCO knowledge]; c++14 -> C++ [ESCO knowledge]; visualforce -> Salesforce Visualforce [O*NET software]; vb.net -> Microsoft Visual Basic.NET [O*NET software]; asp.net -> ASP.NET [ESCO knowledge]; cmake -> CMake [O*NET software]; gradle -> Gradle [O*NET software]; delphi -> Delphi Technology [O*NET software]; perforce helix core -> Perforce Helix software [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence sufficient
> 
> There is a real core of about 15 C++/.NET/C# and build-tool members, but string-matched groups are attached: 'arc' (arc flash analysis, arc flash mitigation, plasma arc melt, arcsde), 'core' (procore, core text, perforce helix core) and 'open source' items. Coverage 58%; validity = mixed.
> 
> *Also:* The name fits the core. Splitting out the arc-flash (electrical safety) members might be enough, and the current name could then stay. Near-duplicate partners T0018 / T0012 are programming topics, so overlap is real but they are both low-cohesion too.

### T0018 — Software Development Tools

*Proficiency in a diverse range of programming languages, frameworks, and software development platforms used for building and managing applications.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic mixes core programming languages with unrelated collaboration tools (Confluence, Discord) and niche software (Bluebeam, HRally), indicating a broad and incoherent cluster of technical tools.
- **Members:** 30 assigned, 39 weak · **cohesion** cos_mean 0.797 (min 0.701) · transversal false
- **Near-duplicates (centroid cosine):** T0012 (0.945); T0211 (0.925); T0162 (0.923); T0057 (0.922)
- **Reference coverage:** linked: 12/30 assigned skills confidently linked (40%) (ESCO knowledge=5;O*NET software=7)
- **Validity screening:** mixed — no shared word (head_word_share 0.07) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;weak_exceeds_assigned;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.797 is at or below the 25th percentile of all 374 topics
- weak_exceeds_assigned: 39 weak members > 30 assigned members
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0012 (0.945); T0211 (0.925); T0162 (0.923); T0057 (0.922))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** scala (0.848); apache (0.845); portal (0.845); apache beam (0.841); confluence (0.834); lambda (0.832); ruby (0.832); python (0.828); golang (0.821); meta (0.820)

**Assigned members (30):** scala; apache; portal; apache beam; confluence; lambda; ruby; python; golang; meta; java; pub/sub; unity; gulp; discord; scalactic; maven; django; hrally portal; bluebeam; artifactory; flask; bluebeam pdf; reddit; lucid; argus; r programming; pyramid; bluesky; blue yonder

**Weak members (39):** docker; opentext; composition; pathmatics; slack; assembler; assembly; synchro; mulesoft; syncade; bpml; puppet; logstash; groovy; io link; vertex; logs; google; synbio; meraki; sonarqube; pki; pytorch; mi; niosh; alteryx; unifier; token ring; radiant; litmus; electron beam; gnu radio; axure; elk; igel; identity; genesis; composer; opera

**Confident member links:** scala -> Scala [ESCO knowledge]; apache -> Apache HTTP Server [O*NET software]; confluence -> Atlassian Confluence [O*NET software]; ruby -> Ruby [O*NET software]; python -> Python [O*NET software]; java -> Java (computer programming) [ESCO knowledge]; unity -> design principles [ESCO knowledge]; scalactic -> Scala [ESCO knowledge]; maven -> Apache Maven [ESCO knowledge]; django -> Django [O*NET software]; flask -> Flask [O*NET software]; lucid -> Lucidchart [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence sufficient
> 
> The members mix programming languages (python, java, scala, ruby, golang), frameworks (django, flask) and unrelated platforms or brands (discord, reddit, bluebeam, bluesky, blue yonder, hrally portal). 39 weak vs 30 assigned; validity = mixed. Its closest neighbour is T0012 Web Front-End Development (centroid cosine 0.945).
> 
> *Also:* Possible merge or boundary check with T0012 for the programming-language part only, after the noise is removed. The name 'Software Development Tools' is broad.

### T0140 — Garment and Lens Fitting

*Adjusting and customizing the fit of clothing, eyewear, and contact lenses for customers, including related alterations and pressing.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic mixes apparel fitting with optical lens fitting and includes unrelated industrial press and administrative punch list terms.
- **Members:** 33 assigned, 5 weak · **cohesion** cos_mean 0.803 (min 0.704) · transversal false
- **Near-duplicates (centroid cosine):** T0293 (0.908)
- **Reference coverage:** linked: 25/33 assigned skills confidently linked (76%) (ESCO knowledge=9;ESCO skill=15;O*NET software=1)
- **Validity screening:** mixed — no shared word (head_word_share 0.21) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.803 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0293 (0.908))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** garment fitting (0.892); garment pressing (0.882); eyewear fitting (0.874); fitting (0.857); tailoring (0.848); garment construction (0.845); garment care (0.834); contact lens fittings (0.832); fabrics (0.830); presses (0.829)

**Assigned members (33):** garment fitting; garment pressing; eyewear fitting; fitting; tailoring; garment construction; garment care; contact lens fittings; fabrics; presses; textiles; pressing; customer fitting; dressing changes; form/fit/function; alterations; garment marking; club fitting; fitment; extrusion press; lens fabrication; sheets; drill presses; pap mask fitting; punch press; lens design; contact lens dispensing; lens; san fabric; linen distribution; lens options; punch list; punch down

**Weak members (5):** steam fitting; body assembly; safelite way of fitting; head to toe merchandising; attention to detail

**Confident member links:** garment fitting -> alter wearing apparel [ESCO skill]; garment pressing -> press rubberized fabrics [ESCO skill]; eyewear fitting -> adjust eyeglasses to fit customers [ESCO skill]; tailoring -> dressmaking [ESCO knowledge]; garment construction -> manufacturing of wearing apparel [ESCO knowledge]; garment care -> alter wearing apparel [ESCO skill]; contact lens fittings -> contact lens fitting techniques [ESCO knowledge]; fabrics -> dye fabrics [ESCO skill]; presses -> tend press operation [ESCO skill]; textiles -> textile materials [ESCO knowledge]; pressing -> milling machines [ESCO knowledge]; dressing changes -> alter wearing apparel [ESCO skill]; form/fit/function -> align content with form [ESCO skill]; alterations -> adjust clothes [ESCO skill]; extrusion press -> blow moulding machine parts [ESCO knowledge]; lens fabrication -> optical manufacturing process [ESCO knowledge]; sheets -> measure paper sheets [ESCO skill]; drill presses -> operate drill press [ESCO skill]; punch press -> tend punch press [ESCO skill]; lens design -> optical components [ESCO knowledge]; contact lens dispensing -> dispense corrective lenses [ESCO skill]; lens -> optical components [ESCO knowledge]; linen distribution -> maintain linen operation [ESCO skill]; lens options -> select camera apertures [ESCO skill]; punch list -> Bosch Punch List [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence sufficient
> 
> There are three distinct themes joined by the word 'fit/press': garment fitting and tailoring, optical lens and contact lens fitting, and industrial presses (punch press, drill presses, extrusion press, punch list, punch down). Coverage is high (76%), but the links confirm the themes are different, e.g. punch press -> 'tend punch press', eyewear fitting -> 'adjust eyeglasses'.
> 
> *Also:* Near-duplicate T0293 Sewing and Stitching (0.908); the garment part may belong with sewing.

### T0103 — Enterprise System Acronyms

*Familiarity with various enterprise software platforms and industrial systems identified by their standard acronyms.*

- **Source / model confidence:** groq / qwen/qwen3.8-27b / low — The topic is a low-cohesion mix of unrelated software acronyms (e.g., Ansys, IBM IMS, IaaS) and industrial systems (MES, ATS) without a single unifying competency.
- **Members:** 40 assigned, 43 weak · **cohesion** cos_mean 0.808 (min 0.691) · transversal false
- **Near-duplicates (centroid cosine):** T0135 (0.916)
- **Reference coverage:** low coverage (<30%): 9/40 assigned skills confidently linked (22%) (ESCO knowledge=2;ESCO skill=1;O*NET software=6)
- **Validity screening:** surface_form_cluster — no shared word (head_word_share 0.05); acronym_share 0.85 >= 0.5 · hierarchy: exclude_until_reclustered · AI-proposed (not human): surface_form_cluster
- **Review flags:** `low_cohesion;weak_exceeds_assigned;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.808 is at or below the 25th percentile of all 374 topics
- weak_exceeds_assigned: 43 weak members > 40 assigned members
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0135 (0.916))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** ams (0.882); mes (0.879); ims (0.879); ats (0.869); ansys (0.866); iaas (0.858); ias (0.855); ids (0.852); oas (0.838); asrs (0.837)

**Assigned members (40):** ams; mes; ims; ats; ansys; iaas; ias; ids; oas; asrs; isdas; aas; lis; paas; ohs; toas; nms; iis; slas; ecosys; roas; pdas; mes/mom; ifrs; ams360; ledes ids; tars; iges; laas; teds; mmrs; mesos; luns; unisys 2200; ifsp; isbe; ispf; sla management; nam; ishikawa

**Weak members (43):** ips; urs; sns; ecs; tas; ats units; aes; pms; pos; pds; pss/e; pos systems; hris systems; mcs; mds; tss/vss; poss; eos; h&mbs; dds; family systems; rnns; aviation systems; asee; jes2; student information systems; ndas; gaas; smbios; soc; wds; submittals; social systems; pkms; cjis; jobboss; hcss heavybid; ib; accepted abbreviations; opera pms; suse; covenants; jadocs

**Confident member links:** ams -> use aeronautical mobile service communications [ESCO skill]; ims -> IBM Information Management System (IMS) [O*NET software]; ansys -> ANSYS ASAS [O*NET software]; iis -> Microsoft Internet Information Services (IIS) [O*NET software]; ifrs -> visual flight rules [ESCO knowledge]; ams360 -> AMS Services AMS 360 [O*NET software]; ifsp -> visual flight rules [ESCO knowledge]; ispf -> IBM Interactive System Productivity Facility ISPF [O*NET software]; nam -> NAMD [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence partial
> 
> Acronyms ending in 's' (ams, mes, ims, ats, iaas, paas, ifrs, slas, luns). 43 weak vs 40 assigned. Validity rules: surface_form_cluster (acronym share 0.85); Claude's earlier validity proposal agrees (not human-confirmed). Coverage 22%.
> 
> *Also:* Many acronyms are ambiguous without postings (ams, ats, ias, ids, lis).

### T0192 — Rigging and Surface Finishing

*Hands-on physical trade techniques, chiefly rigging and securing loads plus surface finishing such as sanding, polishing, caulking and blasting, with a minor cluster of clinical procedures like suturing.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members mix rigging/grounding, surface finishing, and medical or lab procedures (suturing, splinting, centrifuging, aliquotting), so no single competency covers them all.
- **Members:** 26 assigned, 22 weak · **cohesion** cos_mean 0.811 (min 0.727) · transversal false
- **Near-duplicates (centroid cosine):** T0050 (0.912); T0172 (0.905)
- **Reference coverage:** linked: 15/26 assigned skills confidently linked (58%) (ESCO knowledge=4;ESCO skill=11)
- **Validity screening:** mixed — no shared word (head_word_share 0.19) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.811 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0050 (0.912); T0172 (0.905))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** crimping (0.877); rigging (0.867); sanding (0.863); ground rigging (0.856); grounding (0.850); polishing (0.842); caulking (0.836); finishing (0.835); waxing (0.835); suturing (0.833)

**Assigned members (26):** crimping; rigging; sanding; ground rigging; grounding; polishing; caulking; finishing; waxing; suturing; high rigging; splinting; tunneling; garnishing; centrifuging; ground up construction; cavitation; suture cutting; sand blasting; shot blasting; shimming; sheath removal; ground tackle; suture removal; ground support equipment; aliquotting

**Weak members (22):** fixturing; buffing; patching; roofing; floor buffing; lubrication; decapping; working under pressure; drill out applications; excavation; masking; pruning techniques; mold polishing; asphalt paving; working at height; patience; planting; effective tonnage; microsegmentation; hoists; gravity sprayers; heat sinking

**Confident member links:** crimping -> crimping [ESCO knowledge]; rigging -> use rigging equipment [ESCO skill]; sanding -> sanding techniques [ESCO knowledge]; ground rigging -> use rigging equipment [ESCO skill]; grounding -> seed the ground [ESCO skill]; polishing -> buffing motions [ESCO knowledge]; caulking -> caulk expansion joints [ESCO skill]; finishing -> sand wood [ESCO skill]; waxing -> wax body parts [ESCO skill]; high rigging -> use rigging tools [ESCO skill]; tunneling -> operate tunnelling machine [ESCO skill]; centrifuging -> operate centrifuges [ESCO skill]; sand blasting -> sand blasting machine parts [ESCO knowledge]; shot blasting -> blast surface [ESCO skill]; ground support equipment -> assist equipment operation [ESCO skill]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence sufficient
> 
> Three themes: rigging and grounding (rigging, ground rigging, high rigging, ground tackle), surface finishing (sanding, polishing, caulking, sand/shot blasting), and clinical or lab procedures (suturing, suture removal, splinting, centrifuging, aliquotting). Also 'ground' word matches (ground up construction, ground support equipment) and garnishing. Coverage 58%; validity = mixed.
> 
> *Also:* Near-duplicate T0050 Hand and Power Tool Operation (0.912) for the trade part.

### T0229 — Scaling and Growth Terms

*Loosely related single-word terms centred on scaling, ramping up and scale measures, mixed with unrelated product and brand names such as Zoom, ZoomInfo and Panorama.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members mix scaling vocabulary with unrelated software and brand names (zoom, zoominfo, apex, cornerstone, lawson) and a landscaping term (hardscape).
- **Members:** 14 assigned, 16 weak · **cohesion** cos_mean 0.813 (min 0.749) · transversal false
- **Near-duplicates (centroid cosine):** T0040 (0.901)
- **Reference coverage:** linked: 5/14 assigned skills confidently linked (36%) (ESCO knowledge=2;O*NET software=3)
- **Validity screening:** mixed — no shared word (head_word_share 0.14) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;weak_exceeds_assigned;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.813 is at or below the 25th percentile of all 374 topics
- weak_exceeds_assigned: 16 weak members > 14 assigned members
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0040 (0.901))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** zoom (0.876); scaling (0.853); scales (0.846); scale up (0.841); ramp (0.826); apex (0.824); axis (0.819); zoominfo (0.819); hardscape (0.815); panorama (0.790)

**Assigned members (14):** zoom; scaling; scales; scale up; ramp; apex; axis; zoominfo; hardscape; panorama; cornerstone; lawson; rise; cobra

**Weak members (16):** tuning; lean; step; rotation; tune ups; encompass; mt; 8x8; vtscada; zscaler; swing angle; composure; elevations; milestone; brocade; tricentis tosca

**Confident member links:** zoom -> Zoom [O*NET software]; scaling -> design principles [ESCO knowledge]; scales -> design principles [ESCO knowledge]; zoominfo -> Zoom [O*NET software]; panorama -> Panorama NovaView [O*NET software]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence sufficient
> 
> Small topic (14 assigned, 16 weak). Scaling words (scaling, scales, scale up, ramp) are mixed with brand names (zoom, zoominfo, apex, cornerstone, lawson, cobra, panorama) and hardscape. 'Scales' may mean weighing scales, not growth. Validity = mixed.
> 
> *Also:* The name 'Scaling and Growth Terms' describes words, not a skill.

### T0171 — Site and User Journey Design

*Planning, building and managing sites, templates and user journeys, spanning website management, site development, journey mapping and user experience design.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members mix website/site management and templates, user journey and experience design, and construction site planning, with a few unrelated items like virtual worlds and route navigation.
- **Members:** 29 assigned, 5 weak · **cohesion** cos_mean 0.818 (min 0.749) · transversal false
- **Near-duplicates (centroid cosine):** T0012 (0.913); T0125 (0.910); T0123 (0.905)
- **Reference coverage:** linked: 14/29 assigned skills confidently linked (48%) (ESCO knowledge=2;ESCO skill=6;O*NET software=5;O*NET software category=1)
- **Validity screening:** mixed — no shared word (head_word_share 0.21) and low cohesion · hierarchy: hold_split_candidate
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.818 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0012 (0.913); T0125 (0.910); T0123 (0.905))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** site experience (0.900); site development (0.865); site planning (0.859); user journeys (0.855); sitemapping (0.852); user experience (0.842); page builder (0.842); journey mapping (0.842); user journey maps (0.838); journey builder (0.838)

**Assigned members (29):** site experience; site development; site planning; user journeys; sitemapping; user experience; page builder; journey mapping; user journey maps; journey builder; template development; template building; experience cloud; site handler; multi site management; templates; design experience; site start up; website management; virtual experience; computer experience; arm templates; website updating; tridion sites; route navigation apps; user stories; virtual worlds; journey building; annotations

**Weak members (5):** site evaluations; place and route; dynamics 365; mr experience; go live

**Confident member links:** site development -> prepare building site [ESCO skill]; site planning -> prepare building site [ESCO skill]; sitemapping -> Site mapping software [O*NET software]; user experience -> combine business technology with user experience [ESCO skill]; page builder -> Adobe PageMaker [O*NET software]; journey mapping -> Route mapping software [O*NET software]; template development -> Template design software [O*NET software]; template building -> create floor plan template [ESCO skill]; templates -> Template design software [O*NET software]; design experience -> think creatively [ESCO skill]; website management -> manage website [ESCO skill]; computer experience -> computer equipment [ESCO knowledge]; route navigation apps -> Route navigation software [O*NET software category]; virtual worlds -> synthetic natural environment [ESCO knowledge]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): UNSURE** · confidence low · evidence insufficient
> 
> Most members are web/UX items (user journeys, journey mapping, user experience, website management, page builder, experience cloud). But several are ambiguous between web sites and construction sites: site development and site planning are linked to the ESCO skill 'prepare building site', and site start up / site handler could be either. The member strings alone cannot tell which meaning the postings use.
> 
> *Also:* Near-duplicates T0012 Web Front-End (0.913), T0125 Web Application Development (0.910), T0123 User Interface Design (0.905). If the site members turn out to be web, POTENTIAL_MERGE with T0123 is worth checking; if construction, INVESTIGATE_CLUSTER. Needs supporting postings.

### T0239 — Decorative Styling and Decorating

*Applying decorative and styling techniques, such as food, wardrobe and cake decorating and stencil design, to produce visually styled products and presentations.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members mix decorating and styling with unrelated items such as style guides, AP style, upholstery, spray booth, acetylene and music styles.
- **Members:** 22 assigned, 0 weak · **cohesion** cos_mean 0.827 (min 0.715) · transversal false
- **Near-duplicates (centroid cosine):** T0181 (0.914); T0193 (0.907)
- **Reference coverage:** linked: 13/22 assigned skills confidently linked (59%) (ESCO knowledge=9;ESCO skill=4)
- **Validity screening:** coherent — no surface-form, mixing or evidence problem detected · hierarchy: eligible
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.827 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0181 (0.914); T0193 (0.907))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** decorative designs (0.922); styling (0.891); food styling (0.872); style frames (0.868); stylesheets (0.863); decorative flowers (0.859); wardrobe styling (0.859); decorating tips (0.849); cookie decorating (0.845); stencil design (0.844)

**Assigned members (22):** decorative designs; styling; food styling; style frames; stylesheets; decorative flowers; wardrobe styling; decorating tips; cookie decorating; stencil design; decorating nozzles; decorating bags; style guides; cake decorating; upholstery; crafts; ap style; booth design; fashion knowledge; spray booth; diverse music styles; acetylene

**Weak members (0):** —

**Confident member links:** decorative designs -> paint decorative designs [ESCO skill]; styling -> hairdressing [ESCO knowledge]; food styling -> hairdressing [ESCO knowledge]; style frames -> optical components [ESCO knowledge]; stylesheets -> JSSS [ESCO knowledge]; decorative flowers -> design floral decorations [ESCO skill]; wardrobe styling -> advise on clothing style [ESCO skill]; decorating tips -> home decoration techniques [ESCO knowledge]; style guides -> writing style guides [ESCO knowledge]; upholstery -> upholstery tools [ESCO knowledge]; crafts -> crafting [ESCO knowledge]; spray booth -> pump paint [ESCO skill]; diverse music styles -> musical genres [ESCO knowledge]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence partial
> 
> Grouped by the words 'style' and 'decor': food / wardrobe styling and cake / cookie decorating sit with stylesheets, style guides, AP style (writing and web), style frames, diverse music styles, spray booth, acetylene and upholstery. The automatic validity rule says coherent (no weak members, head-word share not low), but the members show a word-form grouping. Some 'known_skill' links are wrong (food styling -> hairdressing, style frames -> optical components), so 59% coverage overstates the fit.
> 
> *Also:* Near-duplicates T0181 Layout and Spatial Design (0.914) and T0193 Painting and Art (0.907). The rule-based 'coherent' result and this recommendation disagree; a human should decide.

### T0193 — Painting and Art Techniques

*Knowledge and practice of fine art creation, including painting techniques, paint mixing and application, art mediums, and art history, with a smaller cluster of dental impression work.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Dominant theme is painting and art, but several members (impression materials, impression pouring, custom impression trays, digital impressions, itero digital impressions) belong to a separate dental impression theme.}
- **Members:** 23 assigned, 2 weak · **cohesion** cos_mean 0.828 (min 0.720) · transversal false
- **Near-duplicates (centroid cosine):** T0239 (0.907)
- **Reference coverage:** linked: 11/23 assigned skills confidently linked (48%) (ESCO knowledge=1;ESCO skill=10)
- **Validity screening:** coherent — no surface-form, mixing or evidence problem detected · hierarchy: eligible
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.828 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0239 (0.907))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** artworking (0.894); art techniques (0.878); painting (0.874); artwork analysis (0.866); impression materials (0.865); paint application (0.862); painting techniques (0.861); impression pouring (0.856); paint retouching (0.844); art mediums (0.841)

**Assigned members (23):** artworking; art techniques; painting; artwork analysis; impression materials; paint application; painting techniques; impression pouring; paint retouching; art mediums; mockups; paint mixing; mock ups; custom impression trays; paint qualities; digital impressions; post paint finishing; artistic ability; impression casts; sculpture; art history; butterfly method; itero digital impressions

**Weak members (2):** makeup application; color matching

**Confident member links:** artworking -> create artwork [ESCO skill]; art techniques -> study artistic techniques [ESCO skill]; painting -> paint surfaces [ESCO skill]; artwork analysis -> contextualise artistic work [ESCO skill]; paint application -> apply colour coats [ESCO skill]; painting techniques -> use painting techniques [ESCO skill]; mockups -> create mock-ups [ESCO skill]; paint mixing -> mix paint [ESCO skill]; paint qualities -> inspect paint quality [ESCO skill]; sculpture -> create sculptures [ESCO skill]; art history -> art history [ESCO knowledge]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence sufficient
> 
> The core of about 16 members is fine art and painting (painting techniques, paint mixing, art history, sculpture), with ESCO links that agree. But 6 dental impression members (impression materials, impression pouring, custom impression trays, digital impressions, itero digital impressions, impression casts) joined because of the word 'impression'. The name fits the core.
> 
> *Also:* Low-impact case: reassigning the dental members may be enough and the name could then be KEPT. Near-duplicate T0239 (0.907) is itself mixed.

### T0293 — Sewing and Stitching

*Hand and machine sewing and stitching of materials, including industrial and single or double needle sewing equipment; a smaller group of members concerns brazing metal joining.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Most members concern sewing, but a distinct brazing group (hand brazing, induction brazing, braze) and a few unrelated items (classical hand analysis, hand scratches) do not fit the name.
- **Members:** 19 assigned, 2 weak · **cohesion** cos_mean 0.829 (min 0.706) · transversal false
- **Near-duplicates (centroid cosine):** T0140 (0.908); T0050 (0.904)
- **Reference coverage:** linked: 12/19 assigned skills confidently linked (63%) (ESCO knowledge=4;ESCO skill=8)
- **Validity screening:** coherent — no surface-form, mixing or evidence problem detected · hierarchy: eligible
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.829 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0140 (0.908); T0050 (0.904))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** hand sewing (0.918); sewing (0.890); machine sewing (0.890); hand stitching (0.887); sewing equipment (0.878); hand brazing (0.875); industrial sewing equipment (0.871); stitching (0.871); custom sewing (0.861); industrial sewing machines (0.849)

**Assigned members (19):** hand sewing; sewing; machine sewing; hand stitching; sewing equipment; hand brazing; industrial sewing equipment; stitching; custom sewing; industrial sewing machines; single needle machines; double needle machines; induction brazing; hand to surface method; brazing; classical hand analysis; brazing alloy; hand scratches; braze

**Weak members (2):** splint fabrication; mouse husbandry

**Confident member links:** hand sewing -> use manual knitting techniques [ESCO skill]; sewing -> dressmaking [ESCO knowledge]; machine sewing -> dressmaking [ESCO knowledge]; hand stitching -> apply stitching techniques [ESCO skill]; sewing equipment -> dressmaking [ESCO knowledge]; hand brazing -> apply brazing techniques [ESCO skill]; industrial sewing equipment -> tend automatic sewing machines [ESCO skill]; stitching -> apply stitching techniques [ESCO skill]; custom sewing -> dressmaking [ESCO knowledge]; industrial sewing machines -> tend automatic sewing machines [ESCO skill]; brazing -> apply brazing techniques [ESCO skill]; classical hand analysis -> read palms [ESCO skill]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence medium · evidence sufficient
> 
> The core of about 11 sewing and stitching members is coherent. Attached by the word 'hand' or 'braz': brazing (hand brazing, induction brazing, braze, brazing alloy) is metal joining, plus classical hand analysis (linked to ESCO 'read palms', a wrong link), hand scratches and hand to surface method.
> 
> *Also:* Low-impact case like T0193: removing the brazing and 'hand' members may be enough to KEEP the name. Near-duplicate T0140 (0.908) shares the garment theme.

### T0177 — Bill of Materials Management

*Creating and analyzing bills of materials and related product or lifecycle management systems, within a topic dominated by short, ambiguous three-letter acronyms.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Most members are ambiguous acronyms (ltm, m2m, sem, srm, ohm's law, veeam, tm1) that do not share a clear competency; only the BOM and PLM items form a coherent theme.
- **Members:** 31 assigned, 24 weak · **cohesion** cos_mean 0.836 (min 0.721) · transversal false
- **Near-duplicates (centroid cosine):** T0272 (0.912)
- **Reference coverage:** low coverage (<30%): 4/31 assigned skills confidently linked (13%) (ESCO knowledge=1;ESCO skill=2;O*NET software=1)
- **Validity screening:** surface_form_cluster — no shared word (head_word_share 0.10); acronym_share 0.84 >= 0.5 · hierarchy: exclude_until_reclustered
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.836 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0272 (0.912))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** ltm (0.885); m2m (0.884); sem (0.876); bom (0.876); plm (0.875); mam (0.873); apm (0.869); srm (0.868); asm (0.866); bim (0.864)

**Assigned members (31):** ltm; m2m; sem; bom; plm; mam; apm; srm; asm; bim; ipam; powm; skm; tms; tdm; alm; afm; uvm; tpm; bom analysis; rprm; bom creation; tm1; tpms; s.g.m; sqcdm; wpm; veeam; ohm's law; cyme; t1

**Weak members (24):** mdm; itsm; ecm; gpm; iam; hcm; bpms; gtm; cpm; itsm tool; fem; ppm tools; plm tools; hcm module; e1 ifm; itam; asme; snmp; mbom; rsmeans; jmp; scom; lod300 bim models; postman

**Confident member links:** sem -> search engine optimisation [ESCO knowledge]; bom -> draft bill of materials [ESCO skill]; tdm -> Technical Data Management System TDMS [O*NET software]; bom creation -> draft bill of materials [ESCO skill]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence high · evidence partial
> 
> Only the BOM / PLM items (bom, bom analysis, bom creation, plm) match the name. The rest are three-letter acronyms ending in 'm' (ltm, m2m, sem, srm, asm, ipam, alm, uvm, tpm) plus ohm's law and veeam. Validity rules: surface_form_cluster (acronym share 0.84); coverage 13%.
> 
> *Also:* Near-duplicate T0272 Management System Acronyms (0.912), also a surface-form cluster. Ambiguous acronyms need posting context.

### T0190 — Materials Preparation and Planning

*Selecting, preparing, formulating and managing raw and construction materials, including planning material requirements and distribution, with some laboratory and medical preparation items.*

- **Source / model confidence:** anthropic / claude-sonnet-5-5 / low — Members mix materials planning/management with formulation and lab or medical preparation (contrast materials, reagent preparation, explant preparation, soybean transformation) and printing make-ready items.
- **Members:** 27 assigned, 9 weak · **cohesion** cos_mean 0.840 (min 0.668) · transversal false
- **Near-duplicates (centroid cosine):** T0084 (0.900)
- **Reference coverage:** linked: 17/27 assigned skills confidently linked (63%) (ESCO knowledge=2;ESCO skill=11;O*NET Transferable Skills=1;O*NET software=2;O*NET software category=1)
- **Validity screening:** coherent — no surface-form, mixing or evidence problem detected · hierarchy: eligible
- **Review flags:** `low_cohesion;near_duplicate_topic;llm_confidence_low`

**Why flagged (source evidence)**

- low_cohesion: cos_mean 0.840 is at or below the 25th percentile of all 374 topics
- near_duplicate_topic: a neighbour centroid has cosine >= 0.90 (T0084 (0.900))
- llm_confidence_low: the naming model rated its own name 'low' confidence

**Representative skills:** material preparation (0.937); material formulation (0.906); materials planning (0.895); board materials preparation (0.886); building materials (0.884); material selection (0.873); materials management (0.867); materials requirement planning (0.866); material design guidelines (0.858); construction materials (0.856)

**Assigned members (27):** material preparation; material formulation; materials planning; board materials preparation; building materials; material selection; materials management; materials requirement planning; material design guidelines; construction materials; material distribution; contrast materials; material submissions; materials systems; engineered materials; reagent preparation; raw materials; explant preparation; adhesive preparation; formulation; raw material transformation; time and material; make ready process; contrast preparation; drug preparation; make ready program; soybean transformation

**Weak members (9):** material fabrication; material handling; materials characterization; material flow; nonconforming material handling; packaging methods; build to suit; polymerization; 1099 preparation

**Confident member links:** material preparation -> prepare roofing materials [ESCO skill]; material formulation -> mix treating materials [ESCO skill]; materials planning -> ERP INDUSTRIOS Material Planning [O*NET software]; board materials preparation -> design circuit boards [ESCO skill]; building materials -> handle building materials [ESCO skill]; material selection -> select material to process [ESCO skill]; materials management -> Management of Material Resources [O*NET Transferable Skills]; materials requirement planning -> Materials requirements planning logistics and supply chain software [O*NET software category]; construction materials -> advise on construction materials [ESCO skill]; material distribution -> transport construction supplies [ESCO skill]; contrast materials -> administer contrast media [ESCO skill]; materials systems -> Integrated materials management systems [O*NET software]; raw materials -> prepare raw materials [ESCO skill]; adhesive preparation -> adhesives [ESCO knowledge]; formulation -> food product ingredients [ESCO knowledge]; contrast preparation -> administer contrast media [ESCO skill]; drug preparation -> mix chemicals [ESCO skill]

> **AI recommendation (AI-GENERATED, NOT HUMAN-VALIDATED): INVESTIGATE_CLUSTER** · confidence low · evidence partial
> 
> Most members share the word 'material(s)' but span different skills: supply-chain planning (materials requirement planning, materials management), construction materials, and material science (engineered materials, material formulation). Joined by the word 'preparation' are lab and medical items (reagent preparation, explant preparation, contrast preparation, drug preparation, soybean transformation) and printing make-ready. The automatic validity rule says coherent; the members suggest a word-form grouping.
> 
> *Also:* Borderline: a human could reasonably KEEP it as a broad materials topic. Near-duplicate T0084 Structural Engineering Design (0.900) only for the construction part.
