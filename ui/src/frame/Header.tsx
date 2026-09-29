import { HelpCircle, MessageSquare, Settings as SettingsIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
// Docket product mark (not the OffGrid beacon — that stays in Footer.tsx's wordmark).
import docketMark from '../brand/logo/docket/docket-mark-ember.svg';
import { useWorkspace } from '../api/useWorkspace';
import { ICON_PROPS } from '../lib/icons';
import type { EpisodeView } from '../types/api';
import { BrowseMenu } from './BrowseMenu';
import { DecisionSwitcher } from './DecisionSwitcher';
import { EpisodeChip } from './EpisodeChip';

const ICON_BTN = 'inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 px-2 og-label text-b3 border border-transparent hover:border-hairline-strong';

export function Header({ episode }: { episode: EpisodeView | null }) {
  const { explain, setExplain, chatCollapsed, setChatCollapsed, chatSheet, setChatSheet, openOverlay } = useWorkspace();
  return (
    <div className="flex flex-wrap items-center gap-2 px-[clamp(14px,2.2vw,30px)] py-1.5">
      <Link to="/" className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2">
        {/* The mark is NOT `hide-below-520`: below that width the word is off and the
            mark is the only thing left saying whose app this is. */}
        <img src={docketMark} alt="" width={24} height={24} className="block shrink-0" />
        <span className="og-display text-b1 hide-below-520">Docket</span>
      </Link>
      <DecisionSwitcher />
      <span className="hide-below-768"><EpisodeChip episode={episode} /></span>
      <span className="flex-1" />
      {/* `aria-label` rather than the visible word alone: the name has to be the same
          at every width, and below 1024 the word itself is off to make room. */}
      <button type="button" onClick={() => setExplain(!explain)} aria-pressed={explain} aria-label="Explain"
        className={`${ICON_BTN} hide-below-520 ${explain ? 'border-fg' : ''}`} title="Show the record's own term beside every label">
        <HelpCircle {...ICON_PROPS} size={20} aria-hidden /><span className="hide-below-1280">Explain</span>
      </button>
      <BrowseMenu />
      <button type="button" aria-label="Ask about this decision" title="Ask about this decision" className={ICON_BTN}
        onClick={() => {
          // Below 1024 the chat is a bottom sheet. A sheet that opened still collapsed
          // would slide up empty — the collapsed rail is `hide-below-1024` — so opening
          // it from the header also un-collapses it.
          if (window.innerWidth >= 1024) setChatCollapsed(!chatCollapsed);
          else { setChatSheet(!chatSheet); setChatCollapsed(false); }
        }}>
        <MessageSquare {...ICON_PROPS} size={20} aria-hidden />
      </button>
      <button type="button" aria-label="open settings" title="Settings" className={ICON_BTN} onClick={() => openOverlay({ kind: 'settings' })}>
        <SettingsIcon {...ICON_PROPS} size={20} aria-hidden />
      </button>
    </div>
  );
}
