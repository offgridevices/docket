// Evidence (spec §16) — the register with every slot filled: every field that can be a
// P3 slot (`pointer`, `scopeOfValidity`, `reliabilitySteps`, `inclusionReason`, and the
// per-limitation `impact`) renders through `Slot`: content, a `GapCard` or an
// `ExclusionCard`, and nothing else — a blank cell is the one thing this view may never
// show (plan Task 8, carried unchanged into the new frame by this task). The register
// itself is read-only here; accepting or rejecting a drafted item belongs to the review
// dialog, not this view.
//
// **No Ember.** There is no human act on this view — reading the register is not a
// decision this interface asks anyone to make — so `assertSingleEmber` allows zero here,
// and nothing on this screen spends the one Ember plane §5's precedence rule permits.
//
// Reads go through `useFetched` (never a hand-rolled effect): `Loading` on any read in
// flight (so switching the header's episode never leaves the last one's register on
// screen under the new heading), `ErrorState` with retry on error, defensive `?? []`
// reads throughout since every list here is open schema.

import { useState } from 'react';
import { useFetched } from '../api/useFetched';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { ClassificationChip } from '../components/ClassificationChip';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { IdChip } from '../components/IdChip';
import { Loading } from '../components/Loading';
import { Num } from '../components/Num';
import { Provenance } from '../components/Provenance';
import { resolveSlot, Slot, slotValue } from '../components/Slot';
import { Sev, type SevKind } from '../components/Sev';
import { ViewHead } from '../components/ViewHead';
import { useFields, type FieldSpec } from '../lib/fields';
import { isWithheldMarker } from '../lib/format';
import type { EvidenceItem, EvidenceRegisterResponse, ScopeFinding } from '../types/api';

/** The two withheld-fields renderings `_withhold_evidence_fields` (`routes/kernel.py`)
 * understands, mirroring the old screen's own toggle: `full` reads every field as
 * stored, `unclassified` asks the server to replace `pointer`/`scopeOfValidity`/
 * `reliabilitySteps`/`reviewStatus` with a `[withheld: <level>]` marker wherever the
 * item's `classification.metadataLevel` is above `U` — the same substitution the
 * signed package applies at that rendering, so this view and the package can never
 * show a different answer to "what does an unclassified reader see here". */
type Rendering = 'full' | 'unclassified';

export const EVIDENCE_FIELDS: FieldSpec[] = [
  { key: 'classification', label: 'classification', default: true },
  { key: 'reliability', label: 'reliability steps', default: true },
  { key: 'cited-by', label: 'cited by', default: true },
  { key: 'scope-findings', label: 'scope findings', default: true },
  { key: 'id', label: 'id', default: false },
];

/** `rule`/`objects`/`message`, joined — content equality, not reference equality:
 * `routes/kernel.py` builds the episode-wide `findings` list and each item's
 * `scopeFindings` from two separate `Finding.to_dict()` calls, so the same finding
 * shows up as two distinct (but equal-content) objects, never the same reference. */
function findingKey(f: ScopeFinding): string {
  return `${f.rule}|${f.message}|${f.objects.join(',')}`;
}

/** Findings that name no single evidence item at all (e.g. `ModelUsePastPurpose`,
 * keyed on a Model id) — everything in `data.findings` that no item's own
 * `scopeFindings` already surfaces, so nothing from the episode's live findings is
 * silently dropped from the view. */
function unattachedFindings(data: EvidenceRegisterResponse): ScopeFinding[] {
  const attached = new Set((data.items ?? []).flatMap((it) => (it.scopeFindings ?? []).map(findingKey)));
  return (data.findings ?? []).filter((f) => !attached.has(findingKey(f)));
}

function sevKindFor(severity: ScopeFinding['severity']): SevKind {
  return severity === 'blocking' ? 'blocking' : severity === 'warning' ? 'warning' : 'info';
}

/** One scope-finding row, shared by the per-item list and the register-level
 * "unattached findings" list so the two can never drift apart. The rule id is mono
 * (`BlockerList.tsx`'s own treatment of a rule id, and the old screen's) — it is a
 * coordinate into the kernel, not a sentence; the message stays prose. [review fix
 * round 1, Minor 8] */
function ScopeFindingRow({ f }: { f: ScopeFinding }) {
  return (
    <li data-scope-finding>
      <Sev kind={sevKindFor(f.severity)}>
        <span className="og-mono text-m2">{f.rule}</span>
      </Sev>{' '}
      <span data-num="label">{f.message}</span>
    </li>
  );
}

/** [T8 spec run-in] `EvidenceCitedBy.reuseJustification` is typed here as
 * `string | null` (`types/api.ts`), but the route that fills it
 * (`routes/kernel.py::_claims_citing_evidence`) passes the citing Claim's own
 * `supportedBy[].reuseJustification` straight through — and on the schema
 * (`objects.yaml`/`types/objects.d.ts`'s `Claim`), that field is
 * `{ authority: string; text: string }`, not a string. Handed to React as a bare
 * child, an object throws ("Objects are not valid as a React child"), which is
 * exactly what crashed the old screen on Demo A's flagship episode (its evidence
 * register has a citing claim whose `reuseJustification` carries this shape).
 * Accept both shapes defensively rather than trust the (currently wrong) type. */
function reuseJustificationText(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === 'string') return value;
  if (typeof value === 'object' && 'text' in (value as Record<string, unknown>)) {
    const text = (value as { text?: unknown }).text;
    return typeof text === 'string' ? text : null;
  }
  return null;
}

function PointerContent({ value }: { value: unknown }) {
  if (isWithheldMarker(value)) return <span className="og-mono text-fg-muted">{value}</span>;
  const p = value as { uri?: string; custodian?: string; hash?: string } | undefined;
  if (!p || typeof p !== 'object') return <span className="text-fg-muted">_[unavailable]_</span>;
  return (
    <div className="flex flex-col gap-0.5">
      {/* A URI is an identifier, the same category ISO dates and object ids already
          are for the numeral walk — never a value to compute with, however many
          digits its path happens to carry. */}
      <span className="og-mono break-all" data-num="label">{p.uri}</span>
      {/* `custodian` is free text too — quoted source content, not a value. */}
      <span className="text-m2 text-fg-muted" data-num="label">custodian: {p.custodian}</span>
      {p.hash && <span className="og-mono text-m2 text-fg-muted">hash {p.hash}</span>}
    </div>
  );
}

function ScopeContent({ value }: { value: unknown }) {
  if (isWithheldMarker(value)) return <span className="og-mono text-fg-muted">{value}</span>;
  const s = value as
    | {
        builtToAnswer?: string;
        questionClass?: string;
        intendedUse?: string;
        conditions?: string[];
        accreditedFor?: string;
        validUntil?: string;
      }
    | undefined;
  if (!s || typeof s !== 'object') return <span className="text-fg-muted">_[unavailable]_</span>;
  return (
    // Every field here is extracted/descriptive text about the evidence's own scope —
    // free prose that can legitimately state a year or a year range, never a value
    // anyone would compute with. Marked on the whole block: every field in this object
    // is the same kind of content.
    <div className="flex flex-col gap-0.5 text-b2" data-num="label">
      <span>{s.builtToAnswer}</span>
      <span className="og-mono text-m2 text-fg-muted">{s.questionClass}</span>
      <span className="text-m2 text-fg-muted">intended use: {s.intendedUse}</span>
      {s.conditions?.length ? <span className="text-m2 text-fg-muted">conditions: {s.conditions.join('; ')}</span> : null}
      {s.accreditedFor && <span className="text-m2 text-fg-muted">accredited for: {s.accreditedFor}</span>}
      {s.validUntil && <span className="og-mono text-m2 text-fg-muted">valid until {s.validUntil}</span>}
    </div>
  );
}

function ReliabilityContent({ value }: { value: unknown }) {
  if (isWithheldMarker(value)) return <span className="og-mono text-fg-muted">{value}</span>;
  const ids = Array.isArray(value) ? (value as string[]) : [];
  if (ids.length === 0) return <span className="text-fg-muted">_[none]_</span>;
  return (
    <ul className="og-mono text-m2 text-fg-muted">
      {ids.map((id) => (
        <li key={id}>{id}</li>
      ))}
    </ul>
  );
}

type VariantFieldKind = 'string' | 'stringArray' | 'integer' | 'ref' | 'refArray' | 'date';

interface VariantFieldSpec {
  path: string;
  label: string;
  kind: VariantFieldKind;
  /** True for the two fields across all nine variants that are not `required` in the
   * schema (`MSStudy.runs`, `SoldierTouchpoint.hsiPlanRef`) — skip the row entirely
   * when unset rather than print a `_[not stated]_` for a field the schema never
   * promised would be there. */
  optional?: boolean;
}

/** Every field each `Evidence.evidenceType` variant defines of its own, in the exact
 * order `src/docket/schema/objects.yaml`'s `Evidence.variants` lists them. `EvidenceRow`
 * resolves every one of these through the same `resolveSlot`/`Slot` pattern the base
 * fields already use, so a marker on any of them renders a `GapCard`/`ExclusionCard`
 * exactly like `pointer` or `scopeOfValidity` would. */
const VARIANT_FIELDS: Record<string, VariantFieldSpec[]> = {
  MSStudy: [
    { path: 'model', label: 'model', kind: 'ref' },
    { path: 'scenarios', label: 'scenarios', kind: 'refArray' },
    { path: 'vvaRecord', label: 'VV&A record', kind: 'ref' },
    { path: 'runs', label: 'runs', kind: 'refArray', optional: true },
  ],
  SoldierTouchpoint: [
    { path: 'n', label: 'n', kind: 'integer' },
    { path: 'selectionRule', label: 'selection rule', kind: 'string' },
    { path: 'unit', label: 'unit', kind: 'string' },
    { path: 'instrument', label: 'instrument', kind: 'stringArray' },
    { path: 'dates', label: 'dates', kind: 'date' },
    { path: 'analysisMethod', label: 'analysis method', kind: 'string' },
    { path: 'hsiPlanRef', label: 'HSI plan ref', kind: 'string', optional: true },
  ],
  VendorFeedback: [
    { path: 'vendors', label: 'vendors', kind: 'stringArray' },
    { path: 'event', label: 'event', kind: 'string' },
  ],
  MarketResearch: [
    { path: 'method', label: 'method', kind: 'string' },
    { path: 'respondents', label: 'respondents', kind: 'string' },
  ],
  ThreatAnalysis: [
    { path: 'threatSet', label: 'threat set', kind: 'string' },
    { path: 'authority', label: 'authority', kind: 'string' },
  ],
  Document: [
    { path: 'publisher', label: 'publisher', kind: 'string' },
    { path: 'published', label: 'published', kind: 'date' },
  ],
  Dataset: [
    { path: 'custodian', label: 'custodian', kind: 'string' },
    { path: 'schemaRef', label: 'schema ref', kind: 'string' },
  ],
  ExpertAssessment: [
    { path: 'experts', label: 'experts', kind: 'stringArray' },
    { path: 'method', label: 'method', kind: 'string' },
  ],
  BudgetExhibit: [
    { path: 'fiscalYear', label: 'fiscal year', kind: 'string' },
    { path: 'programElement', label: 'program element', kind: 'string' },
    { path: 'submitted', label: 'submitted', kind: 'date' },
  ],
};

/** Renders one variant field's *content* value (never called for a gap/exclusion —
 * `Slot` intercepts those before `children` is reached). `n` (`SoldierTouchpoint`'s
 * sample size, the one integer field in this table) is the one value here that must go
 * through the numeral-provenance convention — every other field is a verbatim string,
 * an id, or a list of either. */
function VariantContent({ kind, value, from }: { kind: VariantFieldKind; value: unknown; from: string }) {
  if (isWithheldMarker(value)) return <span className="og-mono text-fg-muted">{value}</span>;
  if (value === undefined || value === null) return <span className="text-fg-muted">_[not stated]_</span>;
  switch (kind) {
    case 'integer':
      return typeof value === 'number' ? (
        <Num value={value} from={from} />
      ) : (
        <span className="text-fg-muted">_[not stated]_</span>
      );
    case 'ref':
      return <span className="og-mono">{String(value)}</span>;
    case 'refArray': {
      const ids = Array.isArray(value) ? (value as string[]) : [];
      if (ids.length === 0) return <span className="text-fg-muted">_[none]_</span>;
      return (
        <ul className="og-mono text-m2 text-fg-muted">
          {ids.map((id) => (
            <li key={id}>{id}</li>
          ))}
        </ul>
      );
    }
    case 'stringArray': {
      const items = Array.isArray(value) ? (value as string[]) : [];
      if (items.length === 0) return <span className="text-fg-muted">_[none]_</span>;
      // Free-text schema fields — quoted source content, not values.
      return (
        <ul className="text-b2" data-num="label">
          {items.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      );
    }
    case 'date':
      // A citation date, at whatever precision the source states — marked here since
      // this span is semantically known to be a date field, not merely "a string that
      // happens to hold digits".
      return <span className="og-mono" data-num="label">{String(value)}</span>;
    default:
      // The `'string'` kind — every one of them a free-text field a source states,
      // not a value: same exemption as `stringArray` above.
      return <span data-num="label">{String(value)}</span>;
  }
}

/** One label-over-value pair inside the register's `<dl>`. Below 768 px the pairs stack
 * and a hairline separates them; at 768 px and up the grid supplies the separation. */
const PAIR_CLASS =
  'flex min-w-0 flex-col gap-0.5 border-b border-hairline pb-2 last:border-b-0 md:border-b-0 md:pb-0';

function EvidenceRow({
  item,
  shown,
  onOpen,
}: {
  item: EvidenceItem;
  shown: Record<string, boolean>;
  onOpen: (id: string) => void;
}) {
  const obj = item.object;
  if (!obj) {
    return (
      <div className="border border-hairline p-4" data-state="unresolved" data-evidence-row>
        <p className="og-mono text-m1 break-all">{item.id}</p>
        <p className="text-b2 text-fg-muted">this id does not resolve in the current graph</p>
      </div>
    );
  }

  const view = { slots: item.slots ?? [], object: obj as unknown as Record<string, unknown> };
  const pointerSlot = resolveSlot(view, 'pointer');
  const scopeSlot = resolveSlot(view, 'scopeOfValidity');
  const reliabilitySlot = resolveSlot(view, 'reliabilitySteps');
  const inclusionSlot = resolveSlot(view, 'inclusionReason');

  const variantFields = VARIANT_FIELDS[obj.evidenceType as string] ?? [];

  // Belt-and-suspenders: every path this row is about to render by name, so any marker
  // the server reports in `item.slots` that isn't one of them still renders somewhere
  // rather than silently vanishing. `reliabilitySteps` is listed here ONLY while its
  // own pair is actually on screen (`shown.reliability`) — Fields hiding that pair
  // must not also hide a `$gap`/`$exclusion` marker recorded on it; unchecking
  // "reliability steps" now makes the marker fall through to `leftoverSlots` instead,
  // which still renders it (under its raw path) rather than nowhere at all. [review
  // fix round 1, Important 1]
  const knownPaths = new Set<string>([
    'pointer',
    'scopeOfValidity',
    ...(shown.reliability ? ['reliabilitySteps'] : []),
    'inclusionReason',
    ...variantFields.map((f) => f.path),
    ...(obj.limitations ?? []).map((_, i) => `limitations/${i}/impact`),
  ]);
  const leftoverSlots = (item.slots ?? []).filter((s) => !knownPaths.has(s.path));

  const withheldFieldPresent =
    isWithheldMarker(obj.pointer) ||
    isWithheldMarker(obj.scopeOfValidity) ||
    isWithheldMarker(obj.reliabilitySteps) ||
    isWithheldMarker(obj.reviewStatus);

  return (
    <div data-evidence-row>
      <Provenance
        authorType={item.authorType ?? 'kernel'}
        confidence={item.confidence}
        locator={item.provenance?.locator}
        actorId={item.authorId}
      >
        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
          <div>
            {/* A verbatim citation title — an identifying label the source itself
                carries, not a value anyone would compute with. */}
            <p className="text-b1" data-num="label">{obj.title}</p>
            <p className="og-mono text-m2 text-fg-muted">{obj.evidenceType}</p>
          </div>
          {shown.classification && (
            <span data-classification>
              <ClassificationChip classification={obj.classification} withheld={withheldFieldPresent} />
            </span>
          )}
        </div>

        <dl
          className="grid gap-x-6 gap-y-3 text-b2"
          style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(22rem, 100%), 1fr))' }}
        >
          {shown.id && (
            <div className={PAIR_CLASS}>
              <dt className="og-label text-b3 text-fg-muted">id</dt>
              <dd className="og-mono" data-num="label">{item.id}</dd>
            </div>
          )}
          <div className={PAIR_CLASS}>
            <dt className="og-label text-b3 text-fg-muted">pointer</dt>
            <dd>
              <Slot slot={pointerSlot}>
                <PointerContent value={slotValue(pointerSlot)} />
              </Slot>
            </dd>
          </div>
          <div className={PAIR_CLASS}>
            <dt className="og-label text-b3 text-fg-muted">scope of validity</dt>
            <dd>
              <Slot slot={scopeSlot}>
                <ScopeContent value={slotValue(scopeSlot)} />
              </Slot>
            </dd>
          </div>
          {shown.reliability && (
            <div className={PAIR_CLASS}>
              <dt className="og-label text-b3 text-fg-muted">reliability steps</dt>
              <dd>
                <Slot slot={reliabilitySlot}>
                  <ReliabilityContent value={slotValue(reliabilitySlot)} />
                </Slot>
              </dd>
            </div>
          )}
          <div className={PAIR_CLASS}>
            <dt className="og-label text-b3 text-fg-muted">inclusion reason</dt>
            <dd>
              <Slot slot={inclusionSlot}>
                {(() => {
                  const v = slotValue(inclusionSlot);
                  if (isWithheldMarker(v)) return <span className="og-mono text-fg-muted">{v}</span>;
                  // Quoted source prose — the same exemption `ScopeContent`'s fields
                  // already get, and for the same reason.
                  return <span data-num="label">{typeof v === 'string' ? v : '_[not stated]_'}</span>;
                })()}
              </Slot>
            </dd>
          </div>
          <div className={PAIR_CLASS}>
            <dt className="og-label text-b3 text-fg-muted">review status</dt>
            <dd className={isWithheldMarker(obj.reviewStatus) ? 'og-mono text-fg-muted' : 'og-mono'}>
              {String(obj.reviewStatus)}
            </dd>
          </div>
          {obj.date && (
            <div className={PAIR_CLASS}>
              <dt className="og-label text-b3 text-fg-muted">date</dt>
              <dd className="og-mono" data-num="label">{obj.date}</dd>
            </div>
          )}
          {variantFields.map((f) => {
            const slot = resolveSlot(view, f.path);
            const value = slotValue(slot);
            // Optional fields that are simply unset are not gaps — the schema never
            // required them — so nothing to show is correct, not a silent drop (a
            // marker on either would still be `slot.kind !== 'content'` and render
            // below regardless of this check).
            if (
              slot.kind === 'content' &&
              f.optional &&
              (value === undefined || (Array.isArray(value) && value.length === 0))
            ) {
              return null;
            }
            return (
              <div key={f.path} className={PAIR_CLASS}>
                <dt className="og-label text-b3 text-fg-muted">{f.label}</dt>
                <dd>
                  <Slot slot={slot}>
                    <VariantContent kind={f.kind} value={value} from={`${item.id}.${f.path}`} />
                  </Slot>
                </dd>
              </div>
            );
          })}
          {leftoverSlots.map((s) => (
            <div key={s.path} className={PAIR_CLASS}>
              {/* The one `dt` on this view that stays mono: a leftover slot is named by
                  its raw schema path, a coordinate into the object, not a written label. */}
              <dt className="og-mono text-m2 text-fg-muted break-all">{s.path}</dt>
              <dd>
                <Slot slot={resolveSlot(view, s.path)} />
              </dd>
            </div>
          ))}
        </dl>

        {(obj.limitations?.length ?? 0) > 0 && (
          <div className="mt-3">
            <p className="og-label text-b3 text-fg-muted">limitations</p>
            <ul className="flex flex-col gap-2 mt-1">
              {obj.limitations!.map((lim, i) => {
                const impactSlot = resolveSlot(view, `limitations/${i}/impact`);
                return (
                  <li key={i} className="text-b2 border-l-2 border-hairline pl-2">
                    <p data-num="label">{lim.statement}</p>
                    <div className="og-mono text-m2 text-fg-muted">
                      <Slot slot={impactSlot}>
                        <span data-num="label">{String(slotValue(impactSlot) ?? '')}</span>
                      </Slot>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {shown['scope-findings'] && (item.scopeFindings?.length ?? 0) > 0 && (
          <div className="mt-3">
            <p className="og-label text-b3 text-fg-muted">scope findings</p>
            <ul className="flex flex-col gap-1 mt-1">
              {item.scopeFindings!.map((f, i) => (
                <ScopeFindingRow key={i} f={f} />
              ))}
            </ul>
          </div>
        )}

        {shown['cited-by'] && (item.citedBy?.length ?? 0) > 0 && (
          <div className="mt-3">
            <p className="og-label text-b3 text-fg-muted">cited by</p>
            <ul className="flex flex-col gap-2 mt-1 text-b2">
              {item.citedBy!.map((c, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2">
                  <IdChip id={c.claim} onOpen={() => onOpen(c.claim)} />
                  {c.assessableAt && (
                    <span className="og-mono text-m2 text-fg-muted">assessable at {c.assessableAt.level}</span>
                  )}
                  {reuseJustificationText(c.reuseJustification) ? (
                    // Free-text rationale — source content, not a value; same
                    // exemption as this file's other extracted-prose fields.
                    <span data-num="label">{reuseJustificationText(c.reuseJustification)}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Provenance>
    </div>
  );
}

export function Evidence() {
  const { sessionId, episodeId } = useSession();
  const { openOverlay } = useWorkspace();
  const fields = useFields('evidence', EVIDENCE_FIELDS);
  const [rendering, setRendering] = useState<Rendering>('full');
  const path = sessionId && episodeId
    ? `/session/${sessionId}/episode/${episodeId}/evidence?rendering=${rendering}`
    : null;
  const fetched = useFetched<EvidenceRegisterResponse>(path);

  if (!sessionId) {
    return <ViewHead eyebrow="evidence" title="Evidence" sentence="Choose a decision in the header first." />;
  }

  const data = fetched.data;
  // Hoisted rather than called twice per render (once to decide whether the section
  // renders at all, once to render its rows) — the same list either way, since
  // nothing between the two reads can change it. [review fix round 1, Minor 4]
  const unattached = data ? unattachedFindings(data) : [];

  return (
    <div>
      <ViewHead
        eyebrow={`evidence · ${episodeId}`}
        title="Evidence"
        sentence="Every item the record cites, with where it came from, what it is valid for, and what is missing — a blank cell is the one thing this view may never show."
        right={
          <>
            {/* The rendering toggle every other option-bearing screen keeps reachable
                (controller ruling, review fix round 1 Important 2): `unclassified`
                asks the server to withhold `pointer`/`scopeOfValidity`/
                `reliabilitySteps`/`reviewStatus` behind a `[withheld: <level>]`
                marker wherever an item's metadata is classified above `U`, and
                `ClassificationChip` lights its own withheld glyph for that item — the
                same substitution the signed package applies at that rendering, so
                this view can never claim a different answer. Bordered, never Ember
                (§5): choosing a rendering is not this view's human act. */}
            <div className="flex border border-hairline-strong" role="group" aria-label="rendering">
              {(['full', 'unclassified'] as Rendering[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRendering(r)}
                  aria-pressed={rendering === r}
                  className={`og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center px-3 ${rendering === r ? 'text-fg bg-canvas' : 'text-fg-muted'}`}
                >
                  {r}
                </button>
              ))}
            </div>
            <FieldsControl list="evidence" spec={EVIDENCE_FIELDS} shownOverride={fields} />
          </>
        }
      />

      {!episodeId && <EmptyState eyebrow="Evidence" message="No episode exists in this session yet." />}

      {/* On ANY read in flight, not only the first: switching the decision in the
          header must never leave the last episode's register on screen under the new
          heading. */}
      {episodeId && fetched.loading && <Loading label="loading register" />}
      {episodeId && fetched.error && (
        <ErrorState
          message={fetched.error.message}
          route={`session/${sessionId}/episode/${episodeId}/evidence`}
          onRetry={fetched.refresh}
        />
      )}

      {/* Gated on the same `scope-findings` field the per-item list is: Fields hiding
          scope findings must hide all of them, not only the ones attached to an item.
          [review fix round 1, Minor 3] */}
      {episodeId && fields.shown['scope-findings'] && !fetched.loading && !fetched.error && data && unattached.length > 0 && (
        <section className="mb-6 flex flex-col gap-2">
          <h2 className="og-display text-e2">What the register itself says</h2>
          <ul className="flex flex-col gap-1">
            {unattached.map((f, i) => (
              <ScopeFindingRow key={i} f={f} />
            ))}
          </ul>
        </section>
      )}

      {episodeId && !fetched.loading && !fetched.error && data && (data.items ?? []).length === 0 && (
        <EmptyState eyebrow="Evidence" message="No evidence in this episode's register." />
      )}

      {episodeId && !fetched.loading && !fetched.error && data && (data.items ?? []).length > 0 && (
        <div className="flex flex-col gap-4">
          {(data.items ?? []).map((item) => (
            <EvidenceRow
              key={item.id}
              item={item}
              shown={fields.shown}
              onOpen={(id) => openOverlay({ kind: 'raw', id })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
