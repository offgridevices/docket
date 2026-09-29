// Plain language by default, the record's term on demand (spec §11; Appendix A's
// glossary is the content). Every label a person reads comes through `term()`; ids,
// hashes, revs, seeds and state names stay mono and verbatim wherever they are data.

export type TermKey =
  | 'draft' | 'accepted' | 'computed' | 'linchpin' | 'gap' | 'exclusion' | 'charter'
  | 'consequences' | 'g1' | 'g2' | 'g3' | 'g4' | 'run' | 'flip' | 'simplex' | 'readiness'
  | 'verdicts' | 'blocking' | 'scope' | 'vva' | 'withheld' | 'superseded' | 'trigger'
  | 'pkg' | 'locator' | 'actor';

export interface TermEntry {
  plain: string;
  record: string;
  explain: string;
}

export const GLOSSARY: Record<TermKey, TermEntry> = {
  draft: { plain: 'drafted by the AI, not yet agreed', record: 'DRAFT · agent-proposed', explain: 'The AI read a source and proposed a typed object. Nothing about it is accepted.' },
  accepted: { plain: 'agreed by a person', record: 'human-accepted', explain: 'A person accepted, edited or authored this, and their actor id is on it.' },
  computed: { plain: 'computed (same inputs, same answer)', record: 'kernel-computed', explain: 'Ordinary deterministic code wrote this value; re-running it gives the same bytes.' },
  linchpin: { plain: 'an assumption the answer depends on', record: 'linchpin assumption', explain: 'If it is wrong the ranking does not shift a little, it inverts.' },
  gap: { plain: 'something the source never says', record: 'InsufficientEvidence', explain: 'Rather than leave a field blank, the record holds an object saying what was looked for and not found.' },
  exclusion: { plain: 'left out on purpose, with a reason', record: 'Exclusion', explain: 'A recorded omission, with the reason type and the authority who decided it.' },
  charter: { plain: 'the question, the stakes, the scope', record: 'Charter', explain: 'Three mandated fields: the question, what happens if it is wrong, and what is in and out of scope.' },
  consequences: { plain: 'what happens if this is wrong', record: 'consequencesOfErroneousOutput', explain: 'One of the three charter fields; when the source never states it, a person must.' },
  g1: { plain: 'approve the model (gate 1)', record: 'G1 · MODEL_APPROVED', explain: 'The door to every computation. Nothing is computed before it.' },
  g2: { plain: 'approve the plan (gate 2)', record: 'G2 · PLAN_APPROVED', explain: 'A person approves how the comparison will be evaluated.' },
  g3: { plain: 'sign the package (gate 3)', record: 'G3 · SIGNED', explain: 'A person takes the decision, with its conditions and stop rules.' },
  g4: { plain: 'accept a refresh (gate 4)', record: 'G4 · refresh', explain: 'A person opens a new episode; the old one is superseded, never deleted.' },
  run: { plain: 'a sealed calculation', record: 'EvaluationRun', explain: 'Sealed with its seed, kernel version and hash, so it can be re-run byte for byte.' },
  flip: { plain: 'what would change the answer', record: 'flip analysis · flip distance', explain: 'The smallest change to one input that would change which option comes first.' },
  simplex: { plain: 'how often each option wins across all weightings', record: 'weight simplex', explain: 'The fraction of all possible weightings in which each option ranks first.' },
  readiness: { plain: 'ready to sign?', record: 'readiness · four-state grid', explain: 'The record scored against the applicable questions of the research standard.' },
  verdicts: { plain: 'objectivity · validity · reliability', record: 'dimension verdicts', explain: 'Three judgements aggregated from the question ratings by a stated rule.' },
  blocking: { plain: 'something that stops sign-off', record: 'blocking finding', explain: 'A rule the record fails; it names the objects it is about.' },
  scope: { plain: 'what this evidence was built to answer', record: 'scope of validity', explain: 'Using evidence outside it is reuse, and reuse carries a written justification.' },
  vva: { plain: 'whether the model behind it was checked', record: 'VV&A', explain: 'Verification, validation and accreditation of the model an evidence item came from.' },
  withheld: { plain: 'the value exists but is not shown at this level', record: 'withheld at this rendering', explain: 'The object and its provenance are visible; the value is not.' },
  superseded: { plain: 'replaced by a later episode (kept, never deleted)', record: 'SUPERSEDED', explain: 'Nothing is deleted; a later episode supersedes an earlier one.' },
  trigger: { plain: 'a reason to look again', record: 'RefreshTrigger', explain: 'An elapsed period, a change of evidence, a changed assumption, or a signer sending the package back.' },
  pkg: { plain: 'the decision package (the receipt)', record: 'Decision Package', explain: 'Sixteen sections where every sentence cites the object it was rendered from.' },
  locator: { plain: 'where this came from (page)', record: 'ingestion provenance · locator', explain: 'The page or paragraph of the source the draft was taken from.' },
  actor: { plain: 'who did it', record: 'actor id', explain: 'Every human write in this session is attributed to it.' },
};

export function term(key: TermKey): TermEntry {
  return GLOSSARY[key];
}
