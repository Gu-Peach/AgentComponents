import { create } from "zustand";
import { mockCatalogAssets, mockInitialSceneObjects } from "@/mocks/catalog";
import type {
  AssetCategory,
  CatalogAsset,
  LayoutSizes,
  LogLevel,
  PanelState,
  RuntimeAnimationAction,
  RuntimeDeviceVisualState,
  SceneDocumentRecord,
  SceneObject,
  Transform3D,
  Vector3Tuple,
} from "@/types/scene";

const initialPanels: PanelState = {
  headerCollapsed: false,
  leftCollapsed: false,
  rightCollapsed: false,
  footerCollapsed: false,
};

const initialLayout: LayoutSizes = {
  leftWidth: 330,
  rightWidth: 340,
  footerHeight: 190,
};

let idCounter = 0;

function createId(prefix: string) {
  idCounter += 1;
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}_${Date.now()}_${idCounter}`;
}

function nowTime() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function makeLog(level: LogLevel, message: string) {
  return { id: createId("log"), level, message, timestamp: nowTime() };
}

const initialLogs = [
  { id: "initial-log-1", level: "success" as const, message: "frontend workspace initialized", timestamp: "00:00:00" },
  { id: "initial-log-2", level: "info" as const, message: "mock catalog loaded: device models + scene models", timestamp: "00:00:00" },
  { id: "initial-log-3", level: "info" as const, message: "R3F viewport ready for object selection and transform edits", timestamp: "00:00:00" },
];

interface WorkspaceState {
  projectName: string;
  panels: PanelState;
  layout: LayoutSizes;
  assets: CatalogAsset[];
  assetCategory: AssetCategory;
  assetQuery: string;
  selectedAssetId: string | null;
  sceneObjects: SceneObject[];
  selectedObjectId: string | null;
  logs: ReturnType<typeof makeLog>[];
  runtimeRunId: string | null;
  runtimeSceneDocument: SceneDocumentRecord | null;
  runtimeGlbLoaded: boolean;
  runtimeGlbObjectIds: string[];
  activeRuntimeActions: RuntimeAnimationAction[];
  runtimeDeviceVisuals: Record<string, RuntimeDeviceVisualState>;
  seenRuntimeEventRefs: string[];
  setAssetCategory: (category: AssetCategory) => void;
  setAssetQuery: (query: string) => void;
  selectAsset: (assetId: string) => void;
  togglePanel: (panel: keyof PanelState) => void;
  setLayoutSize: (key: keyof LayoutSizes, value: number) => void;
  selectSceneObject: (objectId: string | null) => void;
  addAssetToScene: (assetId: string, position?: Vector3Tuple) => void;
  updateSceneObject: (objectId: string, patch: Partial<Omit<SceneObject, "id">>) => void;
  updateSceneObjectTransform: (objectId: string, patch: Partial<Transform3D>) => void;
  applyRuntimeObjectTransform: (objectId: string, patch: Partial<Transform3D>) => void;
  replaceSceneObjects: (objects: SceneObject[]) => void;
  setRuntimeRunId: (runId: string | null) => void;
  setRuntimeSceneDocument: (document: SceneDocumentRecord | null) => void;
  setRuntimeGlbLoaded: (loaded: boolean) => void;
  setRuntimeGlbObjectIds: (objectIds: string[]) => void;
  startRuntimeAction: (action: RuntimeAnimationAction) => void;
  updateRuntimeAction: (actionId: string, patch: Partial<RuntimeAnimationAction>) => void;
  completeRuntimeAction: (actionId: string, status?: "done" | "failed") => RuntimeAnimationAction | undefined;
  setRuntimeDeviceVisual: (objectId: string, visual: RuntimeDeviceVisualState | null) => void;
  markRuntimeEventSeen: (eventRef: string) => void;
  hasSeenRuntimeEvent: (eventRef: string) => boolean;
  appendLog: (level: LogLevel, message: string) => void;
  clearLogs: () => void;
  resetWorkspace: () => void;
}

function getPlacement(index: number): Vector3Tuple {
  const column = index % 4;
  const row = Math.floor(index / 4);
  return [-3 + column * 1.7, 0.2, 2.7 + row * 1.2];
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  projectName: "AgentComponents · VC Workspace",
  panels: initialPanels,
  layout: initialLayout,
  assets: mockCatalogAssets,
  assetCategory: "device_model",
  assetQuery: "",
  selectedAssetId: mockCatalogAssets[0]?.id ?? null,
  sceneObjects: mockInitialSceneObjects,
  selectedObjectId: mockInitialSceneObjects[0]?.id ?? null,
  logs: initialLogs,
  runtimeRunId: process.env.NEXT_PUBLIC_SIMULATION_RUN_ID ?? null,
  runtimeSceneDocument: null,
  runtimeGlbLoaded: false,
  runtimeGlbObjectIds: [],
  activeRuntimeActions: [],
  runtimeDeviceVisuals: {},
  seenRuntimeEventRefs: [],

  setAssetCategory: (category) => set({ assetCategory: category }),
  setAssetQuery: (query) => set({ assetQuery: query }),
  selectAsset: (assetId) => {
    const asset = get().assets.find((item) => item.id === assetId);
    set((state) => ({
      selectedAssetId: assetId,
      logs: asset ? [...state.logs, makeLog("info", `selected asset: ${asset.name}`)] : state.logs,
    }));
  },
  togglePanel: (panel) => {
    set((state) => ({
      panels: { ...state.panels, [panel]: !state.panels[panel] },
      logs: [...state.logs, makeLog("info", `panel toggled: ${panel}`)],
    }));
  },
  setLayoutSize: (key, value) => set((state) => ({ layout: { ...state.layout, [key]: value } })),
  selectSceneObject: (objectId) => {
    const object = get().sceneObjects.find((item) => item.id === objectId);
    set((state) => ({
      selectedObjectId: objectId,
      logs: object ? [...state.logs, makeLog("info", `selected scene object: ${object.name}`)] : state.logs,
    }));
  },
  addAssetToScene: (assetId, position) => {
    const asset = get().assets.find((item) => item.id === assetId);
    if (!asset) return;
    const index = get().sceneObjects.length;
    const object: SceneObject = {
      id: createId(asset.type),
      assetId: asset.id,
      name: `${asset.name} ${index + 1}`,
      type: asset.type,
      description: asset.description,
      transform: {
        position: position ?? getPlacement(index),
        rotation: [0, 0, 0],
        scale: [1, 1, 1],
      },
      dimensions: asset.defaultDimensions,
      color: asset.color,
      createdFrom: asset.source === "mock" ? "mock catalog" : asset.apiRef ?? "api",
    };
    set((state) => ({
      sceneObjects: [...state.sceneObjects, object],
      selectedObjectId: object.id,
      selectedAssetId: asset.id,
      logs: [...state.logs, makeLog("success", `added ${object.name} to scene`)],
    }));
  },
  updateSceneObject: (objectId, patch) => {
    set((state) => ({
      sceneObjects: state.sceneObjects.map((object) => (object.id === objectId ? { ...object, ...patch } : object)),
      logs: [...state.logs, makeLog("info", `updated object properties: ${objectId}`)],
    }));
  },
  updateSceneObjectTransform: (objectId, patch) => {
    set((state) => ({
      sceneObjects: state.sceneObjects.map((object) =>
        object.id === objectId ? { ...object, transform: { ...object.transform, ...patch } } : object,
      ),
      logs: [...state.logs, makeLog("info", `updated transform: ${objectId}`)],
    }));
  },
  applyRuntimeObjectTransform: (objectId, patch) => {
    set((state) => ({
      sceneObjects: state.sceneObjects.map((object) =>
        object.id === objectId ? { ...object, transform: { ...object.transform, ...patch } } : object,
      ),
    }));
  },
  replaceSceneObjects: (objects) => set((state) => ({
    sceneObjects: objects,
    selectedObjectId: objects[0]?.id ?? null,
    activeRuntimeActions: [],
    runtimeDeviceVisuals: {},
    seenRuntimeEventRefs: [],
    runtimeGlbLoaded: false,
    runtimeGlbObjectIds: [],
    logs: [...state.logs, makeLog("success", `scene document loaded: ${objects.length} objects`)],
  })),
  setRuntimeRunId: (runId) => set({ runtimeRunId: runId }),
  setRuntimeSceneDocument: (document) => set({ runtimeSceneDocument: document, runtimeGlbLoaded: false, runtimeGlbObjectIds: [] }),
  setRuntimeGlbLoaded: (loaded) => set({ runtimeGlbLoaded: loaded }),
  setRuntimeGlbObjectIds: (objectIds) => set({ runtimeGlbObjectIds: objectIds }),
  startRuntimeAction: (action) => {
    set((state) => {
      if (state.activeRuntimeActions.some((item) => item.actionId === action.actionId)) return {};
      return {
        activeRuntimeActions: [...state.activeRuntimeActions, action],
        runtimeDeviceVisuals: {
          ...state.runtimeDeviceVisuals,
          [action.instanceId]: {
            ...state.runtimeDeviceVisuals[action.instanceId],
            activeActionId: action.actionId,
            armPhase: action.kind === "robot_pick_place" ? "approach" : state.runtimeDeviceVisuals[action.instanceId]?.armPhase,
          },
        },
        logs: [...state.logs, makeLog("success", `runtime action started: ${action.instanceId}.${action.behaviorId}`)],
      };
    });
  },
  updateRuntimeAction: (actionId, patch) => {
    set((state) => ({
      activeRuntimeActions: state.activeRuntimeActions.map((action) =>
        action.actionId === actionId ? { ...action, ...patch } : action,
      ),
    }));
  },
  completeRuntimeAction: (actionId, status = "done") => {
    const action = get().activeRuntimeActions.find((item) => item.actionId === actionId);
    if (!action) return undefined;
    set((state) => {
      const nextVisuals = { ...state.runtimeDeviceVisuals };
      const hasAnotherActionOnDevice = state.activeRuntimeActions.some(
        (item) => item.actionId !== actionId && item.instanceId === action.instanceId,
      );
      if (hasAnotherActionOnDevice) {
        nextVisuals[action.instanceId] = { ...nextVisuals[action.instanceId], activeActionId: undefined };
      } else {
        nextVisuals[action.instanceId] = {
          ...nextVisuals[action.instanceId],
          activeActionId: undefined,
          beltOffset: 0,
          armPhase: "idle",
          shoulder: 0,
          elbow: 0,
          wrist: 0,
          gripperClosed: false,
        };
      }
      return {
        activeRuntimeActions: state.activeRuntimeActions.filter((item) => item.actionId !== actionId),
        runtimeDeviceVisuals: nextVisuals,
        logs: [
          ...state.logs,
          makeLog(status === "done" ? "success" : "error", `runtime action ${status}: ${action.instanceId}.${action.behaviorId}`),
        ],
      };
    });
    return { ...action, status };
  },
  setRuntimeDeviceVisual: (objectId, visual) => {
    set((state) => {
      const nextVisuals = { ...state.runtimeDeviceVisuals };
      if (visual === null) {
        delete nextVisuals[objectId];
      } else {
        nextVisuals[objectId] = { ...nextVisuals[objectId], ...visual };
      }
      return { runtimeDeviceVisuals: nextVisuals };
    });
  },
  markRuntimeEventSeen: (eventRef) => {
    set((state) =>
      state.seenRuntimeEventRefs.includes(eventRef)
        ? {}
        : { seenRuntimeEventRefs: [...state.seenRuntimeEventRefs, eventRef] },
    );
  },
  hasSeenRuntimeEvent: (eventRef) => get().seenRuntimeEventRefs.includes(eventRef),
  appendLog: (level, message) => set((state) => ({ logs: [...state.logs, makeLog(level, message)] })),
  clearLogs: () => set({ logs: [makeLog("info", "terminal cleared")] }),
  resetWorkspace: () =>
    set({
      panels: initialPanels,
      layout: initialLayout,
      assetCategory: "device_model",
      assetQuery: "",
      selectedAssetId: mockCatalogAssets[0]?.id ?? null,
      sceneObjects: mockInitialSceneObjects,
      selectedObjectId: mockInitialSceneObjects[0]?.id ?? null,
      logs: initialLogs,
      runtimeRunId: process.env.NEXT_PUBLIC_SIMULATION_RUN_ID ?? null,
      runtimeSceneDocument: null,
      runtimeGlbLoaded: false,
      runtimeGlbObjectIds: [],
      activeRuntimeActions: [],
      runtimeDeviceVisuals: {},
      seenRuntimeEventRefs: [],
    }),
}));

export function filterCatalogAssets(assets: CatalogAsset[], category: AssetCategory, rawQuery: string) {
  const query = rawQuery.trim().toLowerCase();
  return assets.filter((asset) => {
    const matchesCategory = asset.category === category;
    const matchesQuery =
      query.length === 0 ||
      asset.name.toLowerCase().includes(query) ||
      asset.description.toLowerCase().includes(query) ||
      asset.tags.some((tag) => tag.toLowerCase().includes(query));
    return matchesCategory && matchesQuery;
  });
}

export function selectFilteredAssets(state: WorkspaceState) {
  return filterCatalogAssets(state.assets, state.assetCategory, state.assetQuery);
}
