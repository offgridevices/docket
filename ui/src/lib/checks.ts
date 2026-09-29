// Plain language for every gate check `kernel.lifecycle.CHECKS` can name (spec §11).
// The record's own name stays beside it under Explain; the remedy is the act that
// would satisfy it, routed to where that act lives.
//
// This table is the plain LABEL only. The sentence a reader is shown for what would
// satisfy a check is the check's own docstring line, served on the sheet as
// `whatWouldSatisfy` (`kernel.queue.what_would_satisfy`) and printed verbatim — so the
// remedy text can never drift from the predicate that will actually refuse.
export const CHECK_PLAIN: Record<string, string> = {
  'charter-three-fields': 'the charter holds all three of its fields',
  'charter-human-accepted': 'a person has put their name on the charter',
  'no-blocking-structural': 'nothing structural is broken in what this decision reaches',
  'gaps-confirmed': 'every recorded absence has been confirmed by a person',
  'linchpins-human': 'no assumption the answer depends on is still unread',
  'plan-present': 'a plan has been proposed',
  'plan-approved-by-human': 'a person approved the plan',
  'plan-steps-have-authority': 'every step cites the doctrine paragraph that requires it',
  'policy-method-matches': 'every step uses the method the policy chose',
  'every-step-has-run': 'every planned step has a sealed calculation behind it',
  'readiness-present': 'the record has been scored against the standard',
  'commitment-present': 'the decision names an option, conditions and stop rules',
  'readiness-ready': 'nothing stops sign-off',
  'commitment-package-hash': 'the signature binds to the package as rendered',
  'store-integrity': "the store's log chain and authorship lines hold",
  'human-actor': 'a person, not the AI, is acting',
  'kernel-actor': 'the kernel, not a person, draws this conclusion',
};

export function checkPlain(name: string): string {
  return CHECK_PLAIN[name] ?? name.replace(/-/g, ' ');
}

export interface Remedy { label: string; route: string }

export function remedyFor(name: string, ctx: { charterId: string | null; firstGap: string | null; firstLinchpin: string | null }): Remedy | null {
  switch (name) {
    case 'charter-three-fields': return { label: 'Write the missing charter field', route: '/model#charter' };
    case 'charter-human-accepted': return ctx.charterId ? { label: 'Read and accept the charter', route: `/review/${ctx.charterId}` } : null;
    case 'gaps-confirmed': return ctx.firstGap ? { label: 'Confirm the recorded absence', route: `/review/${ctx.firstGap}` } : null;
    case 'linchpins-human': return ctx.firstLinchpin ? { label: 'Read the assumption the answer depends on', route: `/review/${ctx.firstLinchpin}` } : null;
    case 'no-blocking-structural': return { label: 'Open the readiness findings', route: '/readiness' };
    case 'plan-present': return { label: 'Ask the AI to propose a plan', route: '/plan#propose' };
    case 'plan-approved-by-human': return { label: 'Read and approve the plan', route: '/plan#approve' };
    case 'plan-steps-have-authority': case 'policy-method-matches': return { label: 'Read the plan', route: '/plan' };
    case 'every-step-has-run': return { label: 'Send it to be computed', route: '/compute' };
    case 'readiness-present': case 'readiness-ready': return { label: 'Open readiness', route: '/readiness' };
    case 'commitment-present': case 'commitment-package-hash': return { label: 'Fill in the commitment block', route: '/package#commit' };
    default: return null;
  }
}
