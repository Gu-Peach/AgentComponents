import { mockCatalogAssets, mockInitialSceneObjects } from "@/mocks/catalog";
import type { CatalogAsset, SceneObject } from "@/types/scene";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface FrontendApiClient {
  listCatalogAssets(): Promise<CatalogAsset[]>;
  loadWorkspaceScene(projectId: string): Promise<SceneObject[]>;
  getApiBaseUrl(): string;
}

export const frontendApiClient: FrontendApiClient = {
  async listCatalogAssets() {
    return mockCatalogAssets;
  },

  async loadWorkspaceScene() {
    return mockInitialSceneObjects;
  },

  getApiBaseUrl() {
    return API_BASE_URL;
  },
};
