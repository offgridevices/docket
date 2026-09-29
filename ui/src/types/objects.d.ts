/* GENERATED from src/docket/schema/json — do not edit. Run `npm run gen:types`.
   One interface per committed JSON Schema (39 object shapes) so the UI cannot
   silently drift from what the kernel and agent actually write. Local `$defs`
   (actor, provenance, exclusionRef, gapRef, id, timestamp, ...) are inlined per
   file rather than hoisted to shared names — see ui/scripts/gen-types.mjs. */

export interface Action {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  description: string;
  dueDate?: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  owner: string;
  rev: number;
  status: 'open' | 'done';
  supersedes?: string;
  type: 'Action';
  verification?: string;
}

export interface Alternative {
  baselineFlag: boolean;
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  description: string;
  enteredOrder?: number;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  name: string;
  optionSet?: string;
  parameters?: {
    [k: string]: unknown;
  };
  rev: number;
  status: 'candidate' | 'screened-out' | 'evaluated' | 'selected' | 'rejected';
  statusReason?: string;
  supersedes?: string;
  type: 'Alternative';
}

/**
 * ICD 203 §D.6.e(3) fields; linchpin + gap is the Poland-bridges object.
 */
export interface Assumption {
  confidence?: 'explicit' | 'inferred' | 'absent';
  conflictsWith?: string[];
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  evidence:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  id: string;
  implicationsIfWrong:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  indicatorsThatWouldAlter:
    | string[]
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  linchpin: boolean;
  parameterBinding?: {
    kind: 'weight' | 'observation';
    target: string;
  };
  rationale:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  rev: number;
  sensitivityResult?: string;
  statement: string;
  supersedes?: string;
  type: 'Assumption';
  variedInSensitivity: boolean;
}

export interface BiasCheck {
  checkType:
    | 'anchoring-control'
    | 'independent-disconfirming-review'
    | 'premortem'
    | 'outside-view'
    | 'structured-alternative-comparison'
    | 'devils-advocate';
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  performedAt?: string;
  performedBy?: string;
  producedEvidence:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  requiredBy: string;
  rev: number;
  status: 'required' | 'performed' | 'waived';
  supersedes?: string;
  type: 'BiasCheck';
  waiver?: string;
}

/**
 * AR 5-11 ¶4-5b problem statement plus scope and authority (design §6.1).
 */
export interface Charter {
  authority: {
    board?: string;
    delegations?: string[];
    signer: string;
  };
  conditionsOfInterest?: string[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  consequencesOfErroneousOutput:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  decisionClassPolicy: string;
  decisionToBeMade:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  definitions?: {
    term: string;
    text:
      | string
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
  }[];
  hierarchyBinding?: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  limitations?: {
    mitigation:
      | string
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
    statement: string;
  }[];
  mandateElements?: string[];
  neededBy?: string;
  question:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  questionClass:
    | 'desired-characteristics'
    | 'force-structure'
    | 'operational-concept'
    | 'combat-effectiveness'
    | 'cost'
    | 'schedule'
    | 'industrial-base'
    | 'requirements-tradeoff'
    | 'capability-gap'
    | 'other';
  rev: number;
  scope: {
    excluded: string[];
    included: string[];
  };
  successCriteria?: string[];
  supersedes?: string;
  type: 'Charter';
}

/**
 * A statement the package asserts. Assessable at level L if supporting evidence metadata is visible at L.
 */
export interface Claim {
  addresses?: string[];
  assessableAt: {
    level: 'U' | 'CUI' | 'C' | 'S' | 'TS';
  };
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  derivedFrom?: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  mandateElements?: string[];
  questionClass:
    | 'desired-characteristics'
    | 'force-structure'
    | 'operational-concept'
    | 'combat-effectiveness'
    | 'cost'
    | 'schedule'
    | 'industrial-base'
    | 'requirements-tradeoff'
    | 'capability-gap'
    | 'other';
  resultRef?: string;
  rev: number;
  section?: string;
  supersedes?: string;
  supportedBy:
    | {
        evidence: string;
        reuseJustification?: {
          authority: string;
          text: string;
        };
      }[]
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  text: string;
  type: 'Claim';
}

export interface Commitment {
  conditions: {
    dueDate: string;
    text: string;
    verifyBy: string;
  }[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  dissent?: {
    text: string;
    who: string;
  }[];
  episode: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  packageHash: string;
  rev: number;
  selected: string;
  signedAt: string;
  signer: {
    identity: string;
    role: string;
  };
  stopRules: string[];
  supersedes?: string;
  type: 'Commitment';
}

export interface Constraint {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  implications:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kind: 'physical' | 'programmatic' | 'policy';
  rev: number;
  source:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  statement: string;
  supersedes?: string;
  type: 'Constraint';
}

export interface DataReliabilityStep {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  date?: string;
  description: string;
  documentation:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  method:
    'source-review' | 'tracing' | 'electronic-testing' | 'corroboration' | 'interview' | 'expert-review' | 'other';
  performedBy: string;
  rev: number;
  supersedes?: string;
  type: 'DataReliabilityStep';
}

export interface DecisionEpisode {
  alternatives: string[];
  asOf: string;
  assumptions: string[];
  biasChecks: string[];
  charter: string;
  claims: string[];
  commitment?: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  constraints: string[];
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  distribution?: {
    date: string;
    to: string;
  }[];
  evidenceRegister: string[];
  flipAnalyses: string[];
  groundRules: string[];
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  lifecycleState:
    | 'DRAFT'
    | 'MODEL_APPROVED'
    | 'PLAN_APPROVED'
    | 'EVALUATED'
    | 'PENDING_SIGNATURE'
    | 'SIGNED'
    | 'SUSPECT'
    | 'SUPERSEDED'
    | 'VOID';
  mandateElements: string[];
  models: string[];
  narratives: string[];
  objectives: string[];
  observations: string[];
  plan?: string;
  program?: string;
  readiness?: string;
  refreshedBecause?: string;
  replacements?: {
    [k: string]: string;
  };
  rev: number;
  risks: string[];
  runs: string[];
  scenarios: string[];
  sequence: number;
  supersedes?: string;
  transitions: {
    actor: {
      actorId: string;
      actorType: 'human' | 'agent' | 'kernel';
    };
    at: string;
    checksSatisfied: string[];
    checksUnsatisfied: string[];
    from: string;
    policyVersion: string;
    refused: boolean;
    to: string;
  }[];
  type: 'DecisionEpisode';
  weightSets: string[];
}

export interface DecisionPackage {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  episode: string;
  graphSnapshotHash: string;
  hash: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kernelVersion: string;
  path?: string;
  renderedAt: string;
  rendering: 'unclassified' | 'full';
  rev: number;
  supersedes?: string;
  type: 'DecisionPackage';
}

export interface DecisionProgram {
  charter: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  diffs: string[];
  episodes: string[];
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  name: string;
  refreshTriggers: string[];
  rev: number;
  supersedes?: string;
  type: 'DecisionProgram';
}

export interface EpisodeDiff {
  added: string[];
  because: string;
  changed: {
    after: string;
    before: string;
    field: string;
    object: string;
  }[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  from: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  judgmentsChanged: {
    [k: string]: unknown;
  }[];
  judgmentsConsistent: string[];
  kernelVersion: string;
  pairing: string;
  rankingAfter: string[];
  rankingBefore: string[];
  ratingsChanged: {
    [k: string]: unknown;
  }[];
  removed: string[];
  rev: number;
  supersedes?: string;
  to: string;
  type: 'EpisodeDiff';
}

/**
 * Immutable, sealed, kernel-only.
 */
export interface EvaluationRun {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  evaluator: string;
  evaluatorVersion: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  inputsHash: string;
  kernelVersion: string;
  method: string;
  outputHashes: string[];
  outputs: string[];
  parameterBindings: {
    [k: string]: unknown;
  };
  plan: string;
  ranking: string[];
  rev: number;
  runRecordHash: string;
  sealedAt: string;
  sealedBy: 'kernel';
  seed: number;
  step: string;
  supersedes?: string;
  type: 'EvaluationRun';
}

/**
 * The load-bearing object. Pointer, classification and scope are separable from any Claim.
 */
export type Evidence = {
  analysisMethod?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  assertions?: {
    field: string;
    locator: string;
    subject: string;
    value: string | number;
  }[];
  authority?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  classification: {
    caveats?: string[];
    controlledBy?: string;
    level: 'U' | 'CUI' | 'C' | 'S' | 'TS';
    metadataLevel: 'U' | 'CUI' | 'C' | 'S' | 'TS';
  };
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  custodian?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  date?: string;
  dates?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  event?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  evidenceType:
    | 'MSStudy'
    | 'SoldierTouchpoint'
    | 'VendorFeedback'
    | 'MarketResearch'
    | 'ThreatAnalysis'
    | 'Document'
    | 'Dataset'
    | 'ExpertAssessment'
    | 'BudgetExhibit';
  experts?:
    | string[]
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  fiscalYear?: string;
  hsiPlanRef?: string;
  id: string;
  inclusionReason?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  instrument?:
    | string[]
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  limitations?: {
    impact:
      | string
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
    statement: string;
  }[];
  method?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  model?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  n?:
    | number
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  pointer:
    | {
        custodian: string;
        hash?: string;
        uri: string;
      }
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  programElement?: string;
  published?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  publisher?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  reliabilitySteps:
    | string[]
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  respondents?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  rev: number;
  reviewStatus: 'draft' | 'reviewed' | 'rejected';
  reviewers?: {
    date: string;
    name: string;
    role: string;
  }[];
  runs?: string[];
  scenarios?:
    | string[]
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  schemaRef?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  scopeOfValidity:
    | {
        accreditedFor?: string;
        builtToAnswer: string;
        conditions?: string[];
        intendedUse: string;
        questionClass:
          | 'desired-characteristics'
          | 'force-structure'
          | 'operational-concept'
          | 'combat-effectiveness'
          | 'cost'
          | 'schedule'
          | 'industrial-base'
          | 'requirements-tradeoff'
          | 'capability-gap'
          | 'other';
        validUntil?: string;
      }
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  selectionRule?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  submitted?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  supersedes?: string;
  threatSet?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  title: string;
  type: 'Evidence';
  unit?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  vendors?:
    | string[]
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  vvaRecord?:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
};

/**
 * First-class omission. time-or-resource is PROHIBITED by default policy (OAS AoA Handbook §4.7).
 */
export interface Exclusion {
  authority: {
    date: string;
    role: string;
    who: string;
  };
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  evidence?: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  reason: string;
  reasonType:
    | 'infeasible'
    | 'dominated'
    | 'out-of-scope'
    | 'security-withheld'
    | 'data-unavailable'
    | 'superseded'
    | 'time-or-resource'
    | 'not-applicable'
    | 'assessed-differently'
    | 'other';
  retainedInStructure: true;
  rev: number;
  supersedes?: string;
  target: {
    id?: string;
    kind: 'Alternative' | 'Evidence' | 'Study' | 'Section' | 'Question' | 'Measure' | 'Category' | 'Scenario';
    label: string;
  };
  type: 'Exclusion';
}

export interface FlipAnalysis {
  assumption?: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  currentValue: number;
  direction: 'up' | 'down' | 'none';
  flipDistance: number | null;
  flipThreshold: number | null;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kernelVersion: string;
  parameter: {
    kind: 'weight' | 'observation' | 'assumption';
    label: string;
    target: string;
  };
  range: {
    hi: number;
    lo: number;
    source: 'uncertainty' | 'sweep' | 'default';
  };
  rankingAfter: string[] | null;
  rankingBefore: string[];
  rev: number;
  run: string;
  supersedes?: string;
  type: 'FlipAnalysis';
}

export interface GroundRule {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  rev: number;
  source:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  statement: string;
  supersedes?: string;
  type: 'GroundRule';
}

/**
 * First-class gap. Required fields make recording a gap more work-complete than inventing a value (PhantomFill).
 */
export interface InsufficientEvidence {
  confidence?: 'explicit' | 'inferred' | 'absent';
  confirmedBy?: {
    actorId: string;
    date: string;
  };
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  impact: 'blocking' | 'degrading' | 'informational';
  indicatorsThatWouldResolve: string[];
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  rev: number;
  sought: string;
  supersedes?: string;
  type: 'InsufficientEvidence';
  /**
   * @minItems 1
   */
  whereLookedFor: [string, ...string[]];
  whyNotFound: string;
}

/**
 * One thing the tasking authority required the record to contain.
 */
export interface MandateElement {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  rev: number;
  satisfiedBy?: string[];
  source: string;
  status: 'satisfied' | 'partial' | 'unsatisfied' | 'not-applicable';
  statusReason?: string;
  supersedes?: string;
  text: string;
  type: 'MandateElement';
}

export interface MandateScorecard {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  episode: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kernelVersion: string;
  rev: number;
  rows: {
    element: string;
    satisfiedBy: string[];
    status: string;
  }[];
  supersedes?: string;
  type: 'MandateScorecard';
}

/**
 * One row of the OAS AoA Handbook Table 5-2 Measures Framework.
 */
export interface Measure {
  analysisMethod?: string;
  attribute: string;
  conditions?: string[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  criteria:
    | {
        objective?: number;
        threshold?: number;
      }
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  measure: string;
  metric: {
    aggregation?: 'mean' | 'sum' | 'min' | 'max';
    direction: 'max' | 'min';
    units: string;
  };
  objective: string;
  rev: number;
  supersedes?: string;
  task: string;
  type: 'Measure';
  valueFunction?: {
    hi?: number;
    kind: 'identity' | 'linear' | 'binary' | 'step';
    lo?: number;
    threshold?: number;
  };
}

export interface Model {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  definition: {
    containerDigest?: string;
    kind: 'code' | 'lookup' | 'rpc' | 'rubric' | 'simulation';
    version: string;
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  inputs?: string[];
  intendedUse: string;
  limitations?: {
    justification:
      | string
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
    statement: string;
  }[];
  name: string;
  outputs?: string[];
  qualificationStatus: 'draft' | 'validated' | 'qualified';
  questionClass:
    | 'desired-characteristics'
    | 'force-structure'
    | 'operational-concept'
    | 'combat-effectiveness'
    | 'cost'
    | 'schedule'
    | 'industrial-base'
    | 'requirements-tradeoff'
    | 'capability-gap'
    | 'other';
  rev: number;
  supersedes?: string;
  type: 'Model';
  validityRegions?: {
    [k: string]: unknown;
  };
  vvaRecord:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
}

/**
 * Agent-drafted prose for one package section. Every sentence cites object ids; the renderer enforces it.
 */
export interface Narrative {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  episode: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  rev: number;
  section:
    | 'cover'
    | 'problem-statement'
    | 'mandate-elements'
    | 'objectives-and-measures'
    | 'alternatives'
    | 'grca'
    | 'evidence-register'
    | 'evaluation-results'
    | 'what-flips'
    | 'bias-checks'
    | 'readiness'
    | 'risks'
    | 'refresh-log'
    | 'commitment'
    | 'traceability'
    | 'machine-annex';
  sentences: {
    /**
     * @minItems 1
     */
    cites: [string, ...string[]];
    text: string;
  }[];
  supersedes?: string;
  type: 'Narrative';
}

/**
 * Hierarchical value model node.
 */
export interface Objective {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  description?: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  measures?: string[];
  name: string;
  parent?: string;
  priority: 'primary' | 'secondary';
  priorityRank?: number;
  provenance:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  rev: number;
  supersedes?: string;
  type: 'Objective';
}

/**
 * Alternative × Measure datum, evidence-backed. Kernel input, never kernel output.
 */
export interface Observation {
  alternative: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  evidence:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  measure: string;
  rev: number;
  supersedes?: string;
  type: 'Observation';
  uncertainty?: string;
  value:
    | number
    | {
        hi: number;
        lo: number;
      };
  variedInSensitivity?: boolean;
}

export interface OptionSet {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  members: string[];
  name: string;
  narrowingEvents?: {
    date: string;
    reason: string;
    removed: string[];
  }[];
  rev: number;
  supersedes?: string;
  type: 'OptionSet';
}

/**
 * The evaluation workflow the agent proposes and a human approves (G2).
 */
export interface Plan {
  approvedBy?: {
    actorId: string;
    date: string;
  };
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  deviations?: {
    reason: string;
    step: string;
  }[];
  episode: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  policyBasis: string;
  rev: number;
  /**
   * @minItems 1
   */
  steps: [
    {
      alternatives: string[];
      authority: {
        document: string;
        paragraph: string;
      };
      biasChecks?: string[];
      evaluator: string;
      id: string;
      measures: string[];
      method: 'mavt' | 'ahp' | 'topsis' | 'pugh';
      sensitivitySweeps?: {
        kind: 'weight' | 'observation';
        range?: {
          hi: number;
          lo: number;
        };
        target: string;
      }[];
      weightSet: string;
    },
    ...{
      alternatives: string[];
      authority: {
        document: string;
        paragraph: string;
      };
      biasChecks?: string[];
      evaluator: string;
      id: string;
      measures: string[];
      method: 'mavt' | 'ahp' | 'topsis' | 'pugh';
      sensitivitySweeps?: {
        kind: 'weight' | 'observation';
        range?: {
          hi: number;
          lo: number;
        };
        target: string;
      }[];
      weightSet: string;
    }[]
  ];
  supersedes?: string;
  type: 'Plan';
}

/**
 * Decision-class policy: readiness rules, tailoring, aggregation, blocking rules. Versioned.
 */
export interface Policy {
  aggregationK: number;
  blockingRules: string[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  decisionClass: string;
  expectedDaysByState?: {
    [k: string]: number;
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  method: 'mavt' | 'ahp' | 'topsis' | 'pugh';
  nSimplex: number;
  name: string;
  prohibitedExclusionReasons: string[];
  requireAllLinchpinsVaried: boolean;
  requiredBiasChecks: string[];
  rev: number;
  supersedes?: string;
  tailoring: string;
  type: 'Policy';
  version: string;
}

export interface Rationale {
  author: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  evidence?: string[];
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  rev: number;
  supersedes?: string;
  text: string;
  type: 'Rationale';
}

export interface ReadinessReport {
  biasChecksStatus: {
    [k: string]: unknown;
  }[];
  blockers: {
    [k: string]: unknown;
  }[];
  computedBiasRisks: string[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  episode: string;
  flipSummary: {
    [k: string]: unknown;
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kernelVersion: string;
  mandateScorecard: string;
  openExclusions: string[];
  openGaps: string[];
  policyVersion: string;
  ready: boolean;
  rev: number;
  seed: number;
  standardsAssessment: string;
  supersedes?: string;
  type: 'ReadinessReport';
  warnings: {
    [k: string]: unknown;
  }[];
}

export interface RefreshTrigger {
  affected: string[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  description: string;
  detectedAt: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kind:
    | 'evidence-changed'
    | 'assumption-changed'
    | 'intended-use-changed'
    | 'artefact-version-changed'
    | 'elapsed-time'
    | 'indicator-detected'
    | 'external-finding'
    | 'signer-return';
  rev: number;
  source: string;
  supersedes?: string;
  type: 'RefreshTrigger';
}

export interface Result {
  aggregate: boolean;
  alternative: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  measure?: string;
  method: string;
  raw?:
    | number
    | {
        hi: number;
        lo: number;
      };
  rawUnits?: string;
  rev: number;
  run: string;
  supersedes?: string;
  type: 'Result';
  uncertainty?: {
    hi: number;
    lo: number;
  };
  units: string;
  value: number;
}

export interface Risk {
  acceptanceCriteria?: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  consequence: string;
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  evidence?: string[];
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kind:
    | 'bias-anchoring'
    | 'bias-confirmation'
    | 'bias-selection'
    | 'bias-over-specification'
    | 'method'
    | 'data'
    | 'schedule'
    | 'other';
  mitigation?: string[];
  monitor?: string;
  owner: string;
  rev: number;
  statement: string;
  status: 'open' | 'mitigated' | 'accepted' | 'closed';
  supersedes?: string;
  type: 'Risk';
  uncertainty?: string;
}

export interface Scenario {
  conditions: string[];
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  description: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  name: string;
  rationale:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  rev: number;
  source:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  supersedes?: string;
  type: 'Scenario';
}

export interface StandardsAssessment {
  aggregationRule: string;
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  dimensionVerdicts: {
    [k: string]: unknown;
  };
  episode: string;
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  k: number;
  kernelVersion: string;
  ratings: {
    applicable: boolean;
    justification: string[];
    questionId: string;
    rule: string;
    state: (1 | 2 | 3 | 4) | null;
    tailoringReason?: string;
  }[];
  rev: number;
  supersedes?: string;
  tailoring: string;
  type: 'StandardsAssessment';
}

export interface Uncertainty {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  kind: 'interval' | 'distribution' | 'scenarioSet';
  lexicon?: 'A' | 'B';
  lexiconBand?:
    | 'almost-no-chance'
    | 'very-unlikely'
    | 'unlikely'
    | 'roughly-even-chance'
    | 'likely'
    | 'very-likely'
    | 'almost-certain';
  rev: number;
  spec: {
    [k: string]: unknown;
  };
  supersedes?: string;
  type: 'Uncertainty';
}

/**
 * MIL-STD-3022 Table I fields; §5.3 retained-section rule via sections[].content.
 */
export interface VVARecord {
  accreditationDecision:
    | {
        authority: string;
        basis: 'document' | 'interview' | 'verbal';
        date: string;
        document?: string;
        scope: string;
      }
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  assumptionsCapabilitiesLimitationsRisks: {
    assumptions:
      | string[]
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
    capabilities:
      | string[]
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
    limitations:
      | string[]
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
    risks:
      | string[]
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
  };
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  issues?: string[];
  lessonsLearned?: string;
  methodology:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  problemStatement: string;
  requirementsAndAcceptabilityCriteria:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  rev: number;
  sections: {
    content:
      | string
      | {
          $exclusion: string;
        }
      | {
          $gap: string;
        };
    name: string;
  }[];
  supersedes?: string;
  type: 'VVARecord';
}

export interface WeightSet {
  confidence?: 'explicit' | 'inferred' | 'absent';
  createdAt: string;
  createdBy: {
    actorId: string;
    actorType: 'human' | 'agent' | 'kernel';
  };
  id: string;
  ingestionProvenance?: {
    extractedAt: string;
    extractor: string;
    locator: string;
    sourceArtifact: string;
  };
  method: 'swing' | 'stated' | 'equal' | 'derived';
  name: string;
  provenance:
    | string
    | {
        $exclusion: string;
      }
    | {
        $gap: string;
      };
  rev: number;
  supersedes?: string;
  type: 'WeightSet';
  weights: {
    [k: string]: unknown;
  };
}
