import { MCPServer } from '@mastra/mcp';
import { figmaToM4bComponents } from '../design-systems/m4b/tools/figma-to-m4b';
import { detectFigmaLayoutBlocksTool } from '../tools/detect-figma-layout-blocks';
import { getFigmaImageTool } from '../tools/get-figma-image';
import { getFigmaMetricsTool } from '../tools/get-figma-metrics';
import { getRawFigmaNodeTools } from '../tools/get-raw-figma-node';
export const m4bD2cServer = new MCPServer({
  id: 'm4b-d2c',
  name: 'M4B Design D2C(Design to Code)',
  version: '1.0.0',
  tools: {
    detectFigmaLayoutBlocksTool,
    figmaToM4bComponents,
    getFigmaImageTool,
    getFigmaMetricsTool,
    getRawFigmaNodeTools,
  },
});
