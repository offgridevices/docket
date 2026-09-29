# MIL-STD-3022 VV&A record — vva-cbo-metric

## Problem Statement

**From the VV&A record's dedicated field:**
Question: How would the Army's planned Ground Combat Vehicle compare with four alternatives — the Israeli Namer, an upgraded Bradley, the German Puma, and retaining the current Bradley — in capability, cost and programmatic risk over 2014 through 2030, measured against the current Bradley IFV?
Decision to be made: Whether to continue the Ground Combat Vehicle program as planned or to pursue one of the four alternatives.

**From `sections[]` ("Problem Statement"):**
See the charter, ch-gcv-2013.

## M&S Requirements and Acceptability Criteria

**From the VV&A record's dedicated field:**
Reproduce both of CBO's published overall-improvement figures (Table 2-2, p. 21) from CBO's published category scores and published weights (Table A-3, p. 35), to within the one point CBO's own rounding to whole percent allows, and reproduce both published rankings exactly.

**From `sections[]` ("M&S Requirements and Acceptability Criteria"):**
Reproduce CBO's Table 2-2 overall-improvement figures to within one point and both rankings exactly.

## M&S Assumptions, Capabilities, Limitations & Risks/Impacts

**From the VV&A record's dedicated field:**
**Assumptions**
- value is additive across the four categories, as CBO's construction is
- the category scores are commensurable percentages on a common reference

**Capabilities**
- weighted additive aggregation over the four categories
- one-at-a-time flip analysis and weight-simplex robustness

**Limitations**
- no interaction terms between categories
- CBO's inputs are published rounded to whole percent

**Risks**
- a reproduction within a rounding point could mask a different construction that happens to agree at this precision

**From `sections[]` ("M&S Assumptions, Capabilities, Limitations & Risks/Impacts"):**
As listed in the structured field of this record.

## Accreditation Methodology

**From the VV&A record's dedicated field:**
**Methodology**
Additive multi-attribute value aggregation over the four categories (docket kernel, method mavt), with the weights of Table A-3 and no value-function transformation: the raw percentage improvement is the value.

**Accreditation Decision**
Authority: Congressional Budget Office (published methodology, appendix pp. 33–35); reproduction checked against Table 2-2 by this reconstruction
Date: 2013-04
Scope: comparison of the notional GCV and four alternatives on four categories of capability, relative to the current Bradley IFV, on CBO's own published inputs
Basis: document
Document: Congressional Budget Office, The Army's Ground Combat Vehicle Program and Alternatives (April 2013)

**From `sections[]` ("Accreditation Methodology"):**
Comparison of the kernel's output against CBO's published values, asserted in the demonstration's test suite.

## Issues

This section is not applicable.
Reason: MIL-STD-3022 §5.3 retains every section; there are no outstanding issues and no lessons learned to record for a reproduction of a published additive metric.
Authority: shreyash (reconstruction author), 2026-09-05

## Key Participants

CBO (methodology, appendix pp. 33–35); the docket kernel (computation); shreyash (reconstruction).

## Resources

The public CBO report, and nothing else.

## Lessons Learned

This section is not applicable.
Reason: MIL-STD-3022 §5.3 retains every section; there are no outstanding issues and no lessons learned to record for a reproduction of a published additive metric.
Authority: shreyash (reconstruction author), 2026-09-05

## Appendix: Requirements Traceability Matrix

| claim_id | claim_text | section | level | evidence_id | evidence_title | evidence_level | metadata_level | pointer | scope_built_to_answer | vva_status | review_status | reliability_steps | reuse_justification | assessable_at_U |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cl-cost | Fielding Pumas or upgraded Bradleys would cost $14 billion and $9 billion less, respectively, than the Army's GCV program over 2014 through 2030. | evaluation-results | U | ev-cbo-cost-estimate | CBO's cost estimates for the GCV program and the four options, 2014–2030 | U | U | sources/cbo-2013-04-gcv-program-and-alternatives.pdf#page=26 | What would developing and procuring each option cost over 2014–2030, in 2013 dollars? | n/a | reviewed | 1 |  | True |
| cl-primary | Under CBO's primary metric the Puma is the most capable of the five vehicles, followed by the upgraded Bradley IFV, the notional GCV and the Namer. | evaluation-results | U | ev-army-expert-estimates | Army analysts' estimates of the Namer's and the Puma's performance relative to the current Bradley IFV | U | U | sources/cbo-2013-04-gcv-program-and-alternatives.pdf#page=25 | How would the Namer and the Puma have performed against the current Bradley IFV on protection, survivability and lethality? | n/a | reviewed | 1 | The Namer's and the Puma's protection and lethality are Army analysts' estimates, made because the technical data were insufficient to simulate those vehicles; CBO placed them beside the GCV's simulated scores and said so (p. 20 fn 4). | True |
| cl-primary | Under CBO's primary metric the Puma is the most capable of the five vehicles, followed by the upgraded Bradley IFV, the notional GCV and the Namer. | evaluation-results | U | ev-army-mobility-data | Automotive characteristics behind the mobility score: acceleration, average off-road speed, range on a tank of fuel, turning radius, width and bridge-crossing capacity | U | U | sources/cbo-2013-04-gcv-program-and-alternatives.pdf#page=40 | How mobile is each of the five vehicles on- and off-road, relative to the current Bradley IFV? | n/a | reviewed | 1 |  | True |
| cl-primary | Under CBO's primary metric the Puma is the most capable of the five vehicles, followed by the upgraded Bradley IFV, the notional GCV and the Namer. | evaluation-results | U | ev-cbo-2013 | Congressional Budget Office, The Army's Ground Combat Vehicle Program and Alternatives (April 2013) | U | U | https://www.cbo.gov/publication/44044 | Compare the Army's plan for the Ground Combat Vehicle with four alternatives on capability, cost and programmatic risk over 2014–2030 | n/a | reviewed | 1 |  | True |
| cl-secondary | Under CBO's secondary metric, which scores the nine-member squad all or nothing, the Puma stays slightly ahead of the GCV, and the Namer and the upgraded Bradley are within a quarter-point of each other — CBO printed both as 25. | evaluation-results | U | ev-cbo-2013 | Congressional Budget Office, The Army's Ground Combat Vehicle Program and Alternatives (April 2013) | U | U | https://www.cbo.gov/publication/44044 | Compare the Army's plan for the Ground Combat Vehicle with four alternatives on capability, cost and programmatic risk over 2014–2030 | n/a | reviewed | 1 |  | True |
| cl-squad-rationale | The Army's stated reason for carrying a full nine-member squad in one vehicle is that a squad split between vehicles is hard to organise and direct in the moments after the soldiers dismount. | grca | U | ev-army-squad-2011 | Department of the Army, Capabilities Integration Center, The Squad and Its Ground Combat Vehicle (2011) | U | U | http://go.usa.gov/4fDJ | Why does the Army want a full nine-member squad in one vehicle? | n/a | reviewed | gap:gap-squad-reliability |  | True |
| cl-squad-rationale | The Army's stated reason for carrying a full nine-member squad in one vehicle is that a squad split between vehicles is hard to organise and direct in the moments after the soldiers dismount. | grca | U | ev-cbo-2013 | Congressional Budget Office, The Army's Ground Combat Vehicle Program and Alternatives (April 2013) | U | U | https://www.cbo.gov/publication/44044 | Compare the Army's plan for the Ground Combat Vehicle with four alternatives on capability, cost and programmatic risk over 2014–2030 | n/a | reviewed | 1 | The sentence is read off CBO's Box 1-1, which restates the Army's operational concept for the squad inside a requirements trade-off study and cites the Army's own document for it (p. 6 and fn 2/fn 4). | True |
| cl-weights | CBO's primary-metric weights are the Army's category weights for the four categories CBO could assess, renormalised to sum to one (CBO writes 'based on'; Table A-1's figures make it an exact renormalisation); the Army derived those from rankings given by soldiers who had deployed with combat brigades. | objectives-and-measures | U | ev-cbo-2013 | Congressional Budget Office, The Army's Ground Combat Vehicle Program and Alternatives (April 2013) | U | U | https://www.cbo.gov/publication/44044 | Compare the Army's plan for the Ground Combat Vehicle with four alternatives on capability, cost and programmatic risk over 2014–2030 | n/a | reviewed | 1 |  | True |
| cl-weights | CBO's primary-metric weights are the Army's category weights for the four categories CBO could assess, renormalised to sum to one (CBO writes 'based on'; Table A-1's figures make it an exact renormalisation); the Army derived those from rankings given by soldiers who had deployed with combat brigades. | objectives-and-measures | U | ev-soldier-survey | Soldier ranking of the characteristics that matter most in a fighting vehicle — the source of the Army's AoA category weights | U | U | sources/cbo-2013-04-gcv-program-and-alternatives.pdf#page=38 | Which characteristics of a fighting vehicle matter most to soldiers who have deployed with combat brigades? | n/a | reviewed | 1 | The ranking was collected to find out which characteristics matter most to deployed soldiers; CBO reused it as the weighting for a requirements trade-off and states that derivation in its methodology appendix (pp. 33–34). | True |
