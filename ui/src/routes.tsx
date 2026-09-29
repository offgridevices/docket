// The view table (spec §5): the map, Browse the record and the router all read it.
import type { ComponentType } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Cpu, Database, FileText, Gauge, GitBranch, History, Inbox, Layers, ListChecks, MessageSquare, TriangleAlert } from 'lucide-react';
import { Route, Routes } from 'react-router-dom';
import { AskRedirect } from './frame/AskRedirect';
import { Activity } from './views/Activity';
import { Compute } from './views/Compute';
import { Evidence } from './views/Evidence';
import { Model } from './views/Model';
import { Needs } from './views/Needs';
import { Package } from './views/Package';
import { Plan } from './views/Plan';
import { Readiness } from './views/Readiness';
import { Request } from './views/Request';
import { Review } from './views/Review';
import { Timeline } from './views/Timeline';

export type ViewKey =
  | 'needs' | 'request' | 'model' | 'review' | 'plan' | 'compute'
  | 'readiness' | 'package' | 'evidence' | 'timeline' | 'activity';

export interface ViewDef {
  key: ViewKey;
  path: string;
  label: string;
  /** The record's own term, shown under Explain. */
  record: string;
  group: 'home' | 'stage' | 'register' | 'other';
  icon: LucideIcon;
}

export const VIEWS: ViewDef[] = [
  { key: 'needs', path: '/', label: 'What needs you', record: 'pending human acts', group: 'home', icon: TriangleAlert },
  { key: 'request', path: '/request', label: 'Request', record: 'intake · elicitation', group: 'stage', icon: Inbox },
  { key: 'model', path: '/model', label: 'Model', record: 'G1 · MODEL_APPROVED', group: 'stage', icon: Layers },
  { key: 'plan', path: '/plan', label: 'Plan', record: 'G2 · PLAN_APPROVED', group: 'stage', icon: ListChecks },
  { key: 'compute', path: '/compute', label: 'Compute', record: 'EVALUATED', group: 'stage', icon: Cpu },
  { key: 'readiness', path: '/readiness', label: 'Readiness', record: 'PENDING_SIGNATURE', group: 'stage', icon: Gauge },
  { key: 'package', path: '/package', label: 'Package', record: 'G3 · SIGNED', group: 'stage', icon: FileText },
  { key: 'evidence', path: '/evidence', label: 'Evidence', record: 'evidence register', group: 'register', icon: Database },
  { key: 'timeline', path: '/timeline', label: 'Timeline', record: 'programme episodes', group: 'register', icon: GitBranch },
  { key: 'activity', path: '/activity', label: 'Activity', record: 'append-only log', group: 'register', icon: History },
  { key: 'review', path: '/review', label: 'Review, one thing at a time', record: 'the review card', group: 'other', icon: MessageSquare },
];

export const STAGE_KEYS = ['request', 'model', 'plan', 'compute', 'readiness', 'package'] as const;

/** Retargeted one view per task (Tasks 8–18); every view is now its own screen. */
export const VIEW_COMPONENTS: Record<ViewKey, ComponentType> = {
  needs: Needs, request: Request, model: Model, review: Review, plan: Plan, compute: Compute,
  readiness: Readiness, package: Package, evidence: Evidence, timeline: Timeline, activity: Activity,
};

export function AppRoutes() {
  return (
    <Routes>
      {VIEWS.map((v) => {
        const View = VIEW_COMPONENTS[v.key];
        return <Route key={v.key} path={v.path} element={<View />} />;
      })}
      {/* One object, opened from a card, a remedy on the gate ladder or a pasted
          link — the same view as the queue, reading the id off the address. */}
      <Route path="/review/:objectId" element={<Review />} />
      {/* Not a view: the address a chat answer's chip carries. It asks the question and
          leaves the reader on Home. */}
      <Route path="/ask" element={<AskRedirect />} />
    </Routes>
  );
}
