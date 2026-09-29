// Bottom-left, above the footer (R8/R25); green border for a completed act, red for a
// refusal.
import { useWorkspace } from '../api/useWorkspace';

export function Toasts() {
  const { toasts } = useWorkspace();
  if (toasts.length === 0) return null;
  return (
    <div className="fixed left-[clamp(14px,2.2vw,30px)] z-[100] flex flex-col gap-2" style={{ bottom: 'calc(var(--foot-h, 44px) + 16px)' }} aria-live="polite">
      {toasts.map((t) => (
        // `data-num="label"` is the same carve-out the demo cards take: a toast names the
        // decision it just opened, and "Demo A · CBO GCV 2013" carries the years the demo
        // covers inside a name — not a value read out of the record.
        <div key={t.id} data-toast={t.tone} data-num="label"
          className={`max-w-[min(520px,calc(100vw-2rem))] border border-fg bg-raised px-4 py-3 text-b3 ${t.tone === 'done' ? 'border-l-[3px] border-l-done' : t.tone === 'stop' ? 'border-l-[3px] border-l-stop' : ''}`}>
          {t.text}
        </div>
      ))}
    </div>
  );
}
