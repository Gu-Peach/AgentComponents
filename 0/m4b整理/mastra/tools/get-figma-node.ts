import { createTool } from '@mastra/core/tools';
import { allExtractors, simplifyRawFigmaObject } from 'figma-developer-mcp';
import yaml from 'js-yaml';
import { z } from 'zod';
import {
  type DesignSystemAdapter,
  type DesignSystemIconMatcher,
  m4bDesignSystemAdapter,
} from '../design-systems';
import { figmaService } from '../service/figma';
import { logger } from '../service/logger';
import { normalizeHiuiRepeatedStructures } from '../design-systems/hiui/normalization/normalize-repeated-structures';
import { detectMetricCardGroupHeaders } from '../design-systems/m4b/detection/detect-metric-card-group-headers';
import { getPrivateFigmaToken } from '../utils/context';
import { detectDiscreteStatusBlockGroups } from '../utils/detect-discrete-status-blocks';
import { detectRepeatedGroups } from '../utils/detect-repeated-groups';
import type { FigmaCandidateDetectionResult } from '../utils/figma-candidate-detection-types';
import { parseFigmaUrl } from '../utils/parse-figma-url';

type MatchedIconOutput = {
  nodeName: string;
  iconName: string;
  componentName: string;
  usage: string;
  importSource?: string;
};

type AnyDesignSystemAdapter = {
  id?: string;
  repeatedStructureNormalization?: {
    enabledByDefault?: boolean;
  };
  detectComponentCandidates: DesignSystemAdapter['detectComponentCandidates'];
  getReferenceKeyForComponent: DesignSystemAdapter['getReferenceKeyForComponent'];
  iconMatcher?: DesignSystemIconMatcher<MatchedIconOutput>;
};

function getDesignSystemAdapterFromContext(
  context: unknown,
): AnyDesignSystemAdapter {
  return (
    (context as { designSystemAdapter?: AnyDesignSystemAdapter } | undefined)
      ?.designSystemAdapter ?? m4bDesignSystemAdapter
  );
}

type SimplifiedNode = {
  id?: string;
  name?: string;
  type?: string;
  clippedSnapshotCandidate?: unknown;
  layout?: unknown;
  fills?: unknown;
  strokes?: unknown;
  effects?: unknown;
  borderRadius?: unknown;
  strokeWeight?: unknown;
  textStyle?: unknown;
  componentId?: string;
  componentProperties?: unknown;
  children?: SimplifiedNode[];
  [key: string]: unknown;
};

type SimplifiedDesign = {
  name?: string;
  rootBounds?: FigmaNodeBounds;
  nodes?: SimplifiedNode[];
  assets?: {
    images?: Record<string, ImageAssetManifestItem>;
  };
  assetBindings?: AssetBinding[];
  components?: Record<string, Record<string, unknown>>;
  componentSets?: Record<string, Record<string, unknown>>;
  globalVars?: {
    styles?: Record<string, unknown>;
  };
};

type ImageAssetUsageHint =
  | 'avatar'
  | 'badge'
  | 'logo'
  | 'illustration'
  | 'background'
  | 'thumbnail'
  | 'connector'
  | 'progress'
  | 'decorative-icon'
  | 'unknown';

type ImageAssetManifestItem = {
  url: string;
  format?: 'svg' | 'png' | 'jpg' | 'pdf';
  width?: number;
  height?: number;
  nodePath: string;
};

type AssetBinding = {
  targetPath: string;
  assetRef: string;
};

type FigmaNodeBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type UsedRefs = {
  componentIds: Set<string>;
  componentSetIds: Set<string>;
  styleRefs: Set<string>;
};

const GENERIC_NODE_NAMES = new Set([
  'Text',
  'text',
  '默认',
  'default',
  'content',
  'container',
  'Frame',
]);
const NODE_FIELD_WHITELIST = [
  'id',
  'name',
  'type',
  'layout',
  'fills',
  'strokes',
  'effects',
  'borderRadius',
  'strokeWeight',
  'opacity',
  'text',
  'textStyle',
  'componentId',
  'componentProperties',
  'resolvedIcon',
  'resolvedSvg',
  'resolvedImage',
  'resolvedStructure',
  'children',
];

function compactFigmaSourceData(design: SimplifiedDesign): SimplifiedDesign {
  const styleMap = design.globalVars?.styles ?? {};
  const usedRefs = collectUsedRefs(design.nodes ?? [], styleMap);
  const compactedNodes = compactNodes(design.nodes ?? []);
  const compactedComponents = pickUsedComponents(design.components, usedRefs);
  const compactedComponentSets = pickUsedComponentSets(
    design.componentSets,
    usedRefs,
  );
  const compactedStyles = pickUsedStyles(styleMap, usedRefs);

  const result: SimplifiedDesign = {
    name: design.name,
    nodes: compactedNodes,
  };

  if (Object.keys(compactedComponents).length > 0) {
    result.components = compactedComponents;
  }

  if (Object.keys(compactedComponentSets).length > 0) {
    result.componentSets = compactedComponentSets;
  }

  if (Object.keys(compactedStyles).length > 0) {
    result.globalVars = {
      styles: compactedStyles,
    };
  }

  if (design.assets?.images && Object.keys(design.assets.images).length > 0) {
    result.assets = {
      images: design.assets.images,
    };
  }

  if (design.assetBindings?.length) {
    result.assetBindings = design.assetBindings;
  }

  return result;
}

function collectUsedRefs(
  nodes: SimplifiedNode[],
  styleMap: Record<string, unknown>,
): UsedRefs {
  const usedRefs: UsedRefs = {
    componentIds: new Set<string>(),
    componentSetIds: new Set<string>(),
    styleRefs: new Set<string>(),
  };

  const walk = (node: SimplifiedNode) => {
    collectStyleRefsFromValue(node.layout, styleMap, usedRefs.styleRefs);
    collectStyleRefsFromValue(node.fills, styleMap, usedRefs.styleRefs);
    collectStyleRefsFromValue(node.strokes, styleMap, usedRefs.styleRefs);
    collectStyleRefsFromValue(node.effects, styleMap, usedRefs.styleRefs);
    collectStyleRefsFromValue(node.textStyle, styleMap, usedRefs.styleRefs);

    if (typeof node.componentId === 'string') {
      usedRefs.componentIds.add(node.componentId);
    }

    for (const child of node.children ?? []) {
      walk(child);
    }
  };

  for (const node of nodes) {
    walk(node);
  }

  return usedRefs;
}

function collectStyleRefsFromValue(
  value: unknown,
  styleMap: Record<string, unknown>,
  styleRefs: Set<string>,
) {
  if (typeof value === 'string' && value in styleMap) {
    styleRefs.add(value);
    return;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      collectStyleRefsFromValue(item, styleMap, styleRefs);
    }
    return;
  }

  if (value && typeof value === 'object') {
    for (const nestedValue of Object.values(value)) {
      collectStyleRefsFromValue(nestedValue, styleMap, styleRefs);
    }
  }
}

function compactNodes(nodes: SimplifiedNode[]): SimplifiedNode[] {
  return nodes
    .map((node) => compactNode(node))
    .filter(Boolean) as SimplifiedNode[];
}

function compactNode(node: SimplifiedNode): SimplifiedNode | null {
  const result: SimplifiedNode = {};

  for (const key of NODE_FIELD_WHITELIST) {
    if (!(key in node)) {
      continue;
    }

    if (key === 'children') {
      const compactedChildren = compactNodes(
        (node.children ?? []).filter(Boolean),
      );
      if (compactedChildren.length > 0) {
        result.children = compactedChildren;
      }
      continue;
    }

    if (key === 'name') {
      const compactedName = compactNodeName(node);
      if (compactedName) {
        result.name = compactedName;
      }
      continue;
    }

    const value = node[key];
    if (shouldKeepValue(value)) {
      result[key] = normalizeNodeValue(value);
    }
  }

  return Object.keys(result).length > 0 ? result : null;
}

function compactNodeName(node: SimplifiedNode): string | undefined {
  if (typeof node.name !== 'string') {
    return undefined;
  }

  const trimmedName = node.name.trim();
  if (!trimmedName) {
    return undefined;
  }

  if (node.type === 'TEXT') {
    if (GENERIC_NODE_NAMES.has(trimmedName)) {
      return undefined;
    }

    if (typeof node.text === 'string' && trimmedName === node.text.trim()) {
      return undefined;
    }
  }

  return trimmedName;
}

function shouldKeepValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  if (typeof value === 'object') {
    return Object.keys(value).length > 0;
  }

  if (typeof value === 'string') {
    return value.trim().length > 0;
  }

  return true;
}

function normalizeNodeValue(value: unknown): unknown {
  if (typeof value === 'string') {
    return value.includes('\n')
      ? value.replace(/\s*\n\s*/g, ' ').trim()
      : value;
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeNodeValue(item))
      .filter((item) => shouldKeepValue(item));
  }

  if (value && typeof value === 'object') {
    if ((value as Record<string, unknown>).type === 'IMAGE') {
      // Keep only the fact that this is an image fill so downstream mapping can
      // render a placeholder img without relying on the image content itself.
      return {
        type: 'IMAGE',
      };
    }

    return Object.fromEntries(
      Object.entries(value)
        .filter(([, nestedValue]) => shouldKeepValue(nestedValue))
        .map(([nestedKey, nestedValue]) => [
          nestedKey,
          normalizeNodeValue(nestedValue),
        ])
        .filter(([, nestedValue]) => shouldKeepValue(nestedValue)),
    );
  }

  return value;
}

function pickUsedComponents(
  components: SimplifiedDesign['components'],
  usedRefs: UsedRefs,
): Record<string, Record<string, unknown>> {
  if (!components) {
    return {};
  }

  const result: Record<string, Record<string, unknown>> = {};

  for (const componentId of Array.from(usedRefs.componentIds)) {
    const component = components[componentId];
    if (!component) {
      continue;
    }

    const compactedComponent: Record<string, unknown> = {};
    if (typeof component.name === 'string' && component.name.trim()) {
      compactedComponent.name = component.name;
    }
    if (
      typeof component.componentSetId === 'string' &&
      component.componentSetId.trim()
    ) {
      compactedComponent.componentSetId = component.componentSetId;
      usedRefs.componentSetIds.add(component.componentSetId);
    }

    if (Object.keys(compactedComponent).length > 0) {
      result[componentId] = compactedComponent;
    }
  }

  return result;
}

function pickUsedComponentSets(
  componentSets: SimplifiedDesign['componentSets'],
  usedRefs: UsedRefs,
): Record<string, Record<string, unknown>> {
  if (!componentSets) {
    return {};
  }

  const result: Record<string, Record<string, unknown>> = {};

  for (const componentSetId of Array.from(usedRefs.componentSetIds)) {
    const componentSet = componentSets[componentSetId];
    if (!componentSet) {
      continue;
    }

    const compactedComponentSet: Record<string, unknown> = {};
    if (typeof componentSet.name === 'string' && componentSet.name.trim()) {
      compactedComponentSet.name = componentSet.name;
    }
    if (
      typeof componentSet.description === 'string' &&
      componentSet.description.trim()
    ) {
      compactedComponentSet.description = componentSet.description;
    }

    if (Object.keys(compactedComponentSet).length > 0) {
      result[componentSetId] = compactedComponentSet;
    }
  }

  return result;
}

function pickUsedStyles(
  styleMap: Record<string, unknown>,
  usedRefs: UsedRefs,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const styleRef of Array.from(usedRefs.styleRefs)) {
    if (styleRef in styleMap) {
      result[styleRef] = styleMap[styleRef];
    }
  }

  return result;
}

export const getFigmaNodeDataToolsInputSchema = z.object({
  figmaUrl: z
    .url()
    .describe(
      'The full Figma URL, for example https://www.figma.com/design/<fileKey>/...?node-id=<nodeId>.',
    ),
  enableRepeatedStructureNormalization: z
    .boolean()
    .optional()
    .describe(
      'Whether to normalize repeated structures before serializing figmaNodeData. Defaults to adapter-specific behavior.',
    ),
});

/**
 * Node types that can be exported as SVG images.
 * When a FRAME, GROUP, or INSTANCE contains only these types, we can collapse it to IMAGE-SVG.
 * Note: FRAME/GROUP/INSTANCE are NOT included here—they're only eligible if collapsed to IMAGE-SVG.
 */
const SVG_ELIGIBLE_TYPES = new Set([
  'IMAGE-SVG', // VECTOR nodes are converted to IMAGE-SVG, or containers that were collapsed
  'STAR',
  'LINE',
  'ELLIPSE',
  'REGULAR_POLYGON',
  'RECTANGLE',
]);

const LAYOUT_SIGNIFICANT_DIMENSION = 96;
const VISUAL_ASSET_MAX_DIMENSION = 160;
const VISUAL_ASSET_MAX_ASPECT_RATIO = 2;
const IMAGE_ASSET_ROOT_MIN_DIMENSION = 160;
const COMPOSITE_IMAGE_ROOT_MIN_HEIGHT = 80;
const FLATTENED_IMAGE_FRAME_MAX_DIRECT_CHILDREN = 12;
const WEAK_FLATTENED_IMAGE_MIN_DIMENSION = 24;
const CLIPPED_SNAPSHOT_OVERFLOW_RATIO = 1.35;
const CLIPPED_SNAPSHOT_MIN_OVERFLOW_PX = 24;
const CLIPPED_SNAPSHOT_AREA_RATIO = 1.8;
const CLIPPED_SNAPSHOT_MIN_DESCENDANTS = 12;
const MAX_RESOLVED_SVG_ASSET_EXPORTS = 30;
const MAX_RESOLVED_IMAGE_ASSET_EXPORTS = 30;

function getObjectRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : undefined;
}

function getNodeLayout(
  node: unknown,
  result?: unknown,
  styleMap?: Record<string, unknown>,
): Record<string, unknown> | undefined {
  const nodeLayout = getObjectRecord(node)?.layout;
  const resultLayout = getObjectRecord(result)?.layout;
  return (
    getObjectRecord(nodeLayout) ??
    (typeof nodeLayout === 'string'
      ? getObjectRecord(styleMap?.[nodeLayout])
      : undefined) ??
    getObjectRecord(resultLayout) ??
    (typeof resultLayout === 'string'
      ? getObjectRecord(styleMap?.[resultLayout])
      : undefined)
  );
}

function getNumericDimension(
  layout: Record<string, unknown> | undefined,
  axis: 'width' | 'height',
): number | undefined {
  const dimensions = getObjectRecord(layout?.dimensions);
  const value = dimensions?.[axis];
  return typeof value === 'number' ? value : undefined;
}

function getRawNodeBounds(node: unknown): FigmaNodeBounds | undefined {
  const bounds = getObjectRecord(getObjectRecord(node)?.absoluteBoundingBox);
  const x = bounds?.x;
  const y = bounds?.y;
  const width = bounds?.width;
  const height = bounds?.height;
  if (
    typeof x !== 'number' ||
    typeof y !== 'number' ||
    typeof width !== 'number' ||
    typeof height !== 'number'
  ) {
    return undefined;
  }
  return { x, y, width, height };
}

function isClippedSnapshotUnsafeName(value: unknown): boolean {
  return /table|tabs?|dropdown|select|form|menu|modal|drawer|list|scroll|carousel|swiper/i.test(
    String(value ?? ''),
  );
}

function countRawVisibleDescendants(node: unknown): number {
  const children = Array.isArray(getObjectRecord(node)?.children)
    ? (getObjectRecord(node)?.children as unknown[])
    : [];
  return children.reduce<number>((count, child) => {
    const childRecord = getObjectRecord(child);
    if (childRecord?.visible === false) return count;
    return count + 1 + countRawVisibleDescendants(child);
  }, 0);
}

function hasOversizedRawDescendant(
  parentBounds: FigmaNodeBounds,
  node: unknown,
): boolean {
  const children = Array.isArray(getObjectRecord(node)?.children)
    ? (getObjectRecord(node)?.children as unknown[])
    : [];
  for (const child of children) {
    const childRecord = getObjectRecord(child);
    if (childRecord?.visible === false) continue;
    const childBounds = getRawNodeBounds(child);
    if (childBounds) {
      const widthOverflow = Math.max(0, childBounds.width - parentBounds.width);
      const heightOverflow = Math.max(
        0,
        childBounds.height - parentBounds.height,
      );
      const childArea = childBounds.width * childBounds.height;
      const parentArea = parentBounds.width * parentBounds.height;
      const oversizedByRatio =
        childBounds.width >=
          parentBounds.width * CLIPPED_SNAPSHOT_OVERFLOW_RATIO ||
        childBounds.height >=
          parentBounds.height * CLIPPED_SNAPSHOT_OVERFLOW_RATIO;
      const oversizedByArea =
        parentArea > 0 && childArea >= parentArea * CLIPPED_SNAPSHOT_AREA_RATIO;
      if (
        (oversizedByRatio &&
          Math.max(widthOverflow, heightOverflow) >=
            CLIPPED_SNAPSHOT_MIN_OVERFLOW_PX) ||
        oversizedByArea
      ) {
        return true;
      }
    }
    if (hasOversizedRawDescendant(parentBounds, child)) return true;
  }
  return false;
}

function isRawClippedFrameSnapshotCandidate(node: unknown): boolean {
  const record = getObjectRecord(node);
  if (!record || record.clipsContent !== true) return false;
  if (isClippedSnapshotUnsafeName(record.name)) return false;
  const type = String(record.type ?? '').toUpperCase();
  if (
    type !== 'FRAME' &&
    type !== 'GROUP' &&
    type !== 'INSTANCE' &&
    type !== 'COMPONENT'
  )
    return false;
  const bounds = getRawNodeBounds(node);
  if (!bounds || bounds.width < 1 || bounds.height < 1) return false;
  if (countRawVisibleDescendants(node) < CLIPPED_SNAPSHOT_MIN_DESCENDANTS)
    return false;
  return hasOversizedRawDescendant(bounds, node);
}

function getSimplifiedRootBounds(
  design: SimplifiedDesign,
): FigmaNodeBounds | undefined {
  const rootNode = design.nodes?.[0];
  const layout = getNodeLayout(rootNode);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');
  if (typeof width !== 'number' || typeof height !== 'number') {
    return undefined;
  }
  return { x: 0, y: 0, width, height };
}

function hasOwnKeys(value: unknown): boolean {
  return (
    !!value &&
    typeof value === 'object' &&
    Object.keys(value as Record<string, unknown>).length > 0
  );
}

function hasFigmaComponentIdentity(node: unknown): boolean {
  const record = getObjectRecord(node);
  return Boolean(record?.componentId || record?.componentProperties);
}

function isLayoutSignificantContainer(node: unknown, result: unknown): boolean {
  const layout = getNodeLayout(node, result);
  if (!layout) {
    return false;
  }

  const mode = layout.mode;
  if (mode === 'row' || mode === 'column') {
    return true;
  }

  if (layout.position === 'absolute') {
    return true;
  }

  if (
    layout.gap !== undefined ||
    layout.padding !== undefined ||
    layout.alignItems !== undefined ||
    layout.justifyContent !== undefined ||
    layout.alignSelf !== undefined
  ) {
    return true;
  }

  if (
    hasOwnKeys(layout.sizing) ||
    hasOwnKeys(layout.locationRelativeToParent)
  ) {
    return true;
  }

  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');
  return (
    (typeof width === 'number' && width >= LAYOUT_SIGNIFICANT_DIMENSION) ||
    (typeof height === 'number' && height >= LAYOUT_SIGNIFICANT_DIMENSION)
  );
}

function canCollapseContainerToSvg(
  node: unknown,
  result: unknown,
  children: Array<{ type?: unknown }>,
): boolean {
  if (children.length === 0) {
    return false;
  }

  const nodeName = String(
    getObjectRecord(result)?.name ?? getObjectRecord(node)?.name ?? '',
  ).toLowerCase();
  if (/button|action|more|dropdown|trigger|\.\.\.|···/.test(nodeName)) {
    return false;
  }

  if (/chart|donut|waterfall|trend|y and lines/.test(nodeName)) {
    return false;
  }

  if (isLayoutSignificantContainer(node, result)) {
    return false;
  }

  return children.every((child) =>
    SVG_ELIGIBLE_TYPES.has(String(child.type ?? '')),
  );
}

function hasTextDescendant(node: SimplifiedNode): boolean {
  if (node.type === 'TEXT' || typeof node.text === 'string') {
    return true;
  }

  return (node.children ?? []).some((child) => hasTextDescendant(child));
}

function valueContainsImageFill(value: unknown): boolean {
  if (!value) {
    return false;
  }

  if (Array.isArray(value)) {
    return value.some((item) => valueContainsImageFill(item));
  }

  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;

    if (record.type === 'IMAGE') {
      return true;
    }

    return Object.values(record).some((item) => valueContainsImageFill(item));
  }

  return false;
}

function hasImageFill(
  node: SimplifiedNode,
  styleMap?: Record<string, unknown>,
): boolean {
  if (valueContainsImageFill(node.fills)) {
    return true;
  }

  return typeof node.fills === 'string'
    ? valueContainsImageFill(styleMap?.[node.fills])
    : false;
}

function getResolvedImageFallbackElement(
  node: SimplifiedNode,
): 'img' | 'backgroundImage' {
  return (node.children ?? []).length > 0 ? 'backgroundImage' : 'img';
}

function hasVisualDescendant(node: SimplifiedNode): boolean {
  const nodeType = String(node.type ?? '');

  if (
    SVG_ELIGIBLE_TYPES.has(nodeType) ||
    nodeType === 'VECTOR' ||
    hasImageFill(node)
  ) {
    return true;
  }

  return (node.children ?? []).some((child) => hasVisualDescendant(child));
}

function isVisualAssetCandidate(node: SimplifiedNode): boolean {
  if (node.resolvedIcon || node.resolvedSvg || hasImageFill(node)) {
    return false;
  }

  if (hasTextDescendant(node) || !hasVisualDescendant(node)) {
    return false;
  }

  const layout = getNodeLayout(node);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');

  if (!width || !height) {
    return false;
  }

  const aspectRatio = Math.max(width / height, height / width);

  return (
    width <= VISUAL_ASSET_MAX_DIMENSION &&
    height <= VISUAL_ASSET_MAX_DIMENSION &&
    aspectRatio <= VISUAL_ASSET_MAX_ASPECT_RATIO
  );
}

function getResolvedSvgExportDimensions(
  node: SimplifiedNode,
  styleMap?: Record<string, unknown>,
) {
  const layout = getNodeLayout(node, undefined, styleMap);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');

  if (!width || !height) {
    return undefined;
  }

  return { width, height };
}

function isResolvedSvgExportCandidate(
  node: SimplifiedNode,
  styleMap?: Record<string, unknown>,
): boolean {
  if (!node.id || !node.resolvedSvg) {
    return false;
  }

  const dimensions = getResolvedSvgExportDimensions(node, styleMap);

  if (!dimensions) {
    return true;
  }

  const aspectRatio = Math.max(
    dimensions.width / dimensions.height,
    dimensions.height / dimensions.width,
  );

  return aspectRatio <= VISUAL_ASSET_MAX_ASPECT_RATIO;
}

function isResolvedImageExportCandidate(node: SimplifiedNode): boolean {
  return Boolean(node.id && node.resolvedImage);
}

function isSvgLikeNode(node: SimplifiedNode): boolean {
  const type = String(node.type ?? '').toUpperCase();
  return (
    SVG_ELIGIBLE_TYPES.has(type) ||
    type === 'VECTOR' ||
    type === 'BOOLEAN_OPERATION'
  );
}

const svgLikeDescendantCountCache = new WeakMap<SimplifiedNode, number>();

function countSvgLikeDescendants(node: SimplifiedNode): number {
  const cached = svgLikeDescendantCountCache.get(node);
  if (cached !== undefined) {
    return cached;
  }

  const count = (node.children ?? []).reduce(
    (count, child) =>
      count + (isSvgLikeNode(child) ? 1 : 0) + countSvgLikeDescendants(child),
    0,
  );
  svgLikeDescendantCountCache.set(node, count);
  return count;
}

function isFragmentSvgNode(node: SimplifiedNode): boolean {
  const name = String(node.name ?? '')
    .trim()
    .toLowerCase();
  return (
    /^\d+$/.test(name) ||
    /^vector\b/.test(name) ||
    /^ellipse\b/.test(name) ||
    /^rectangle\b/.test(name) ||
    name === 'subtract' ||
    name === 'mask group' ||
    name === 'path'
  );
}

function isVisualSvgRootCandidate(
  node: SimplifiedNode,
  styleMap?: Record<string, unknown>,
): boolean {
  if (!node.id || hasImageFill(node, styleMap) || hasTextDescendant(node)) {
    return false;
  }

  const type = String(node.type ?? '').toUpperCase();
  if (type === 'TEXT' || type === 'VECTOR') {
    return false;
  }

  if ((node.children ?? []).length === 0 && !node.resolvedSvg) {
    return false;
  }

  const layout = getNodeLayout(node, undefined, styleMap);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');
  if (!width || !height) {
    return false;
  }

  const aspectRatio = Math.max(width / height, height / width);
  if (
    width > VISUAL_ASSET_MAX_DIMENSION ||
    height > VISUAL_ASSET_MAX_DIMENSION ||
    aspectRatio > VISUAL_ASSET_MAX_ASPECT_RATIO
  ) {
    return false;
  }

  return countSvgLikeDescendants(node) >= 2;
}

function ensureResolvedSvg(node: SimplifiedNode) {
  node.resolvedSvg = {
    ...(getObjectRecord(node.resolvedSvg) ?? {}),
    usage: 'generic-svg',
    fallbackElement: 'img',
    ...(node.name ? { svgName: node.name } : {}),
  };
}

function clearDescendantResolvedSvgAssets(node: SimplifiedNode) {
  for (const child of node.children ?? []) {
    delete child.resolvedSvg;
    clearDescendantResolvedSvgAssets(child);
  }
}

function clearDescendantAssetAnnotations(node: SimplifiedNode) {
  for (const child of node.children ?? []) {
    delete child.resolvedSvg;
    delete child.resolvedImage;
    clearDescendantAssetAnnotations(child);
  }
}

function markVisualSvgRootAssets(design: SimplifiedDesign) {
  let markedCount = 0;
  const styleMap = design.globalVars?.styles ?? {};

  const walk = (node: SimplifiedNode) => {
    if (isVisualSvgRootCandidate(node, styleMap)) {
      ensureResolvedSvg(node);
      clearDescendantResolvedSvgAssets(node);
      markedCount += 1;
      return;
    }

    for (const child of node.children ?? []) {
      walk(child);
    }
  };

  for (const node of design.nodes ?? []) {
    walk(node);
  }

  if (markedCount > 0) {
    logger.info('Marked visual SVG asset roots: count=%d', markedCount);
  }
}

function annotateResolvedImageAssets(design: SimplifiedDesign) {
  const walk = (node: SimplifiedNode) => {
    if (node.id && hasImageFill(node)) {
      delete node.resolvedSvg;

      if (node.resolvedImage) {
        node.resolvedImage = {
          ...(getObjectRecord(node.resolvedImage) ?? {}),
          fallbackElement: getResolvedImageFallbackElement(node),
        };
      } else {
        node.resolvedImage = {
          usage: 'image-asset',
          fallbackElement: getResolvedImageFallbackElement(node),
          ...(node.name ? { imageName: node.name } : {}),
        };
      }
    }

    for (const child of node.children ?? []) {
      walk(child);
    }
  };

  for (const node of design.nodes ?? []) {
    walk(node);
  }
}

function annotateVisualAssetContainers(design: SimplifiedDesign) {
  const walk = (node: SimplifiedNode): boolean => {
    let childHasVisualAssetContainer = false;

    for (const child of node.children ?? []) {
      childHasVisualAssetContainer =
        walk(child) || childHasVisualAssetContainer;
    }

    if (!node.id || !isVisualAssetCandidate(node)) {
      return childHasVisualAssetContainer;
    }

    node.resolvedSvg = {
      usage: 'generic-svg',
      fallbackElement: 'img',
      ...(node.name ? { svgName: node.name } : {}),
    };

    // Once a parent visual container is exportable, prefer it over internal
    // vector fragments to preserve the Figma illustration as a single asset.
    if (childHasVisualAssetContainer) {
      node.children = (node.children ?? []).map((child) => {
        if (isVisualAssetCandidate(child)) {
          const { resolvedSvg: _resolvedSvg, ...restChild } = child;
          return restChild;
        }

        return child;
      });
    }

    return true;
  };

  for (const node of design.nodes ?? []) {
    walk(node);
  }
}

function isDividerSvgAssetSignal(node: SimplifiedNode) {
  const nodeType = String(node.type ?? '').toLowerCase();
  const nodeName = String(node.name ?? '')
    .trim()
    .toLowerCase();
  const isSvgLike =
    nodeType.includes('image-svg') ||
    nodeType.includes('vector') ||
    nodeType.includes('line') ||
    nodeType.includes('rectangle');

  if (!isSvgLike || hasImageFill(node) || hasTextDescendant(node)) {
    return false;
  }

  if (
    !/(^|\s)(divider|separator)(\s|$)/.test(nodeName) &&
    nodeName !== 'line'
  ) {
    return false;
  }

  const dimensions = getResolvedSvgExportDimensions(node);
  if (!dimensions) {
    return true;
  }

  const minDimension = Math.min(dimensions.width, dimensions.height);
  const maxDimension = Math.max(dimensions.width, dimensions.height);
  return minDimension <= 4 || maxDimension / Math.max(minDimension, 1) >= 8;
}

function removeDividerSvgAssets(design: SimplifiedDesign) {
  const walk = (node: SimplifiedNode) => {
    if (isDividerSvgAssetSignal(node)) {
      delete node.resolvedIcon;
      delete node.resolvedSvg;
    }

    for (const child of node.children ?? []) {
      walk(child);
    }
  };

  for (const node of design.nodes ?? []) {
    walk(node);
  }
}

function getBuiltinIconKeyForComponent(
  componentName: string,
  adapter: AnyDesignSystemAdapter,
) {
  const referenceKey = adapter.getReferenceKeyForComponent(componentName);
  return (
    adapter.iconMatcher?.getBuiltinIconKeyForComponent?.(
      componentName,
      referenceKey,
    ) ?? referenceKey
  );
}

function isAncestorCandidatePath(candidatePath: string, nodePath: string) {
  return nodePath.startsWith(`${candidatePath}.children[`);
}

function hasCandidateDescendantPath(
  candidatePaths: Set<string>,
  nodePath: string,
) {
  for (const candidatePath of Array.from(candidatePaths)) {
    if (
      candidatePath === nodePath ||
      isAncestorCandidatePath(nodePath, candidatePath)
    ) {
      return true;
    }
  }

  return false;
}

function getBuiltinIconScopeKey(
  nodePath: string,
  scopes: Array<{ nodePath: string; builtinIconKey: string }>,
) {
  let matchedScope: { nodePath: string; builtinIconKey: string } | undefined;

  for (const scope of scopes) {
    if (!isAncestorCandidatePath(scope.nodePath, nodePath)) {
      continue;
    }
    if (!matchedScope || scope.nodePath.length > matchedScope.nodePath.length) {
      matchedScope = scope;
    }
  }

  return matchedScope?.builtinIconKey;
}

function isBuiltinGenericSvgNode(
  node: SimplifiedNode,
  builtinIconKey: string,
  adapter: AnyDesignSystemAdapter,
) {
  const nodeName = typeof node.name === 'string' ? node.name.trim() : '';
  if (!nodeName || !adapter.iconMatcher?.isBuiltinGenericSvgName(nodeName)) {
    return false;
  }

  if (builtinIconKey === 'button' && !/loading/i.test(nodeName)) {
    return false;
  }

  if (hasTextDescendant(node) || hasImageFill(node)) {
    return false;
  }

  const dimensions = getResolvedSvgExportDimensions(node);
  if (!dimensions) {
    return true;
  }

  return Math.max(dimensions.width, dimensions.height) <= 32;
}

function removeBuiltinComponentIconAssets(
  design: SimplifiedDesign,
  candidateDetectionResult: FigmaCandidateDetectionResult,
  adapter: AnyDesignSystemAdapter,
) {
  const iconMatcher = adapter.iconMatcher;
  if (!iconMatcher) {
    return;
  }

  const scopes = candidateDetectionResult.nodes.flatMap((candidateNode) => {
    for (const candidate of candidateNode.candidates) {
      const builtinIconKey = getBuiltinIconKeyForComponent(
        candidate.component,
        adapter,
      );
      if (
        builtinIconKey &&
        iconMatcher.hasBuiltinIconsForReferenceKey(builtinIconKey)
      ) {
        return [
          {
            nodePath: candidateNode.nodePath,
            builtinIconKey,
          },
        ];
      }
    }
    return [];
  });

  if (!scopes.length) {
    return;
  }

  const walk = (node: SimplifiedNode, nodePath: string) => {
    const builtinIconKey = getBuiltinIconScopeKey(nodePath, scopes);

    if (builtinIconKey) {
      const resolvedIcon = getObjectRecord(node.resolvedIcon);
      const iconComponentName = String(resolvedIcon?.componentName ?? '');
      const iconUsage = String(resolvedIcon?.usage ?? '');
      const shouldRemoveResolvedIcon =
        !!resolvedIcon &&
        (iconMatcher.isBuiltinComponentIcon(
          builtinIconKey,
          iconComponentName,
        ) ||
          iconUsage === 'closable-signal' ||
          iconUsage === 'loading-signal' ||
          iconUsage === 'info-signal');
      const shouldRemoveResolvedSvg =
        !!node.resolvedSvg &&
        isBuiltinGenericSvgNode(node, builtinIconKey, adapter);

      if (shouldRemoveResolvedIcon || shouldRemoveResolvedSvg) {
        delete node.resolvedIcon;
        delete node.resolvedSvg;
      }
    }

    for (let index = 0; index < (node.children ?? []).length; index += 1) {
      const child = (node.children ?? [])[index];
      if (child) {
        walk(child, `${nodePath}.children[${index}]`);
      }
    }
  };

  for (let index = 0; index < (design.nodes ?? []).length; index += 1) {
    const node = (design.nodes ?? [])[index];
    if (node) {
      walk(node, `nodes[${index}]`);
    }
  }
}

type VisualAnnotationMetrics = {
  hasText: boolean;
  hasVisual: boolean;
  hasImageFill: boolean;
  imageFillDescendantCount: number;
  maskGroupDescendantCount: number;
  svgLikeDescendantCount: number;
  hasVisualAssetContainer: boolean;
};

function isVisualAssetCandidateFromMetrics(
  node: SimplifiedNode,
  metrics: VisualAnnotationMetrics,
  styleMap?: Record<string, unknown>,
): boolean {
  if (node.resolvedIcon || node.resolvedSvg || hasImageFill(node, styleMap)) {
    return false;
  }

  if (metrics.hasText || !metrics.hasVisual) {
    return false;
  }

  const layout = getNodeLayout(node, undefined, styleMap);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');

  if (!width || !height) {
    return false;
  }

  const aspectRatio = Math.max(width / height, height / width);

  return (
    width <= VISUAL_ASSET_MAX_DIMENSION &&
    height <= VISUAL_ASSET_MAX_DIMENSION &&
    aspectRatio <= VISUAL_ASSET_MAX_ASPECT_RATIO
  );
}

function isVisualSvgRootCandidateFromMetrics(
  node: SimplifiedNode,
  metrics: VisualAnnotationMetrics,
  styleMap?: Record<string, unknown>,
): boolean {
  if (!node.id || hasImageFill(node, styleMap) || metrics.hasText) {
    return false;
  }

  const type = String(node.type ?? '').toUpperCase();
  if (type === 'TEXT' || type === 'VECTOR') {
    return false;
  }

  if ((node.children ?? []).length === 0 && !node.resolvedSvg) {
    return false;
  }

  const layout = getNodeLayout(node, undefined, styleMap);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');
  if (!width || !height) {
    return false;
  }

  const aspectRatio = Math.max(width / height, height / width);
  if (
    width > VISUAL_ASSET_MAX_DIMENSION ||
    height > VISUAL_ASSET_MAX_DIMENSION ||
    aspectRatio > VISUAL_ASSET_MAX_ASPECT_RATIO
  ) {
    return false;
  }

  return metrics.svgLikeDescendantCount >= 2;
}

function isContainerLikeNode(node: SimplifiedNode): boolean {
  const type = String(node.type ?? '').toUpperCase();
  return (
    type === 'FRAME' ||
    type === 'GROUP' ||
    type === 'INSTANCE' ||
    type === 'COMPONENT'
  );
}

function isMaskGroupLikeNode(node: SimplifiedNode): boolean {
  return /mask\s*group/i.test(String(node.name ?? ''));
}

function hasDirectMaskGroupChild(node: SimplifiedNode): boolean {
  return (node.children ?? []).some((child) => isMaskGroupLikeNode(child));
}

function isStrongImageName(value: unknown): boolean {
  const name = String(value ?? '')
    .trim()
    .toLowerCase();
  return /^(image|img|picture|photo|banner|cover|thumbnail|illustration|artwork)(\b|[_\-\s]|$)/.test(
    name,
  );
}

function isVisualImageRootCandidateFromMetrics(
  node: SimplifiedNode,
  metrics: VisualAnnotationMetrics,
  styleMap?: Record<string, unknown>,
): boolean {
  if (!node.id || !isContainerLikeNode(node) || metrics.hasText) {
    return false;
  }

  if (!metrics.hasImageFill && metrics.imageFillDescendantCount === 0) {
    return false;
  }

  const layout = getNodeLayout(node, undefined, styleMap);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');
  if (!width || !height) {
    return false;
  }

  const maxDimension = Math.max(width, height);
  const minDimension = Math.min(width, height);
  if (maxDimension < IMAGE_ASSET_ROOT_MIN_DIMENSION || minDimension < 24) {
    return false;
  }

  return (
    metrics.hasImageFill ||
    metrics.maskGroupDescendantCount > 0 ||
    metrics.imageFillDescendantCount >= 2
  );
}

function isCompositeImageRootCandidateFromMetrics(
  node: SimplifiedNode,
  metrics: VisualAnnotationMetrics,
  styleMap?: Record<string, unknown>,
): boolean {
  if (!node.id || !isContainerLikeNode(node)) {
    return false;
  }

  if (!hasDirectMaskGroupChild(node) || !metrics.hasVisual) {
    return false;
  }

  const layout = getNodeLayout(node, undefined, styleMap);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');
  if (!width || !height) {
    return false;
  }

  return (
    width >= IMAGE_ASSET_ROOT_MIN_DIMENSION &&
    height >= COMPOSITE_IMAGE_ROOT_MIN_HEIGHT &&
    metrics.svgLikeDescendantCount >= 2
  );
}

function hasFlattenedImageUnsafeSignal(node: SimplifiedNode): boolean {
  const type = String(node.type ?? '').toUpperCase();
  const name = String(node.name ?? '').toLowerCase();

  if (node.componentId || node.componentProperties) {
    return true;
  }

  if (
    /button|input|select|dropdown|table|tabs?|checkbox|radio|switch|modal|form|menu|filter|search/.test(
      name,
    )
  ) {
    return true;
  }

  if (type === 'INSTANCE' || type === 'COMPONENT') {
    return true;
  }

  return (node.children ?? []).some((child) =>
    hasFlattenedImageUnsafeSignal(child),
  );
}

function isFlattenableVisualNode(node: SimplifiedNode): boolean {
  const type = String(node.type ?? '').toUpperCase();
  return (
    SVG_ELIGIBLE_TYPES.has(type) ||
    type === 'VECTOR' ||
    type === 'BOOLEAN_OPERATION' ||
    type === 'TEXT' ||
    type === 'FRAME' ||
    type === 'GROUP' ||
    hasImageFill(node)
  );
}

function isFlattenableVisualSubtree(node: SimplifiedNode): boolean {
  if (!isFlattenableVisualNode(node) || hasFlattenedImageUnsafeSignal(node)) {
    return false;
  }

  return (node.children ?? []).every((child) =>
    isFlattenableVisualSubtree(child),
  );
}

function getVisualPrimitiveChildCount(node: SimplifiedNode): number {
  return (node.children ?? []).filter((child) => {
    const type = String(child.type ?? '').toUpperCase();
    return (
      SVG_ELIGIBLE_TYPES.has(type) ||
      type === 'VECTOR' ||
      type === 'BOOLEAN_OPERATION' ||
      type === 'TEXT'
    );
  }).length;
}

function isFlattenedImageFrameCandidateFromMetrics(
  node: SimplifiedNode,
  nodePath: string,
  metrics: VisualAnnotationMetrics,
  candidatePaths: Set<string>,
  styleMap?: Record<string, unknown>,
): boolean {
  const type = String(node.type ?? '').toUpperCase();
  if (type !== 'FRAME' && type !== 'GROUP') {
    return false;
  }

  if (!node.id || !metrics.hasVisual) {
    return false;
  }

  const children = node.children ?? [];
  if (children.length < 1) {
    return false;
  }

  const hasStrongImageSignal =
    isStrongImageName(node.name) ||
    metrics.hasImageFill ||
    metrics.imageFillDescendantCount > 0 ||
    metrics.maskGroupDescendantCount > 0;

  if (
    !hasStrongImageSignal &&
    hasCandidateDescendantPath(candidatePaths, nodePath)
  ) {
    return false;
  }

  if (hasFlattenedImageUnsafeSignal(node)) {
    return false;
  }

  if (!isFlattenableVisualSubtree(node)) {
    return false;
  }

  if (hasStrongImageSignal) {
    return true;
  }

  if (children.length > FLATTENED_IMAGE_FRAME_MAX_DIRECT_CHILDREN) {
    return false;
  }

  const layout = getNodeLayout(node, undefined, styleMap);
  const width = getNumericDimension(layout, 'width');
  const height = getNumericDimension(layout, 'height');
  if (!width || !height) {
    return false;
  }

  return (
    Math.min(width, height) >= WEAK_FLATTENED_IMAGE_MIN_DIMENSION &&
    getVisualPrimitiveChildCount(node) >= 2
  );
}

function isClippedFrameSnapshotCandidate(
  node: SimplifiedNode,
  nodePath: string,
  metrics: VisualAnnotationMetrics,
  candidatePaths: Set<string>,
  styleMap?: Record<string, unknown>,
): boolean {
  if (node.clippedSnapshotCandidate !== true) {
    return false;
  }
  if (isClippedSnapshotUnsafeName(node.name)) {
    return false;
  }
  const hasExistingAssetSignal = Boolean(
    node.resolvedImage ||
      node.resolvedSvg ||
      node.resolvedIcon ||
      hasImageFill(node, styleMap) ||
      isFlattenedImageFrameCandidateFromMetrics(
        node,
        nodePath,
        metrics,
        candidatePaths,
        styleMap,
      ) ||
      isCompositeImageRootCandidateFromMetrics(node, metrics, styleMap) ||
      isVisualImageRootCandidateFromMetrics(node, metrics, styleMap),
  );
  if (hasExistingAssetSignal) {
    return false;
  }
  const type = String(node.type ?? '').toUpperCase();
  return (
    (type === 'FRAME' ||
      type === 'GROUP' ||
      type === 'INSTANCE' ||
      type === 'COMPONENT') &&
    metrics.hasVisual
  );
}

function isBuiltinGenericSvgNodeFromMetrics(
  node: SimplifiedNode,
  builtinIconKey: string,
  metrics: VisualAnnotationMetrics,
  adapter: AnyDesignSystemAdapter,
) {
  const nodeName = typeof node.name === 'string' ? node.name.trim() : '';
  if (!nodeName || !adapter.iconMatcher?.isBuiltinGenericSvgName(nodeName)) {
    return false;
  }

  if (builtinIconKey === 'button' && !/loading/i.test(nodeName)) {
    return false;
  }

  if (metrics.hasText || hasImageFill(node)) {
    return false;
  }

  const dimensions = getResolvedSvgExportDimensions(node);
  if (!dimensions) {
    return true;
  }

  return Math.max(dimensions.width, dimensions.height) <= 32;
}

function annotateVisualAssetsInSinglePass(
  design: SimplifiedDesign,
  candidateDetectionResult: FigmaCandidateDetectionResult,
  adapter: AnyDesignSystemAdapter,
) {
  const styleMap = design.globalVars?.styles ?? {};
  const metricsByNode = new WeakMap<SimplifiedNode, VisualAnnotationMetrics>();
  let markedRootCount = 0;
  const iconMatcher = adapter.iconMatcher;
  const candidatePaths = new Set(
    candidateDetectionResult.nodes.map(
      (candidateNode) => candidateNode.nodePath,
    ),
  );

  const scopes = candidateDetectionResult.nodes.flatMap((candidateNode) => {
    for (const candidate of candidateNode.candidates) {
      const builtinIconKey = getBuiltinIconKeyForComponent(
        candidate.component,
        adapter,
      );
      if (
        builtinIconKey &&
        iconMatcher?.hasBuiltinIconsForReferenceKey(builtinIconKey)
      ) {
        return [
          {
            nodePath: candidateNode.nodePath,
            builtinIconKey,
          },
        ];
      }
    }
    return [];
  });

  const walk = (
    node: SimplifiedNode,
    nodePath: string,
    skipVisualAnnotations: boolean,
  ): VisualAnnotationMetrics => {
    const childMetrics = (node.children ?? []).map((child, index) =>
      walk(
        child,
        `${nodePath}.children[${index}]`,
        skipVisualAnnotations || Boolean(node.resolvedIcon),
      ),
    );
    const nodeType = String(node.type ?? '').toUpperCase();
    const currentHasImageFill = hasImageFill(node, styleMap);
    const metrics: VisualAnnotationMetrics = {
      hasText:
        nodeType === 'TEXT' ||
        typeof node.text === 'string' ||
        childMetrics.some((child) => child.hasText),
      hasVisual:
        SVG_ELIGIBLE_TYPES.has(nodeType) ||
        nodeType === 'VECTOR' ||
        currentHasImageFill ||
        childMetrics.some((child) => child.hasVisual),
      hasImageFill: currentHasImageFill,
      imageFillDescendantCount: childMetrics.reduce(
        (count, child) =>
          count + (child.hasImageFill ? 1 : 0) + child.imageFillDescendantCount,
        0,
      ),
      maskGroupDescendantCount: childMetrics.reduce(
        (count, child, index) =>
          count +
          (isMaskGroupLikeNode((node.children ?? [])[index] as SimplifiedNode)
            ? 1
            : 0) +
          child.maskGroupDescendantCount,
        0,
      ),
      svgLikeDescendantCount: childMetrics.reduce(
        (count, child, index) =>
          count +
          (isSvgLikeNode((node.children ?? [])[index] as SimplifiedNode)
            ? 1
            : 0) +
          child.svgLikeDescendantCount,
        0,
      ),
      hasVisualAssetContainer: childMetrics.some(
        (child) => child.hasVisualAssetContainer,
      ),
    };
    metricsByNode.set(node, metrics);

    if (!skipVisualAnnotations) {
      if (!node.resolvedIcon && !node.resolvedSvg && isSvgLikeNode(node)) {
        ensureResolvedSvg(node);
      }

      if (isDividerSvgAssetSignal(node)) {
        delete node.resolvedIcon;
        delete node.resolvedSvg;
      }

      const builtinIconKey = getBuiltinIconScopeKey(nodePath, scopes);
      if (builtinIconKey && iconMatcher) {
        const resolvedIcon = getObjectRecord(node.resolvedIcon);
        const iconComponentName = String(resolvedIcon?.componentName ?? '');
        const iconUsage = String(resolvedIcon?.usage ?? '');
        const shouldRemoveResolvedIcon =
          !!resolvedIcon &&
          (iconMatcher.isBuiltinComponentIcon(
            builtinIconKey,
            iconComponentName,
          ) ||
            iconUsage === 'closable-signal' ||
            iconUsage === 'loading-signal' ||
            iconUsage === 'info-signal');
        const shouldRemoveResolvedSvg =
          !!node.resolvedSvg &&
          isBuiltinGenericSvgNodeFromMetrics(
            node,
            builtinIconKey,
            metrics,
            adapter,
          );

        if (shouldRemoveResolvedIcon || shouldRemoveResolvedSvg) {
          delete node.resolvedIcon;
          delete node.resolvedSvg;
        }
      }

      if (
        isFlattenedImageFrameCandidateFromMetrics(
          node,
          nodePath,
          metrics,
          candidatePaths,
          styleMap,
        )
      ) {
        delete node.resolvedSvg;
        node.resolvedImage = {
          ...(getObjectRecord(node.resolvedImage) ?? {}),
          usage: 'image-asset',
          fallbackElement: 'img',
          ...(node.name ? { imageName: node.name } : {}),
        };
        clearDescendantAssetAnnotations(node);
        metrics.hasVisualAssetContainer = true;
      } else if (
        isCompositeImageRootCandidateFromMetrics(node, metrics, styleMap)
      ) {
        delete node.resolvedSvg;
        node.resolvedImage = {
          ...(getObjectRecord(node.resolvedImage) ?? {}),
          usage: 'image-asset',
          fallbackElement: 'img',
          ...(node.name ? { imageName: node.name } : {}),
        };
        clearDescendantAssetAnnotations(node);
        metrics.hasVisualAssetContainer = true;
      } else if (
        isVisualImageRootCandidateFromMetrics(node, metrics, styleMap)
      ) {
        delete node.resolvedSvg;
        node.resolvedImage = {
          ...(getObjectRecord(node.resolvedImage) ?? {}),
          usage: 'image-asset',
          fallbackElement: getResolvedImageFallbackElement(node),
          ...(node.name ? { imageName: node.name } : {}),
        };
        clearDescendantAssetAnnotations(node);
        metrics.hasVisualAssetContainer = true;
      } else if (currentHasImageFill && node.id) {
        delete node.resolvedSvg;
        node.resolvedImage = {
          ...(getObjectRecord(node.resolvedImage) ?? {}),
          usage: 'image-asset',
          fallbackElement: getResolvedImageFallbackElement(node),
          ...(node.name ? { imageName: node.name } : {}),
        };
      } else if (isVisualAssetCandidateFromMetrics(node, metrics, styleMap)) {
        ensureResolvedSvg(node);
        metrics.hasVisualAssetContainer = true;

        if (childMetrics.some((child) => child.hasVisualAssetContainer)) {
          for (const child of node.children ?? []) {
            const childAnnotationMetrics = metricsByNode.get(child);
            if (
              childAnnotationMetrics &&
              isVisualAssetCandidateFromMetrics(
                child,
                childAnnotationMetrics,
                styleMap,
              )
            ) {
              delete child.resolvedSvg;
            }
          }
        }
      } else if (
        isClippedFrameSnapshotCandidate(
          node,
          nodePath,
          metrics,
          candidatePaths,
          styleMap,
        )
      ) {
        delete node.resolvedSvg;
        node.resolvedImage = {
          usage: 'clipped-frame-snapshot',
          fallbackElement: 'img',
          reason: 'clipped oversized child frame exported as image',
          ...(node.name ? { imageName: node.name } : {}),
        };
        node.children = [];
        metrics.hasVisualAssetContainer = true;
      }

      if (
        !node.resolvedImage &&
        isVisualSvgRootCandidateFromMetrics(node, metrics, styleMap)
      ) {
        ensureResolvedSvg(node);
        clearDescendantAssetAnnotations(node);
        markedRootCount += 1;
        metrics.hasVisualAssetContainer = true;
      }
    }

    return metrics;
  };

  for (let index = 0; index < (design.nodes ?? []).length; index += 1) {
    const node = (design.nodes ?? [])[index];
    if (node) {
      walk(node, `nodes[${index}]`, false);
    }
  }

  if (markedRootCount > 0) {
    logger.info('Marked visual SVG asset roots: count=%d', markedRootCount);
  }
}

function collectResolvedSvgRootNodes(
  nodes: SimplifiedNode[],
  styleMap?: Record<string, unknown>,
): SimplifiedNode[] {
  const result: SimplifiedNode[] = [];

  const walk = (node: SimplifiedNode) => {
    if (node.resolvedImage) {
      return;
    }

    if (isVisualSvgRootCandidate(node, styleMap)) {
      ensureResolvedSvg(node);
      clearDescendantAssetAnnotations(node);
      result.push(node);
      return;
    }

    const resolvedSvg = getObjectRecord(node.resolvedSvg);

    if (
      typeof node.id === 'string' &&
      resolvedSvg?.usage === 'generic-svg' &&
      !hasImageFill(node, styleMap) &&
      !isFragmentSvgNode(node) &&
      isResolvedSvgExportCandidate(node, styleMap)
    ) {
      result.push(node);
      return;
    }

    for (const child of node.children ?? []) {
      walk(child);
    }
  };

  for (const node of nodes) {
    walk(node);
  }

  return result.sort((left, right) => {
    const leftDimensions = getResolvedSvgExportDimensions(left, styleMap);
    const rightDimensions = getResolvedSvgExportDimensions(right, styleMap);
    const leftArea = leftDimensions
      ? leftDimensions.width * leftDimensions.height
      : 0;
    const rightArea = rightDimensions
      ? rightDimensions.width * rightDimensions.height
      : 0;

    return rightArea - leftArea;
  });
}

function collectResolvedImageNodes(
  nodes: SimplifiedNode[],
  styleMap?: Record<string, unknown>,
): SimplifiedNode[] {
  const result: SimplifiedNode[] = [];

  const walk = (node: SimplifiedNode) => {
    if (isResolvedImageExportCandidate(node)) {
      result.push(node);
      return;
    }

    for (const child of node.children ?? []) {
      walk(child);
    }
  };

  for (const node of nodes) {
    walk(node);
  }

  return result.sort((left, right) => {
    const leftDimensions = getResolvedSvgExportDimensions(left, styleMap);
    const rightDimensions = getResolvedSvgExportDimensions(right, styleMap);
    const leftArea = leftDimensions
      ? leftDimensions.width * leftDimensions.height
      : 0;
    const rightArea = rightDimensions
      ? rightDimensions.width * rightDimensions.height
      : 0;

    return rightArea - leftArea;
  });
}

async function attachResolvedSvgAssets(
  design: SimplifiedDesign,
  fileKey: string,
  token?: string,
) {
  const styleMap = design.globalVars?.styles ?? {};
  const svgNodes = collectResolvedSvgRootNodes(design.nodes ?? [], styleMap);
  const exportNodes = svgNodes.slice(0, MAX_RESOLVED_SVG_ASSET_EXPORTS);
  const nodeIds = exportNodes.flatMap((node) => (node.id ? [node.id] : []));

  if (!nodeIds.length) {
    return;
  }

  const svgNodeIds = exportNodes
    .filter((node) => !hasImageFill(node))
    .flatMap((node) => (node.id ? [node.id] : []));
  const pngNodeIds = exportNodes
    .filter((node) => hasImageFill(node))
    .flatMap((node) => (node.id ? [node.id] : []));
  const [svgImageUrls, pngImageUrls]: [
    Record<string, string>,
    Record<string, string>,
  ] = await Promise.all([
    svgNodeIds.length
      ? figmaService
          .getImageUrlsByNodes(
            fileKey,
            svgNodeIds,
            { format: 'svg', scale: 2 },
            token,
          )
          .catch((error) => {
            logger.warn('Failed to export resolved SVG assets: %s', error);
            return {} as Record<string, string>;
          })
      : Promise.resolve({} as Record<string, string>),
    pngNodeIds.length
      ? figmaService
          .getImageUrlsByNodes(
            fileKey,
            pngNodeIds,
            { format: 'png', scale: 2 },
            token,
          )
          .catch((error) => {
            logger.warn('Failed to export resolved PNG assets: %s', error);
            return {} as Record<string, string>;
          })
      : Promise.resolve({} as Record<string, string>),
  ]);

  const imageUrls = { ...svgImageUrls, ...pngImageUrls };
  logger.info(
    'Resolved SVG asset export: candidates=%d exported=%d',
    exportNodes.length,
    Object.keys(imageUrls).length,
  );

  for (const node of exportNodes) {
    if (!node.id || !imageUrls[node.id]) {
      continue;
    }

    const resolvedSvg = getObjectRecord(node.resolvedSvg);
    const layout = getNodeLayout(node, undefined, styleMap);

    node.resolvedSvg = {
      ...(resolvedSvg ?? {}),
      asset: {
        format: 'svg',
        ...(pngImageUrls[node.id] ? { format: 'png' as const } : {}),
        url: imageUrls[node.id],
        ...(getNumericDimension(layout, 'width') !== undefined
          ? { width: getNumericDimension(layout, 'width') }
          : {}),
        ...(getNumericDimension(layout, 'height') !== undefined
          ? { height: getNumericDimension(layout, 'height') }
          : {}),
        ...(getNumericDimension(layout, 'width') !== undefined &&
        getNumericDimension(layout, 'height') !== undefined
          ? {
              aspectRatio: Number(
                (
                  Math.max(
                    getNumericDimension(layout, 'width') || 1,
                    getNumericDimension(layout, 'height') || 1,
                  ) /
                  Math.min(
                    getNumericDimension(layout, 'width') || 1,
                    getNumericDimension(layout, 'height') || 1,
                  )
                ).toFixed(3),
              ),
            }
          : {}),
      },
    };
  }
}

async function attachResolvedImageAssets(
  design: SimplifiedDesign,
  fileKey: string,
  token?: string,
) {
  const styleMap = design.globalVars?.styles ?? {};
  const imageNodes = collectResolvedImageNodes(design.nodes ?? [], styleMap);
  const exportNodes = imageNodes.slice(0, MAX_RESOLVED_IMAGE_ASSET_EXPORTS);
  const nodeIds = exportNodes.flatMap((node) => (node.id ? [node.id] : []));

  if (!nodeIds.length) {
    return;
  }

  let imageUrls: Record<string, string> = {};

  try {
    imageUrls = await figmaService.getImageUrlsByNodes(
      fileKey,
      nodeIds,
      { format: 'png', scale: 2 },
      token,
    );
  } catch (error) {
    logger.warn('Failed to export resolved image assets: %s', error);
  }

  for (const node of exportNodes) {
    if (!node.id || !imageUrls[node.id]) {
      continue;
    }

    const resolvedImage = getObjectRecord(node.resolvedImage);
    const layout = getNodeLayout(node, undefined, styleMap);

    node.resolvedImage = {
      ...(resolvedImage ?? {}),
      fallbackElement: getResolvedImageFallbackElement(node),
      asset: {
        format: 'png',
        url: imageUrls[node.id],
        ...(getNumericDimension(layout, 'width') !== undefined
          ? { width: getNumericDimension(layout, 'width') }
          : {}),
        ...(getNumericDimension(layout, 'height') !== undefined
          ? { height: getNumericDimension(layout, 'height') }
          : {}),
        ...(getNumericDimension(layout, 'width') !== undefined &&
        getNumericDimension(layout, 'height') !== undefined
          ? {
              aspectRatio: Number(
                (
                  Math.max(
                    getNumericDimension(layout, 'width') || 1,
                    getNumericDimension(layout, 'height') || 1,
                  ) /
                  Math.min(
                    getNumericDimension(layout, 'width') || 1,
                    getNumericDimension(layout, 'height') || 1,
                  )
                ).toFixed(3),
              ),
            }
          : {}),
      },
    };
  }
}

function sanitizeAssetIdPart(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 24);
}

function getAssetRefTypePrefix(
  usageHint: ImageAssetUsageHint,
  source: 'resolvedImage' | 'resolvedSvg',
): string {
  if (usageHint === 'decorative-icon' || source === 'resolvedSvg')
    return 'icon';
  if (usageHint === 'thumbnail') return 'img';
  if (usageHint === 'illustration') return 'illus';
  if (usageHint === 'background') return 'bg';
  if (usageHint === 'connector') return 'line';
  return 'img';
}

function getShortAssetHash(value: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(36).slice(0, 6).padStart(6, '0');
}

function buildAssetRef(
  node: SimplifiedNode,
  source: 'resolvedImage' | 'resolvedSvg',
  usageHint: ImageAssetUsageHint,
  usedAssetRefs?: Set<string>,
): string {
  const namePart =
    typeof node.name === 'string' && node.name.trim()
      ? sanitizeAssetIdPart(node.name)
      : '';
  const baseRef = [
    getAssetRefTypePrefix(usageHint, source),
    namePart,
    getShortAssetHash(
      `${source}:${usageHint}:${node.id ?? ''}:${node.name ?? ''}`,
    ),
  ]
    .filter(Boolean)
    .join('_');
  if (!usedAssetRefs) return baseRef;

  let assetRef = baseRef;
  let suffix = 2;
  while (usedAssetRefs.has(assetRef)) {
    assetRef = `${baseRef}_${suffix}`;
    suffix += 1;
  }
  usedAssetRefs.add(assetRef);
  return assetRef;
}

function getAssetRecordFromResolved(
  resolved: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  return getObjectRecord(resolved?.asset);
}

function getAssetNumber(
  asset: Record<string, unknown> | undefined,
  key: 'width' | 'height' | 'aspectRatio',
): number | undefined {
  const value = asset?.[key];
  return typeof value === 'number' ? value : undefined;
}

function inferImageAssetUsageHint(input: {
  node: SimplifiedNode;
  source: 'resolvedImage' | 'resolvedSvg';
  asset: Record<string, unknown> | undefined;
  fallbackElement?: unknown;
}): ImageAssetUsageHint {
  const name = `${input.node.name ?? ''}`.toLowerCase();
  const width = getAssetNumber(input.asset, 'width');
  const height = getAssetNumber(input.asset, 'height');
  const aspectRatio = getAssetNumber(input.asset, 'aspectRatio');
  const maxDimension = Math.max(width ?? 0, height ?? 0);
  const minDimension = Math.min(width ?? 0, height ?? 0);

  if (input.fallbackElement === 'backgroundImage') {
    return 'background';
  }

  if (/avatar|profile|portrait|user/.test(name)) {
    return 'avatar';
  }

  if (/badge|tier|level|medal|rank|ranking|reward/.test(name)) {
    return 'badge';
  }

  if (/logo|brand/.test(name)) {
    return 'logo';
  }

  if (/progress|process|track|bar/.test(name)) {
    return 'progress';
  }

  if (/connector|divider|line|separator/.test(name)) {
    return 'connector';
  }

  if (aspectRatio !== undefined && aspectRatio > 3) {
    return height !== undefined && height <= 24 ? 'connector' : 'background';
  }

  if (width !== undefined && height !== undefined) {
    if (maxDimension <= 32 && minDimension <= 32) {
      return 'decorative-icon';
    }

    if (aspectRatio !== undefined && aspectRatio <= 1.5) {
      if (maxDimension <= 128) {
        return input.source === 'resolvedSvg' ? 'decorative-icon' : 'thumbnail';
      }

      return 'illustration';
    }
  }

  return 'unknown';
}

function attachImageAssetManifest(design: SimplifiedDesign) {
  const images: Record<string, ImageAssetManifestItem> = {};
  const bindings: AssetBinding[] = [];
  const usedAssetRefs = new Set<string>();

  const walk = (node: SimplifiedNode, path: string) => {
    const candidates: Array<{
      source: 'resolvedImage' | 'resolvedSvg';
      resolved: Record<string, unknown> | undefined;
      bindingField: 'resolvedImage' | 'resolvedSvg';
    }> = [
      {
        source: 'resolvedImage',
        resolved: getObjectRecord(node.resolvedImage),
        bindingField: 'resolvedImage',
      },
      {
        source: 'resolvedSvg',
        resolved: getObjectRecord(node.resolvedSvg),
        bindingField: 'resolvedSvg',
      },
    ];

    for (const candidate of candidates) {
      const resolved = candidate.resolved;
      const asset = getAssetRecordFromResolved(candidate.resolved);
      const url = asset?.url;

      if (!node.id || !resolved || typeof url !== 'string' || !url) {
        continue;
      }

      const fallbackElement = resolved.fallbackElement;
      const usageHint = inferImageAssetUsageHint({
        node,
        source: candidate.source,
        asset,
        fallbackElement,
      });
      const assetRef = buildAssetRef(
        node,
        candidate.source,
        usageHint,
        usedAssetRefs,
      );

      resolved.assetRef = assetRef;
      node[candidate.bindingField] = resolved;

      images[assetRef] = {
        url,
        ...(typeof asset.format === 'string'
          ? { format: asset.format as ImageAssetManifestItem['format'] }
          : {}),
        ...(getAssetNumber(asset, 'width') !== undefined
          ? { width: getAssetNumber(asset, 'width') }
          : {}),
        ...(getAssetNumber(asset, 'height') !== undefined
          ? { height: getAssetNumber(asset, 'height') }
          : {}),
        nodePath: path,
      };

      bindings.push({
        targetPath: `${path}.${candidate.bindingField}.assetRef`,
        assetRef,
      });
    }

    for (let index = 0; index < (node.children ?? []).length; index += 1) {
      const child = (node.children ?? [])[index];
      if (child) {
        walk(child, `${path}.children[${index}]`);
      }
    }
  };

  for (let index = 0; index < (design.nodes ?? []).length; index += 1) {
    const node = (design.nodes ?? [])[index];
    if (node) {
      walk(node, `nodes[${index}]`);
    }
  }

  if (Object.keys(images).length > 0) {
    design.assets = {
      ...(design.assets ?? {}),
      images,
    };
    design.assetBindings = bindings;
  }
}

export const getFigmaNodeDataTools = createTool({
  id: 'get-figma-node-data',
  description: 'Get figma node data from a Figma URL',
  inputSchema: getFigmaNodeDataToolsInputSchema,
  outputSchema: z.object({
    figmaNodeData: z.string().describe('Figma node data in YAML format'),
    rootBounds: z
      .object({
        x: z.number(),
        y: z.number(),
        width: z.number(),
        height: z.number(),
      })
      .optional()
      .describe('Absolute bounds of the requested root Figma node'),
    candidateComponents: z
      .array(z.string())
      .describe('Candidate component names detected from figma data'),
    candidateNodes: z
      .array(
        z.object({
          nodePath: z
            .string()
            .describe('Path of the matched node in the simplified figma tree'),
          nodeName: z.string().optional().describe('Original node name'),
          candidates: z.array(
            z.object({
              component: z
                .string()
                .describe('Detected candidate component name'),
              score: z
                .number()
                .describe('Detection score for this component on the node'),
              reasons: z
                .array(z.string())
                .describe('Reasons that contributed to the score'),
            }),
          ),
        }),
      )
      .describe('Detailed candidate matches for each figma node'),
    candidateDebugNodes: z
      .array(
        z.object({
          nodePath: z
            .string()
            .describe('Path of the node in the simplified figma tree'),
          nodeName: z.string().optional().describe('Original node name'),
          candidates: z.array(
            z.object({
              component: z
                .string()
                .describe(
                  'Candidate component name before threshold/filtering',
                ),
              score: z
                .number()
                .describe('Raw detection score for this component on the node'),
              reasons: z
                .array(z.string())
                .describe('Reasons that contributed to the raw score'),
            }),
          ),
        }),
      )
      .describe('Raw node-level candidate matches before threshold/filtering'),
    matchedIcons: z
      .array(
        z.object({
          nodeName: z.string().describe('Original matched icon node name'),
          iconName: z.string().describe('Matched icon manifest name'),
          componentName: z.string().describe('Resolved icon component name'),
          importSource: z
            .string()
            .optional()
            .describe('Package to import the resolved icon component from'),
          usage: z.string().describe('Resolved icon usage'),
        }),
      )
      .describe('Icon registry matches extracted from IMAGE-SVG/VECTOR nodes'),
    repeatedGroups: z
      .array(
        z.object({
          groupType: z
            .enum(['list', 'card-list'])
            .describe('Repeated group type'),
          parentPath: z.string().describe('Path of repeated group parent'),
          itemPaths: z.array(z.string()).describe('All repeated item paths'),
          sampleItemPaths: z
            .array(z.string())
            .describe('Sample repeated item paths'),
          itemCount: z.number().describe('Number of repeated items in group'),
          confidence: z
            .number()
            .describe('Confidence score for repeated group abstraction'),
        }),
      )
      .describe('Detected repeated list/card-list groups'),
    tableRowClipSummaries: z
      .array(
        z.object({
          tablePath: z.string().describe('Path of the normalized Table owner'),
          rowContainerPath: z
            .string()
            .describe('Path of the repeated row container inside the Table'),
          originalRowCount: z
            .number()
            .describe('Total number of repeated rows before clipping'),
          preservedRowCount: z
            .number()
            .describe('Number of representative rows preserved in figmaNodeData'),
          sampleRowPaths: z
            .array(z.string())
            .describe('Representative row paths preserved in the compacted design'),
          bindingKind: z
            .string()
            .describe('Preferred data binding mode for the normalized table'),
        }),
      )
      .describe('Table row clipping summaries produced by HiUI normalization'),
    discreteStatusBlockGroups: z
      .array(
        z.object({
          parentPath: z
            .string()
            .describe('Path of the discrete status group parent'),
          itemPaths: z
            .array(z.string())
            .describe('All discrete status item paths'),
          itemNames: z
            .array(z.string())
            .describe('Displayed item names in order'),
          itemWidths: z
            .array(z.number())
            .describe('Detected width of each item'),
          selectedKey: z
            .string()
            .optional()
            .describe('Selected variant/status key'),
          selectedIndex: z.number().optional().describe('Selected item index'),
          sourceProp: z
            .string()
            .optional()
            .describe('Source component property name'),
          hasContainerBackground: z
            .boolean()
            .describe(
              'Whether the outer container has its own background/fill',
            ),
        }),
      )
      .describe(
        'Detected discrete status block groups from instance/frame variants',
      ),
    metricCardGroupHeaders: z
      .array(
        z.object({
          compositePath: z
            .string()
            .describe('Path of the composite block hosting the header'),
          headerPath: z
            .string()
            .describe('Path of the top header bar (title + switch)'),
          titleText: z
            .string()
            .optional()
            .describe('Header title text -> SimpleMetricCardGroup.title'),
          titleId: z.string().optional().describe('Figma node id of the title'),
          switchPath: z.string().describe('Path of the header switch'),
          switchId: z
            .string()
            .optional()
            .describe('Figma node id of the switch'),
          switchLabel: z
            .string()
            .optional()
            .describe('Switch label -> actions switcher suffix'),
          firstGroupPath: z
            .string()
            .describe('Path of the first metric card group below the header'),
        }),
      )
      .describe(
        'Composite top header bars that belong to the SimpleMetricCardGroup below as title + actions',
      ),
  }),
  async execute(inputData, context) {
    const startedAt = Date.now();
    let lastMarkAt = startedAt;
    const timings: Record<string, number> = {};
    const markTiming = (name: string) => {
      const now = Date.now();
      timings[name] = now - lastMarkAt;
      lastMarkAt = now;
    };
    let requestMeta:
      | {
          fileKey?: string;
          nodeId?: string;
          nodeType?: string;
          nodeName?: string;
          hasDocument?: boolean;
        }
      | undefined;

    try {
      const { fileKey, nodeId } = parseFigmaUrl(inputData.figmaUrl);
      const privateToken = getPrivateFigmaToken(context);
      const rawApiResponse = await figmaService.getRawNode(
        fileKey,
        nodeId,
        privateToken,
      );
      markTiming('figmaRawFetchMs');

      const nodeEntry = rawApiResponse?.nodes?.[nodeId];
      const responseNodeKeys = Object.keys(rawApiResponse?.nodes ?? {});
      requestMeta = {
        fileKey,
        nodeId,
        nodeType: (nodeEntry as any)?.document?.type,
        nodeName: (nodeEntry as any)?.document?.name,
        hasDocument: Boolean((nodeEntry as any)?.document),
      };

      if (!nodeEntry) {
        throw new Error(
          `Figma API response does not contain node '${nodeId}'. ` +
            `Returned node keys: ${responseNodeKeys.slice(0, 5).join(', ') || 'none'}. ` +
            `Figma error: ${(rawApiResponse as any)?.err || 'none'}. ` +
            'Please confirm the figmaUrl points to an accessible node and the Figma token has permission.',
        );
      }

      if ('document' in nodeEntry && !nodeEntry.document) {
        throw new Error(
          `Figma node '${nodeId}' does not contain a document tree. ` +
            'The node may be inaccessible, deleted, or not fully returned by the Figma API.',
        );
      }

      if (
        'document' in nodeEntry &&
        Array.isArray((nodeEntry as any).document)
      ) {
        throw new Error(
          `Figma node '${nodeId}' returned an unexpected document structure.`,
        );
      }

      // Use unified design extraction (handles nodes + components consistently)
      const simplifiedDesign = simplifyRawFigmaObject(
        rawApiResponse,
        allExtractors,
        {
          afterChildren: (node, result, children) => {
            if (typeof node.id === 'string') {
              result.id = node.id;
            }

            if (isRawClippedFrameSnapshotCandidate(node)) {
              (
                result as unknown as Record<string, unknown>
              ).clippedSnapshotCandidate = true;
            }

            if (
              (node.type === 'FRAME' ||
                node.type === 'GROUP' ||
                node.type === 'INSTANCE') &&
              !hasFigmaComponentIdentity(node) &&
              canCollapseContainerToSvg(node, result, children)
            ) {
              // Collapse to IMAGE-SVG and omit children
              result.type = 'IMAGE-SVG';
              return [];
            }

            // Include all children normally
            return children;
          },
        },
      );
      markTiming('simplifyMs');
      const designSystemAdapter = getDesignSystemAdapterFromContext(context);
      const enableRepeatedStructureNormalization =
        inputData.enableRepeatedStructureNormalization ??
        (designSystemAdapter.id === 'hiui' &&
          designSystemAdapter.repeatedStructureNormalization?.enabledByDefault !==
            false);
      const candidateDetectionResult =
        designSystemAdapter.detectComponentCandidates(
          simplifiedDesign as unknown as Parameters<
            typeof designSystemAdapter.detectComponentCandidates
          >[0],
        );
      markTiming('candidateDetectionMs');
      designSystemAdapter.iconMatcher?.annotateResolvedIconsInPayload(
        simplifiedDesign as unknown as Parameters<
          NonNullable<
            typeof designSystemAdapter.iconMatcher
          >['annotateResolvedIconsInPayload']
        >[0],
      );
      annotateVisualAssetsInSinglePass(
        simplifiedDesign as unknown as SimplifiedDesign,
        candidateDetectionResult,
        designSystemAdapter,
      );
      markTiming('annotationMs');
      await Promise.all([
        attachResolvedSvgAssets(
          simplifiedDesign as unknown as SimplifiedDesign,
          fileKey,
          privateToken,
        ),
        attachResolvedImageAssets(
          simplifiedDesign as unknown as SimplifiedDesign,
          fileKey,
          privateToken,
        ),
      ]);
      markTiming('assetExportMs');
      attachImageAssetManifest(simplifiedDesign as unknown as SimplifiedDesign);
      const matchedIcons =
        designSystemAdapter.iconMatcher?.collectMatchedIconsFromPayload(
          simplifiedDesign as unknown as Parameters<
            NonNullable<
              typeof designSystemAdapter.iconMatcher
            >['collectMatchedIconsFromPayload']
          >[0],
        ) ?? [];
      const repeatedGroups = detectRepeatedGroups(
        simplifiedDesign as unknown as Parameters<
          typeof detectRepeatedGroups
        >[0],
      );
      const discreteStatusBlockGroups = detectDiscreteStatusBlockGroups(
        simplifiedDesign as unknown as Parameters<
          typeof detectDiscreteStatusBlockGroups
        >[0],
      );
      const metricCardGroupHeaders =
        designSystemAdapter.id === 'm4b'
          ? detectMetricCardGroupHeaders(
              simplifiedDesign as unknown as Parameters<
                typeof detectMetricCardGroupHeaders
              >[0],
            )
          : [];
      markTiming('postDetectionMs');
      (context as any)?.tracingContext?.currentSpan?.update?.({
        metadata: {
          candidateComponents: candidateDetectionResult.components,
          matchedIcons: matchedIcons.map((icon) => icon.iconName),
          repeatedGroups: repeatedGroups.map((group) => ({
            groupType: group.groupType,
            itemCount: group.itemCount,
            confidence: group.confidence,
          })),
          discreteStatusBlockGroups: discreteStatusBlockGroups.map((group) => ({
            selectedKey: group.selectedKey,
            itemNames: group.itemNames,
          })),
          metricCardGroupHeaders: metricCardGroupHeaders.map((header) => ({
            titleText: header.titleText,
            switchLabel: header.switchLabel,
            switchId: header.switchId,
          })),
        },
      });
      let normalizedDesign =
        simplifiedDesign as unknown as SimplifiedDesign;
      let tableRowClipSummaries: Array<{
        tablePath: string;
        rowContainerPath: string;
        originalRowCount: number;
        preservedRowCount: number;
        sampleRowPaths: string[];
        bindingKind: string;
      }> = [];

      if (enableRepeatedStructureNormalization && designSystemAdapter.id === 'hiui') {
        const normalizationResult = normalizeHiuiRepeatedStructures({
          design: normalizedDesign,
          repeatedGroups: repeatedGroups as Parameters<
            typeof normalizeHiuiRepeatedStructures
          >[0]['repeatedGroups'],
          candidateNodes: candidateDetectionResult.nodes,
        });
        normalizedDesign = normalizationResult.design as SimplifiedDesign;
        tableRowClipSummaries = normalizationResult.tableRowClipSummaries;
      }

      const compactedDesign = compactFigmaSourceData(normalizedDesign);
      const rootBounds =
        getRawNodeBounds((nodeEntry as any)?.document) ??
        getSimplifiedRootBounds(
          simplifiedDesign as unknown as SimplifiedDesign,
        );
      if (rootBounds) {
        compactedDesign.rootBounds = rootBounds;
      }
      const figmaNodeData = yaml.dump(compactedDesign);
      markTiming('compactYamlMs');
      logger.info(
        'Figma node parse timings: meta=%j timings=%j totalMs=%d',
        requestMeta,
        timings,
        Date.now() - startedAt,
      );
      return {
        figmaNodeData,
        rootBounds,
        candidateComponents: candidateDetectionResult.components,
        candidateNodes: candidateDetectionResult.nodes,
        candidateDebugNodes: candidateDetectionResult.debugNodes,
        matchedIcons,
        repeatedGroups,
        tableRowClipSummaries,
        discreteStatusBlockGroups,
        metricCardGroupHeaders,
      };
    } catch (error) {
      logger.error(
        'Error fetching Figma node data: %s, meta=%j',
        error,
        requestMeta,
      );
      throw error;
    }
  },
});
