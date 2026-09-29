import { term, type TermKey } from '../lib/glossary';
import { useWorkspace } from '../api/useWorkspace';

/** A plain label with the record's term on hover, and beside it in mono under Explain. */
export function Term({ k, plain }: { k: TermKey; plain?: string }) {
  const { explain } = useWorkspace();
  const t = term(k);
  return (
    <span title={`${t.record} — ${t.explain}`} data-term={k}>
      <span className="border-b border-dashed border-hairline-strong">{plain ?? t.plain}</span>
      {explain && <span className="og-mono text-m2 text-fg-muted"> {t.record}</span>}
    </span>
  );
}
