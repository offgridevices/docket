# NOTICE — third-party documents in `sources/`, item by item

`sources/` holds a provenance note for each public document that the documentation and
the demonstrations cite. The documents themselves are not committed to this repository;
each note gives the URL to fetch it from. Those documents were written by other people and other organisations. This file records, **for
each one separately**, what is known about its rights and where that knowledge came from.

There is deliberately no blanket statement here. A single sentence covering the whole
directory would be wrong the moment one item is not a US Government work — and two are
not. One is copyrighted press, held as a URL and two quoted sentences with no file. The
other is an author preprint, held as a sidecar only. Rights are recorded per item, in
three classes, and every row is read from that document's `.source.md` sidecar
rather than inferred from its filename.

This file is not a licence and grants no rights in any of these documents. The project's
own work is licensed separately: `LICENSING.md` says which files are under AGPL-3.0-only
(`LICENSE`) and which under Apache-2.0 (`LICENSE-APACHE`). Nothing in those licences
covers the documents listed here.

## How to read a row

Each sidecar carries a **Release status** line. That line answers a *distribution*
question — is this document publicly released, does it carry a distribution statement,
does a CUI marking check on it come back clean. It is not, by itself, a copyright
determination.

The **class** column is therefore derived, and here is the derivation, stated so it can be
argued with:

- Where the sidecar itself speaks to rights — as the Breaking Defense and arXiv sidecars
  do — the class follows what the sidecar says, quoted.
- Otherwise the class follows the sidecar's **Publisher** line together with its Release
  status: a work prepared by an officer or employee of the US Government as part of that
  person's official duties is not subject to copyright in the United States
  (17 U.S.C. §105), and the sidecar records the publisher as a US Government body and the
  document as publicly released.

Three limits on that derivation, stated because they are real:

1. §105 removes copyright protection **in the United States**. It says nothing about
   other jurisdictions.
2. A US Government work can still carry third-party material — a licensed photograph, a
   contractor's figure — that §105 does not reach. No page-by-page review for embedded
   third-party material has been done on any item below.
3. **One** sidecar records a release status with no marking check behind it, and it is
   flagged in its row: `gao-23-106549` states a distribution rationale ("Report to
   Congressional Committees, no distribution limitation") but records no `Release check`
   line, unlike the other GAO sidecars, which record `no-CUI-marking`. That document is
   the linchpin of the demonstrations, which is a reason to say so here rather than a
   reason to round it up.

Quotations below are verbatim from the sidecar, with one formatting change: a double quote
inside a quotation is rendered as a single quote so it survives the table. The seven budget
extracts carry byte-identical Publisher and Release status lines, so six of them say "same
wording as FY2021" rather than repeating it.

## Class 1 — US Government work (17 U.S.C. §105)

| File | Publisher, as the sidecar records it | Release status, quoted from the sidecar |
|---|---|---|
| `acc-dta-2022-10-25-omfv-phase-3-4-industry-qa-01-140.pdf` | U.S. Army Contracting Command – Detroit Arsenal (ACC-DTA) | "**Public.** Cover page carries 'Distribution Statement A: Approved for public release; distribution is unlimited.' Release check on pp. 1–2: `no-CUI-marking`." (the sidecar continues, explaining a "Distribution D or E" mention on p. 9 that describes future proposal documents, not this one) |
| `army-2020-02-25-omfv-characteristics-for-industry-comment.md` | U.S. Army — Next Generation Combat Vehicle Cross-Functional Team, via Army Contracting Command – Detroit Arsenal | "**Public.** Unrestricted SAM.gov (originally beta.SAM.gov) public notice text. No attachments. No CUI, no export control, no login required." |
| `army-2020-04-09-omfv-industry-day-narrative.pdf` | U.S. Army PM Maneuver Combat Systems / NGCV CFT, via ACC-DTA | "**Public.** Cover page carries 'DISTRIBUTION A: Approved for public release: distribution is unlimited. 09 APR 2020'. Release check on pp. 1–2: `no-CUI-marking \| DistA`." |
| `army-2020-12-09-omfv-industry-day-briefing.pdf` | U.S. Army PEO Ground Combat Systems, PM Maneuver Combat Systems, NGCV CFT and ACC-DTA | "**Public.** Every slide carries 'DISTRIBUTION STATEMENT A: Approved for public release: distribution is unlimited.'" (the sidecar adds that a full-document scan confirmed the banner from the title slide onward) |
| `army-2023-06-26-omfv-phase-3-4-award` — **sidecar only, no file committed**` | U.S. Army, via defense.gov contract announcements | "**Believed a public press release. NOT CONFIRMED by retrieval.** Human release-status call outstanding." The announcement itself was not retrieved; the award month is sourced from the FY2025 R-3 exhibit, the day is not |
| `army-rdte-r2-fy2021-omfv-xm30-extract.pdf` | Department of the Army, Assistant Secretary of the Army (Financial Management and Comptroller) | "**Public.** Every page carries the header `UNCLASSIFIED`. No distribution statement, no CUI, no FOUO, no export control — congressional budget justification books are published in full. Release check on pp. 1–2: `no-CUI-marking`." |
| `army-rdte-r2-fy2022-omfv-xm30-extract.pdf` | Department of the Army, Assistant Secretary of the Army (Financial Management and Comptroller) | same wording as FY2021, quoted above |
| `army-rdte-r2-fy2023-omfv-xm30-extract.pdf` | Department of the Army, Assistant Secretary of the Army (Financial Management and Comptroller) | same wording as FY2021, quoted above |
| `army-rdte-r2-fy2024-omfv-xm30-extract.pdf` | Department of the Army, Assistant Secretary of the Army (Financial Management and Comptroller) | same wording as FY2021, quoted above |
| `army-rdte-r2-fy2025-omfv-xm30-extract.pdf` | Department of the Army, Assistant Secretary of the Army (Financial Management and Comptroller) | same wording as FY2021, quoted above |
| `army-rdte-r2-fy2026-omfv-xm30-extract.pdf` | Department of the Army, Assistant Secretary of the Army (Financial Management and Comptroller) | same wording as FY2021, quoted above |
| `army-rdte-r2-fy2027-omfv-xm30-extract.pdf` | Department of the Army, Assistant Secretary of the Army (Financial Management and Comptroller) | same wording as FY2021, quoted above |
| `cbo-2013-04-gcv-program-and-alternatives.pdf` | Congressional Budget Office | "**Public.** US Government work; CBO publications carry no distribution limitation. Release check on pp. 1–2: `no-CUI-marking`; no distribution statement (CBO does not use them)." |
| `gao-06-938-defense-transportation-mobility-capabilities-study.pdf` | U.S. Government Accountability Office | "**Public.** A GAO product issued to Congress and published on gao.gov; a US Government work, not subject to copyright (17 U.S.C. §105). Release check over the full text: no CUI, FOUO, NOFORN or distribution-limitation marking anywhere, and the report carries GAO's own public-availability statement pointing at gao.gov." |
| `gao-11-82r-additional-information-is-needed-for-dod-s.pdf` | U.S. Government Accountability Office | "**Public.** A GAO product issued to Congress and published on gao.gov; a US Government work, not subject to copyright (17 U.S.C. §105). Release check over the full text: no CUI, FOUO, NOFORN or distribution-limitation marking anywhere, and the report carries GAO's own public-availability statement pointing at gao.gov." |
| `gao-15-457r-air-force-s-airlift-study-met-mandate.pdf` | U.S. Government Accountability Office | "**Public.** A GAO product issued to Congress and published on gao.gov; a US Government work, not subject to copyright (17 U.S.C. §105). Release check over the full text: no CUI, FOUO, NOFORN or distribution-limitation marking anywhere, and the report carries GAO's own public-availability statement pointing at gao.gov." |
| `gao-15-548-army-combat-vehicles-industrial-base-study.pdf` | U.S. Government Accountability Office | "**Public.** Report to Congressional Committees, no distribution limitation. Release check on pp. 1–2: `no-CUI-marking`." |
| `gao-16-820-dod-needs-further-analysis-of-the-size.pdf` | U.S. Government Accountability Office | "**Public.** A GAO product issued to Congress and published on gao.gov; a US Government work, not subject to copyright (17 U.S.C. §105). Release check over the full text: no CUI, FOUO, NOFORN or distribution-limitation marking anywhere, and the report carries GAO's own public-availability statement pointing at gao.gov." |
| `gao-16-86-actions-needed-to-identify-and-sustain-critical.pdf` | U.S. Government Accountability Office | "**Public.** A GAO product issued to Congress and published on gao.gov; a US Government work, not subject to copyright (17 U.S.C. §105). Release check over the full text: no CUI, FOUO, NOFORN or distribution-limitation marking anywhere, and the report carries GAO's own public-availability statement pointing at gao.gov." |
| `gao-18-230-dod-needs-to-improve-the-accuracy-of.pdf` | U.S. Government Accountability Office | "**Public.** A GAO product issued to Congress and published on gao.gov; a US Government work, not subject to copyright (17 U.S.C. §105). Release check over the full text: no CUI, FOUO, NOFORN or distribution-limitation marking anywhere, and the report carries GAO's own public-availability statement pointing at gao.gov." |
| `gao-21-460-tactical-wheeled-vehicles-accessible.pdf` | U.S. Government Accountability Office | "**Public.** Report to Congressional Committees, no distribution limitation. Release check on pp. 1–2: `no-CUI-marking`." (the sidecar notes p. 3 carries an unfilled template placeholder that looks like a CUI banner) |
| `gao-23-106059` — **sidecar only, no file committed** | U.S. Government Accountability Office | "**Public.** Report to Congressional Committees, no distribution limitation. Release check on pp. 1–2 of the local copy: `no-CUI-marking`." The file is not in the repository: it is 24.7 MB against the ~25 MB rule and only two of its 259 pages are cited [src: sources/README.md] |
| `gao-23-106549.pdf` | U.S. Government Accountability Office | "**Public.** Report to Congressional Committees, no distribution limitation." — **distribution rationale recorded, no `Release check` line in the sidecar.** The other three GAO sidecars record `no-CUI-marking`; this one does not |
| `gao-24-106982-agencies-need-additional-guidance-to-assess-their.pdf` | U.S. Government Accountability Office | "**Public.** A GAO product issued to Congress and published on gao.gov; a US Government work, not subject to copyright (17 U.S.C. §105). Release check over the full text: no CUI, FOUO, NOFORN or distribution-limitation marking anywhere, and the report carries GAO's own public-availability statement pointing at gao.gov." |

## Class 2 — Copyrighted press: URL and quotation only, no file

| Entry | Publisher, as the sidecar records it | Release status, quoted from the sidecar |
|---|---|---|
| `breaking-defense-2020-02-06-polish-bridge-problem` — **sidecar only, no file committed** | Breaking Defense (Sydney J. Freedberg Jr.) | "**Copyrighted press. Not a US Government work.** No full-text copy is committed to this repository. Quoted below under fair use, at the shortest length that carries the point." |

The sidecar carries two quoted sentences and the landing page. No article text beyond
those two sentences is in this repository, and none should be added.

## Class 3 — Author preprints

One entry, a stub. Same rule: one row per item, read from its sidecar, at the time it is
promoted.

| File | Publisher, as the sidecar records it | Release status, quoted from the sidecar |
|---|---|---|
| `arxiv-2607-20492-phantomfill` — **sidecar only, no file committed** | arXiv (author preprint) | "**Public.** Author preprint, publicly posted on arXiv and openly readable at the abstract page above. Not a US Government work; not redistributed here, which is why this entry is a stub." |

## Not listed here, on purpose

`sources/` contains only documents that have been promoted, each with a sidecar. The local
research library is gitignored and is not part of this repository; nothing in it is listed
in this file, because listing it would imply a distribution posture it does not have.
Anything held under a personal or individual licence is never promoted and never listed.

UI typefaces: OFL-licensed, see `ui/src/brand/FONTS.md`.

---

Every row above was read from that document's `.source.md` sidecar. If a sidecar and this
table disagree, the sidecar is authoritative and this table is wrong.
