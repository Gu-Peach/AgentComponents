import { beforeEach, describe, expect, it } from "vitest";
import { selectFilteredAssets, useWorkspaceStore } from "@/stores/useWorkspaceStore";

describe("workspace store", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().resetWorkspace();
  });

  it("toggles panel state", () => {
    expect(useWorkspaceStore.getState().panels.leftCollapsed).toBe(false);
    useWorkspaceStore.getState().togglePanel("leftCollapsed");
    expect(useWorkspaceStore.getState().panels.leftCollapsed).toBe(true);
  });

  it("filters catalog assets by category and query", () => {
    useWorkspaceStore.getState().setAssetCategory("device_model");
    useWorkspaceStore.getState().setAssetQuery("传送");
    const assets = selectFilteredAssets(useWorkspaceStore.getState());
    expect(assets.some((asset) => asset.type === "conveyor")).toBe(true);
    expect(assets.every((asset) => asset.category === "device_model")).toBe(true);
  });

  it("adds an asset to the scene and selects it", () => {
    const before = useWorkspaceStore.getState().sceneObjects.length;
    useWorkspaceStore.getState().addAssetToScene("asset_conveyor", [1, 0.2, 2]);
    const state = useWorkspaceStore.getState();
    expect(state.sceneObjects).toHaveLength(before + 1);
    expect(state.selectedObjectId).toBe(state.sceneObjects[state.sceneObjects.length - 1].id);
  });

  it("updates selected object transform", () => {
    const objectId = useWorkspaceStore.getState().selectedObjectId;
    expect(objectId).toBeTruthy();
    useWorkspaceStore.getState().updateSceneObjectTransform(objectId!, { position: [3, 0.5, -2] });
    const object = useWorkspaceStore.getState().sceneObjects.find((item) => item.id === objectId);
    expect(object?.transform.position).toEqual([3, 0.5, -2]);
  });
});
