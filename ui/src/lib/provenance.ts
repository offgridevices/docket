// The three provenance marks (design spec §5, plan Task 5 Step 4). Every object the UI
// renders was written by exactly one kind of actor — agent, human or kernel — and that
// single field is the whole basis of the mark. There is no second signal to consult and
// no arithmetic: `markOf` is a pure lookup.

export type AuthorType = 'agent' | 'human' | 'kernel';
export type Mark = 'agent-proposed' | 'human-accepted' | 'kernel-computed';

const MARK_OF_AUTHOR_TYPE: Record<AuthorType, Mark> = {
  agent: 'agent-proposed',
  human: 'human-accepted',
  kernel: 'kernel-computed',
};

/** `v.authorType` is lifted server-side from `object.createdBy.actorType`
 * (see `serialize.object_view`) so the browser never digs into an envelope
 * to find it. The parameter is typed to the exact three-value union (not `string`)
 * so a caller that already has a typed value gets a compile error instead of only a
 * runtime one; the runtime check stays as the defense-in-depth line for a value that
 * arrived as unparsed JSON (an SSE payload, `JSON.parse`'d API response, etc.), which
 * TypeScript cannot verify no matter how this parameter is typed. */
export function markOf(v: { authorType: AuthorType }): Mark {
  const mark = MARK_OF_AUTHOR_TYPE[v.authorType];
  if (!mark) {
    throw new Error(`unknown authorType ${JSON.stringify(v.authorType)}`);
  }
  return mark;
}
