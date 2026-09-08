import { mockCatalogAssets, mockInitialSceneObjects } from "@/mocks/catalog";
import type { CatalogAsset, RuntimeBehaviorEvent, SceneObject } from "@/types/scene";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface FrontendApiClient {
  listCatalogAssets(): Promise<CatalogAsset[]>;
  loadWorkspaceScene(projectId: string): Promise<SceneObject[]>;
  listFrontendEvents(runId: string): Promise<RuntimeBehaviorEvent[]>;
  completeRuntimeAction(runId: string, actionRef: string, payload?: Record<string, unknown>): Promise<Record<string, unknown>>;
  getApiBaseUrl(): string;
}

export const frontendApiClient: FrontendApiClient = {
  async listCatalogAssets() {
    return mockCatalogAssets;
  },

  async loadWorkspaceScene() {
    return mockInitialSceneObjects;
  },

  async listFrontendEvents(runId) {
    const response = await fetch(`${API_BASE_URL}/api/simulation-runs/${encodeURIComponent(runId)}/frontend-events`);
    if (!response.ok) throw new Error(`Failed to load frontend events: ${response.status}`);
    const body = (await response.json()) as { events?: RuntimeBehaviorEvent[] };
    return body.events ?? [];
  },

  async completeRuntimeAction(runId, actionRef, payload = {}) {
    const response = await fetch(
      `${API_BASE_URL}/api/simulation-runs/${encodeURIComponent(runId)}/actions/${encodeURIComponent(actionRef)}/complete`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      },
    );
    if (!response.ok) throw new Error(`Failed to complete runtime action: ${response.status}`);
    return response.json() as Promise<Record<string, unknown>>;
  },

  getApiBaseUrl() {
    return API_BASE_URL;
  },
};
