import { D2C_AGENT_ID } from '../../../agents/d2c-agent';
import type { FigmaLikePayload } from '../../../utils/figma-candidate-types';
import type { DesignSystemAdapter } from '../../types';
import { figmaComponentSignatures } from '../detection/component-signatures';
import { detectFigmaComponentCandidates } from '../detection/detect-component-candidates';
import {
  formatMatchedIconsForPrompt,
  type MatchedIconCandidate,
  m4bIconMatcher,
} from '../icons/icon-matcher';
import {
  formatMatchedReferenceDocs,
  getReferenceKeyForComponent,
  type MatchedReferenceDoc,
  resolveMatchedReferenceDocs,
} from '../reference-docs/reference-resolver';

export const m4bDesignSystemAdapter: DesignSystemAdapter<
  MatchedReferenceDoc,
  MatchedIconCandidate
> = {
  id: 'm4b',
  displayName: 'M4B Design',
  agent: {
    agentId: D2C_AGENT_ID,
    promptKey: 'gec.ai.m4b_d2c',
    outputField: 'm4bYamlResult',
  },
  componentSignatures: figmaComponentSignatures,
  detectComponentCandidates: (payload: FigmaLikePayload) =>
    detectFigmaComponentCandidates(payload, figmaComponentSignatures),
  getReferenceKeyForComponent,
  resolveReferenceDocs: resolveMatchedReferenceDocs,
  formatReferenceDocs: formatMatchedReferenceDocs,
  formatMatchedIcons: formatMatchedIconsForPrompt,
  iconMatcher: m4bIconMatcher,
};
