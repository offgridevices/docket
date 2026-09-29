// The only component allowed to print a digit that came from the API (plan Task 5 Step
// 4; "Honesty and safety in the UI" #1 and #2). `value` is a string or number received
// from the API and never transformed here — no `toFixed`, no unit conversion, no
// percentage arithmetic. If a value needs rounding, the kernel already rounded it
// (`canon.round6`) and the API sent what the kernel stored.
//
// `valueText` (plan 07 Task 7 fix round, I2): the API's own `str()` form of `value`
// (`docket.api.serialize.object_view`'s `valueText` map, `agent.dispatch.read_back`'s
// per-result `valueText`, or the readiness view's `simplexRobustnessText`), preferred
// over `String(value)` when present — `JSON.parse("36.0")` is the JS number `36`, and
// `String(36)` is `"36"`, silently disagreeing with the `36.0` the rendered package
// prints for the exact same object. `String(value)` stays the fallback for the numerals
// no route has been given a text form for yet (never a hard requirement, since a
// reader who wants byte-fidelity can still open the object or the package).
//
// `run` (a per-numeral seed/hash/kernel-version stamp) is deliberately not a prop here
// any more (plan 07 Task 7 fix round, M11): repeating it under every `<Num>` on a
// screen with dozens of them buried the one fact that mattered under noise. A screen
// with more than one kernel-authored numeral prints that stamp once, as its own panel
// footer line (see `Compute.tsx`) — not attached to each value individually.

// `className` (the frame task): the two header counters are the one place §10 lets a
// numeral carry state colour, and the colour has to sit on THIS element — a colour class
// on a wrapper would leave the numeral itself uncoloured for anything reading the class.
// Appended to the mono face, never replacing it.
export interface NumProps {
  value: number | string;
  from: string;
  units?: string;
  valueText?: string;
  className?: string;
}

export function Num({ value, from, units, valueText, className }: NumProps) {
  return (
    <span className={className ? `font-mono ${className}` : 'font-mono'} data-num data-from={from}>
      <span aria-hidden>[</span>&nbsp;{valueText ?? String(value)}
      {units ? ` ${units}` : ''}&nbsp;<span aria-hidden>]</span>
    </span>
  );
}
