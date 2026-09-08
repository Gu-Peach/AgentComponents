import { mockCatalogAssets, mockInitialSceneObjects } from "@/mocks/catalog";
import { sceneDocumentToSceneObjects } from "@/lib/scene-document";
import type { CatalogAsset, RuntimeBehaviorEvent, SceneDocumentRecord, SceneObject } from "@/types/scene";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface FrontendApiClient {
  listCatalogAssets(): Promise<CatalogAsset[]>;
  loadWorkspaceScene(projectId: string): Promise<SceneObject[]>;
  bootstrapScene1Runtime(): Promise<SceneRuntimeBootstrapResult>;
  listFrontendEvents(runId: string): Promise<RuntimeBehaviorEvent[]>;
  completeRuntimeAction(runId: string, actionRef: string, request?: RuntimeActionCompleteRequest): Promise<Record<string, unknown>>;
  getApiBaseUrl(): string;
}

export interface RuntimeActionCompleteRequest {
  status?: "done" | "failed";
  payload?: Record<string, unknown>;
  sim_time_s?: number | null;
  ttl_seconds?: number | null;
}

export interface SceneRuntimeBootstrapResult {
  projectId: string;
  sceneId: string;
  sceneRevision: number;
  topologyId: string | null;
  runId: string;
  sceneDocument: SceneDocumentRecord;
  sceneObjects: SceneObject[];
}

interface DeviceSpecBundle {
  upload_order?: string[];
  device_specs?: Array<{ spec_id: string; path: string }>;
}

export const frontendApiClient: FrontendApiClient = {
  async listCatalogAssets() {
    return mockCatalogAssets;
  },

  async loadWorkspaceScene() {
    return mockInitialSceneObjects;
  },

  async bootstrapScene1Runtime() {
    const [sceneDocument, deviceSpecs] = await Promise.all([
      getJson<Record<string, unknown>>("/test/scene1/scene_document.json"),
      loadScene1DeviceSpecs(),
    ]);

    for (const spec of deviceSpecs) {
      await postJson("/api/device-specs", { spec_id: spec.device_spec_id ?? spec.schema_id, document: spec });
    }

    const project = await postJson<{ id: string }>("/api/projects", {
      name: `Scene1 Runtime ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`,
      description: "Local runtime project created from frontend/public/test/scene1.",
    });
    const currentScene = await getJson<{ revision: number }>(`/api/projects/${encodeURIComponent(project.id)}/scene`);
    const replaced = await putJson<{ scene_id: string; new_revision: number }>(`/api/projects/${encodeURIComponent(project.id)}/scene`, {
      base_revision: currentScene.revision,
      document: sceneDocument,
    });
    const topology = await postJson<{ topology_id?: string | null }>(`/api/projects/${encodeURIComponent(project.id)}/topology/rebuild`, {});
    const run = await postJson<{ run_id: string; scene_id: string; base_scene_revision: number }>(`/api/projects/${encodeURIComponent(project.id)}/simulation-runs`, {
      base_scene_revision: replaced.new_revision,
    });

    return {
      projectId: project.id,
      sceneId: run.scene_id,
      sceneRevision: run.base_scene_revision,
      topologyId: topology.topology_id ?? null,
      runId: run.run_id,
      sceneDocument,
      sceneObjects: sceneDocumentToSceneObjects(sceneDocument),
    };
  },

  async listFrontendEvents(runId) {
    const response = await fetch(`${API_BASE_URL}/api/simulation-runs/${encodeURIComponent(runId)}/frontend-events`);
    if (!response.ok) throw new Error(`Failed to load frontend events: ${response.status}`);
    const body = (await response.json()) as { events?: RuntimeBehaviorEvent[] };
    return body.events ?? [];
  },

  async completeRuntimeAction(runId, actionRef, request = {}) {
    const response = await fetch(
      `${API_BASE_URL}/api/simulation-runs/${encodeURIComponent(runId)}/actions/${encodeURIComponent(actionRef)}/complete`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: request.status ?? "done",
          payload: request.payload ?? {},
          sim_time_s: request.sim_time_s,
          ttl_seconds: request.ttl_seconds,
        }),
      },
    );
    if (!response.ok) throw new Error(`Failed to complete runtime action: ${response.status}`);
    return response.json() as Promise<Record<string, unknown>>;
  },

  getApiBaseUrl() {
    return API_BASE_URL;
  },
};

async function loadScene1DeviceSpecs(): Promise<Record<string, unknown>[]> {
  const bundle = await getJson<DeviceSpecBundle>("/test/scene1/device_specs/index.json");
  const specs = bundle.device_specs ?? [];
  const order = new Map((bundle.upload_order ?? []).map((specId, index) => [specId, index]));
  const orderedSpecs = [...specs].sort((a, b) => (order.get(a.spec_id) ?? 999) - (order.get(b.spec_id) ?? 999));
  return Promise.all(orderedSpecs.map((spec) => getJson<Record<string, unknown>>(publicUrl(spec.path))));
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(apiUrl(url));
  if (!response.ok) throw new Error(`GET ${url} failed: ${response.status}`);
  return response.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(url), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`POST ${url} failed: ${response.status}`);
  return response.json() as Promise<T>;
}

async function putJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(url), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`PUT ${url} failed: ${response.status}`);
  return response.json() as Promise<T>;
}

function apiUrl(url: string): string {
  return url.startsWith("/api/") ? `${API_BASE_URL}${url}` : url;
}

function publicUrl(sourcePath: string): string {
  return `/${sourcePath.replace(/\\/g, "/").replace(/^.*frontend\/public\//, "")}`;
}
