import {
  createFigmaToDesignSystemTool,
  D2C_INITIAL_YAML_MAX_OUTPUT_TOKENS,
  formatIncompleteYamlDiagnosticError,
  summarizeFigmaMetricsForYamlPrompt,
} from '../../tools/create-figma-to-design-system-tool';
import { m4bDesignSystemAdapter } from '../core/adapter';

export {
  D2C_INITIAL_YAML_MAX_OUTPUT_TOKENS,
  formatIncompleteYamlDiagnosticError,
  summarizeFigmaMetricsForYamlPrompt,
};

export const figmaToM4bComponents = createFigmaToDesignSystemTool({
  id: 'figma-to-m4b-components',
  description:
    'Given a Figma file, return the Figma data converted into m4b component information, and require code implementation based on this data structure.',
  adapter: m4bDesignSystemAdapter,
  outputField: 'm4bYamlResult',
  outputDescription: 'The converted M4B Components Yaml',
  candidateComponentsDescription:
    'Candidate m4b-related component names detected from Figma',
  requiredDescription:
    'The required code implementation based on the M4B Components Yaml.',
  requiredMessage:
    'Before implementing the code, you must query the m4b related usage documentation to ensure the correctness of the implementation.',
  agentMissingMessage: 'M4B D2C agent not found',
  enableCachedResult: true,
});
