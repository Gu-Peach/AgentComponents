import { createTool } from '@mastra/core/tools';
import yaml from 'js-yaml';
import { z } from 'zod';
import { datasetService } from '../../service/dataset';
import { figmaService } from '../../service/figma';
import { modelService } from '../../service/model';
import { isResultValidate } from '../../types';
import { getPrivateFigmaToken } from '../../utils/context';
import { parseFigmaUrl } from '../../utils/parse-figma-url';
import { getFigmaMetricsTool } from '../../tools/get-figma-metrics';
import {
  getFigmaNodeDataTools,
  getFigmaNodeDataToolsInputSchema,
} from '../../tools/get-figma-node';
import type { DesignSystemAdapter } from '../types';

const DEFAULT_SPEC_SERVER_BASE_URL = 'https://0mym4uc8.fn.bytedance.net';
export const D2C_INITIAL_YAML_MAX_OUTPUT_TOKENS = 24_000;

type RootBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type D2CCodeArtifact = {
  filePath: string;
  content: string;
};

type CachedD2CResult = {
  yaml: string;
  score?: number;
  source?: string;
  codeArtifacts?: D2CCodeArtifact[];
};

type FigmaMetricNode = Record<string, unknown>;

type FigmaMetricsResult = {
  regions?: FigmaMetricNode[];
};

type IncompleteYamlDiagnosticErrorInput = {
  elapsedMs: number;
  chunkCount: number;
  outputLength: number;
};

type CreateFigmaToDesignSystemToolInput<ReferenceDoc, MatchedIcon> = {
  id: string;
  description: string;
  adapter: DesignSystemAdapter<ReferenceDoc, MatchedIcon>;
  outputField: string;
  outputDescription: string;
  candidateComponentsDescription: string;
  requiredDescription: string;
  requiredMessage: string;
  agentMissingMessage: string;
  enableCachedResult?: boolean;
  datasetName?: string;
};

export function formatIncompleteYamlDiagnosticError({
  elapsedMs,
  chunkCount,
  outputLength,
}: IncompleteYamlDiagnosticErrorInput): string {
  return `D2C initial YAML is incomplete. Please check whether the selected Figma node is too large or too complex for a single D2C generation. If the design contains large raster, illustration, or background areas, make sure those layers are marked/exportable in Figma so D2C can use them as images instead of rebuilding them as components. Diagnostics: ${[
    `elapsedMs=${elapsedMs}`,
    `chunks=${chunkCount}`,
    `outputLength=${outputLength}`,
    'missing=constraints',
    `maxOutputTokens=${D2C_INITIAL_YAML_MAX_OUTPUT_TOKENS}`,
  ].join('; ')}`;
}

function hasConstraintsSection(value: string): boolean {
  return /(^|\n)constraints\s*:/i.test(value);
}

function getSpecServerBaseUrl(): string {
  return (
    process.env.D2C_SPEC_SERVER_BASE_URL ||
    process.env.SPEC_SERVER_BASE_URL ||
    DEFAULT_SPEC_SERVER_BASE_URL
  ).replace(/\/$/, '');
}

async function getCachedD2CResult(figmaUrl: string): Promise<CachedD2CResult | null> {
  const searchParams = new URLSearchParams({ figmaUrl });
  const response = await modelService.fetch(
    `${getSpecServerBaseUrl()}/d2c/iterated-result?${searchParams.toString()}`,
  );
  if (!response.ok) return null;
  const payload = (await response.json()) as {
    code?: number;
    data?: {
      yaml?: unknown;
      score?: unknown;
      source?: unknown;
      codeArtifacts?: unknown;
    };
    yaml?: unknown;
    score?: unknown;
    source?: unknown;
    codeArtifacts?: unknown;
  };
  const data = payload.data ?? payload;
  const cachedYaml = typeof data.yaml === 'string' ? data.yaml.trim() : '';
  if (!cachedYaml) return null;
  const codeArtifacts = Array.isArray(data.codeArtifacts)
    ? data.codeArtifacts.filter(
        (artifact): artifact is D2CCodeArtifact =>
          isRecord(artifact) &&
          typeof artifact.filePath === 'string' &&
          typeof artifact.content === 'string',
      )
    : undefined;
  return {
    yaml: cachedYaml,
    score: typeof data.score === 'number' ? data.score : undefined,
    source: typeof data.source === 'string' ? data.source : undefined,
    codeArtifacts,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function stripYamlCodeFence(value: string): string {
  const trimmed = value.trim();
  const match = trimmed.match(/^```(?:yaml|yml)?\s*\n([\s\S]*?)\n```$/i);
  return match ? match[1].trim() : trimmed;
}

function injectRootBoundsIntoYaml(
  result: string,
  rootBounds?: RootBounds,
): string {
  if (!rootBounds) return result;

  try {
    const parsed = yaml.load(stripYamlCodeFence(result));
    if (!isRecord(parsed)) return result;

    const root = isRecord(parsed.root) ? parsed.root : {};
    const props = isRecord(root.props) ? root.props : {};
    const style = isRecord(props.style) ? props.style : {};

    style.width = rootBounds.width;
    if (style.height === undefined && style.minHeight === undefined) {
      style.minHeight = rootBounds.height;
    }
    props.style = style;
    root.props = props;
    parsed.root = root;

    const constraints = isRecord(parsed.constraints) ? parsed.constraints : {};
    const notes = Array.isArray(constraints.notes) ? constraints.notes : [];
    const sizeNote = `Figma root frame size: ${rootBounds.width}x${rootBounds.height}`;
    constraints.notes = notes.includes(sizeNote) ? notes : [...notes, sizeNote];
    parsed.constraints = constraints;

    return yaml.dump(parsed, { lineWidth: -1 }).trim();
  } catch {
    return result;
  }
}

function formatMetricNumber(value: unknown): string | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? Number.isInteger(value)
      ? String(value)
      : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
    : undefined;
}

function getMetricNodeLabel(node: FigmaMetricNode): string {
  const text =
    typeof node.text === 'string' && node.text.trim()
      ? ` text="${node.text.trim().slice(0, 60)}"`
      : '';
  const name =
    typeof node.name === 'string' && node.name.trim() ? node.name.trim() : '';
  const id =
    typeof node.id === 'string'
      ? node.id
      : typeof node.figmaNodeId === 'string'
        ? node.figmaNodeId
        : 'unknown-node';
  const type = typeof node.type === 'string' ? node.type : 'unknown';
  return `${name || id} (${type}, id=${id})${text}`;
}

function getMetricBox(node: FigmaMetricNode): string | undefined {
  const box = isRecord(node.box) ? node.box : undefined;
  const rect = isRecord(node.relativeRect)
    ? node.relativeRect
    : isRecord(node.rect)
      ? node.rect
      : undefined;
  const x = formatMetricNumber(box?.x ?? rect?.x);
  const y = formatMetricNumber(box?.y ?? rect?.y);
  const width = formatMetricNumber(box?.w ?? rect?.width);
  const height = formatMetricNumber(box?.h ?? rect?.height);
  if (!width || !height) return undefined;
  return `box=${x || '0'},${y || '0'},${width}x${height}`;
}

function getMetricLayout(node: FigmaMetricNode): string | undefined {
  const layout = isRecord(node.layout) ? node.layout : undefined;
  if (!layout) return undefined;
  const dir =
    typeof layout.dir === 'string'
      ? layout.dir
      : typeof layout.mode === 'string'
        ? layout.mode
        : undefined;
  const gap = formatMetricNumber(layout.gap ?? layout.itemSpacing);
  const paddingValue = layout.padding;
  const padding = Array.isArray(paddingValue)
    ? paddingValue.map(formatMetricNumber).filter(Boolean).join('/')
    : isRecord(paddingValue)
      ? ['top', 'right', 'bottom', 'left']
          .map((key) => formatMetricNumber(paddingValue[key]) || '0')
          .join('/')
      : undefined;
  const parts = [
    dir ? `dir=${dir}` : '',
    gap ? `gap=${gap}` : '',
    padding ? `padding=${padding}` : '',
  ].filter(Boolean);
  return parts.length ? `layout(${parts.join(', ')})` : undefined;
}

function getMetricTextStyle(node: FigmaMetricNode): string | undefined {
  const textStyle = isRecord(node.textStyle)
    ? node.textStyle
    : isRecord(node.typography)
      ? node.typography
      : undefined;
  if (!textStyle) return undefined;
  const size = formatMetricNumber(textStyle.size ?? textStyle.fontSize);
  const lineHeight = formatMetricNumber(
    textStyle.lineHeight ?? textStyle.lineHeightPx,
  );
  const weight = formatMetricNumber(textStyle.weight ?? textStyle.fontWeight);
  const parts = [
    size ? `fontSize=${size}` : '',
    lineHeight ? `lineHeight=${lineHeight}` : '',
    weight ? `fontWeight=${weight}` : '',
  ].filter(Boolean);
  return parts.length ? `textStyle(${parts.join(', ')})` : undefined;
}

function getMetricStyle(node: FigmaMetricNode): string | undefined {
  const style = isRecord(node.style) ? node.style : node;
  const fill = typeof style.fill === 'string' ? style.fill : undefined;
  const stroke = typeof style.stroke === 'string' ? style.stroke : undefined;
  const radius = formatMetricNumber(style.radius ?? style.cornerRadius);
  const strokeWeight = formatMetricNumber(style.strokeWeight);
  const parts = [
    fill ? `fill=${fill}` : '',
    stroke ? `stroke=${stroke}` : '',
    strokeWeight ? `strokeWeight=${strokeWeight}` : '',
    radius ? `radius=${radius}` : '',
  ].filter(Boolean);
  return parts.length ? `style(${parts.join(', ')})` : undefined;
}

export function summarizeFigmaMetricsForYamlPrompt(
  metrics: FigmaMetricsResult | undefined,
  maxRegions = 80,
): string {
  const regions = Array.isArray(metrics?.regions) ? metrics.regions : [];
  if (regions.length === 0) return '';

  const lines = [
    '## Figma Metrics Reference',
    '',
    'Use these metrics while generating Initial YAML:',
    '- Figma source data is the semantic node hierarchy source.',
    '- Figma metrics are the structured visual source for bounds, spacing, typography, color, radius and stroke.',
    '- Preserve component semantics in YAML; write only useful visual constraints instead of copying every raw metric node.',
    '',
    'Key regions:',
  ];

  for (const node of regions.slice(0, maxRegions)) {
    const parts = [
      getMetricNodeLabel(node),
      getMetricBox(node),
      getMetricLayout(node),
      getMetricTextStyle(node),
      getMetricStyle(node),
    ].filter(Boolean);
    lines.push(`- ${parts.join('; ')}`);
  }

  if (regions.length > maxRegions) {
    lines.push(
      `- ... ${regions.length - maxRegions} additional regions omitted from prompt summary`,
    );
  }

  return lines.join('\n');
}

function buildRepeatedGroupsText(data: {
  repeatedGroups: Array<{
    groupType: string;
    parentPath: string;
    itemCount: number;
    sampleItemPaths: string[];
  }>;
}): string {
  return data.repeatedGroups.length
    ? [
        '重复结构识别结果：',
        '- 下面这些区域已经被识别为重复 list/card-list，后续必须优先抽成 logic.data + repeat.itemTemplate。',
        '- 不要在 root.children 中继续手写所有重复项。',
        '- sampleItemPaths 只用于推断 item schema；剩余项应进入 logic.data。',
        ...data.repeatedGroups.map(
          (group) =>
            `- ${group.groupType} @ ${group.parentPath}: ${group.itemCount} items, sample=${group.sampleItemPaths.join(', ')}`,
        ),
      ].join('\n')
    : '';
}

function buildDiscreteStatusBlockGroupsText(data: {
  discreteStatusBlockGroups: Array<{
    parentPath: string;
    itemNames: string[];
    itemWidths: number[];
    selectedKey?: string;
    sourceProp?: string;
    hasContainerBackground: boolean;
  }>;
}): string {
  return data.discreteStatusBlockGroups.length
    ? [
        '离散状态块组识别结果：',
        '- 下面这些区域已经被识别为离散状态块组，不是连续轨道，也不是 Progress。',
        '- 每个 item 都有自己的背景承载块和文本，优先保留各自宽度、背景、圆角和选中态。',
        '- 如果 hasContainerBackground=false，不要给父容器补统一底轨背景。',
        ...data.discreteStatusBlockGroups.map(
          (group) =>
            `- @ ${group.parentPath}: items=${group.itemNames.join(' / ')}, widths=${group.itemWidths.join('/')}, selected=${group.selectedKey ?? 'none'}, sourceProp=${group.sourceProp ?? 'unknown'}, hasContainerBackground=${group.hasContainerBackground}`,
        ),
      ].join('\n')
    : '';
}

function buildMetricCardGroupHeadersText(data: {
  metricCardGroupHeaders?: Array<{
    compositePath: string;
    titleText?: string;
    switchLabel?: string;
    switchId?: string;
    switchPath: string;
  }>;
}): string {
  const headers = data.metricCardGroupHeaders ?? [];
  return headers.length
    ? [
        '指标卡组标题栏识别结果：',
        '- 下面这些「标题 + 开关」被设计稿画在复合块顶部、和下方指标卡组并列的独立标题栏里，但它们其实是该 SimpleMetricCardGroup 的顶部 ActionBar，不是独立块。',
        '- 标题文本必须并入下方第一个 SimpleMetricCardGroup 的 `title`，不要单独输出成 Heading/标题块。',
        "- 开关必须并入该 SimpleMetricCardGroup 的 `actions:[{type:'switcher', suffix:'<开关文案>'}]`（控制下方 Trend/图表显隐），不要输出成独立的 `Switch` 组件。",
        '- 也不要把这条标题栏单独输出成一个 Flex/容器；标题与开关都收进 SimpleMetricCardGroup 的 title/actions。',
        ...headers.map(
          (header) =>
            `- @ ${header.compositePath}: title="${header.titleText ?? ''}" -> first SimpleMetricCardGroup.title; switch="${header.switchLabel ?? ''}" (node ${header.switchId ?? header.switchPath}) -> actions[{type:'switcher', suffix:'${header.switchLabel ?? ''}'}]`,
        ),
      ].join('\n')
    : '';
}

function buildTableRowClipSummariesText(data: {
  tableRowClipSummaries: Array<{
    tablePath: string;
    rowContainerPath: string;
    originalRowCount: number;
    preservedRowCount: number;
    sampleRowPaths: string[];
    bindingKind: string;
  }>;
}): string {
  return data.tableRowClipSummaries.length
    ? [
        '表格行裁剪摘要：',
        '- 下列 Table body rows 已裁剪为代表性样本，保留的 sample rows 只用于推断列结构与单元格 schema。',
        '- 不要把 preserved samples 误认为真实数据总量；真实数据应优先抽象为 columns + dataSource。',
        '- sampleRowPaths 表示当前 figmaNodeData 中仍保留的代表性行。',
        ...data.tableRowClipSummaries.map(
          (summary) =>
            `- table=${summary.tablePath}; rowContainer=${summary.rowContainerPath}; originalRows=${summary.originalRowCount}; preservedRows=${summary.preservedRowCount}; binding=${summary.bindingKind}; sample=${summary.sampleRowPaths.join(', ')}`,
        ),
      ].join('\n')
    : '';
}

export function createFigmaToDesignSystemTool<ReferenceDoc, MatchedIcon>({
  id,
  description,
  adapter,
  outputField,
  outputDescription,
  candidateComponentsDescription,
  requiredDescription,
  requiredMessage,
  agentMissingMessage,
  enableCachedResult = false,
  datasetName = 'd2c-figma-data',
}: CreateFigmaToDesignSystemToolInput<ReferenceDoc, MatchedIcon>) {
  return createTool({
    id,
    description,
    inputSchema: getFigmaNodeDataToolsInputSchema,
    outputSchema: z
      .object({
        [outputField]: z.string().describe(outputDescription),
      })
      .extend({
        candidateComponents: z
          .array(z.string())
          .optional()
          .describe(candidateComponentsDescription),
        required: z.string().optional().describe(requiredDescription),
        score: z.number().optional().describe('Best D2C iteration score.'),
        source: z
          .string()
          .optional()
          .describe('Source of the returned D2C result.'),
        codeArtifacts: z
          .array(
            z.object({
              filePath: z.string(),
              content: z.string(),
            }),
          )
          .optional()
          .describe('Final D2C code artifacts saved by completed iterations.'),
      }) as any,
    execute: async (inputData, context) => {
      const { fileKey, nodeId } = parseFigmaUrl(inputData.figmaUrl);
      if (enableCachedResult) {
        try {
          const cachedResult = await getCachedD2CResult(inputData.figmaUrl);
          if (cachedResult) {
            return {
              [outputField]: cachedResult.yaml,
              score: cachedResult.score,
              source: cachedResult.source,
              codeArtifacts: cachedResult.codeArtifacts,
            };
          }
        } catch {
          // Fall back to live Figma parsing when the D2C iteration cache is unavailable.
        }
      }

      const privateToken = getPrivateFigmaToken(context);
      const imageUrlPromise = figmaService
        .getImageUrlByNode(fileKey, nodeId, 2, privateToken)
        .catch(() => undefined);
      const figmaMetricsPromise = getFigmaMetricsTool
        .execute?.(
          {
            figmaUrl: inputData.figmaUrl,
            maxDepth: 8,
            maxNodes: 300,
            minSize: 1,
            format: 'compact',
          },
          context,
        )
        .catch(() => undefined);

      const rawData = await getFigmaNodeDataTools.execute!(
        {
          figmaUrl: inputData.figmaUrl,
          enableRepeatedStructureNormalization:
            adapter.id === 'hiui'
              ? adapter.repeatedStructureNormalization?.enabledByDefault !==
                false
              : false,
        },
        ({
          ...context,
          designSystemAdapter: adapter,
        } as typeof context),
      );
      if (!rawData) {
        throw new Error('Failed to get Figma node data');
      }
      if (!isResultValidate(rawData)) {
        throw rawData.validationErrors;
      }
      const data = rawData;
      (context as any)?.tracingContext?.currentSpan?.update?.({
        metadata: {
          candidateComponents: data.candidateComponents,
        },
      });
      const designSystemAgent = context?.mastra?.getAgentById(
        adapter.agent.agentId,
      );
      if (!designSystemAgent) {
        throw new Error(agentMissingMessage);
      }
      const matchedReferenceDocs = await adapter.resolveReferenceDocs(
        data.candidateComponents,
      );
      const matchedReferenceDocsText =
        adapter.formatReferenceDocs(matchedReferenceDocs);
      const matchedIconsText =
        adapter.formatMatchedIcons?.(data.matchedIcons as MatchedIcon[]) ?? '';
      const repeatedGroupsText = buildRepeatedGroupsText(data);
      const discreteStatusBlockGroupsText =
        buildDiscreteStatusBlockGroupsText(data);
      const metricCardGroupHeadersText =
        buildMetricCardGroupHeadersText(data);
      const tableRowClipSummariesText =
        buildTableRowClipSummariesText(data);
      const imageUrl = await imageUrlPromise;
      const figmaMetricsSummary = summarizeFigmaMetricsForYamlPrompt(
        (await figmaMetricsPromise) as FigmaMetricsResult | undefined,
      );

      let result = '';

      const streamStartMs = Date.now();
      let chunkCount = 0;

      const yamlResult = await designSystemAgent.stream(
        [
          {
            role: 'user',
            content: [
              ...(imageUrl
                ? [
                    {
                      type: 'text' as const,
                      text: '这是 Figma 参考图。请用它恢复布局骨架、分组关系和叠层关系。',
                    },
                    {
                      type: 'image' as const,
                      image: imageUrl,
                    },
                  ]
                : []),
              {
                type: 'text',
                text: `Figma source data:\n${data.figmaNodeData}`,
              },
            ],
          },
          {
            role: 'user',
            content: [
              {
                type: 'text',
                text: [
                  repeatedGroupsText,
                  discreteStatusBlockGroupsText,
                  metricCardGroupHeadersText,
                  tableRowClipSummariesText,
                  figmaMetricsSummary,
                  matchedIconsText,
                  matchedReferenceDocsText,
                ]
                  .filter(Boolean)
                  .join('\n\n'),
              },
            ],
          },
        ],
        {
          modelSettings: {
            maxOutputTokens: D2C_INITIAL_YAML_MAX_OUTPUT_TOKENS,
          },
        },
      );

      for await (const chunk of yamlResult.textStream) {
        if (process.env.LOCAL) {
          process.stdout.write(chunk);
        }
        chunkCount += 1;
        result += chunk;
      }

      if (!hasConstraintsSection(result)) {
        throw new Error(
          formatIncompleteYamlDiagnosticError({
            elapsedMs: Date.now() - streamStartMs,
            chunkCount,
            outputLength: result.length,
          }),
        );
      }

      result = injectRootBoundsIntoYaml(result, data.rootBounds);

      try {
        const rate = context.requestContext?.get('dataset') ? 1 : 0.2;
        datasetService.report(
          datasetName,
          {
            fileId: fileKey,
            nodeId,
            input: data.figmaNodeData,
            output: result,
          },
          rate,
        );
      } catch (err: any) {
        throw new Error(`Dataset report failed: ${err.message}`);
      }
      return {
        [outputField]: result,
        candidateComponents: data.candidateComponents,
        required: requiredMessage,
      };
    },
  });
}
