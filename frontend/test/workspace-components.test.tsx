// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { AssetLibraryPanel } from "@/components/panels/AssetLibraryPanel";
import { PropertiesPanel } from "@/components/panels/PropertiesPanel";
import { useWorkspaceStore } from "@/stores/useWorkspaceStore";

describe("workspace panels", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().resetWorkspace();
  });

  it("filters the asset library and toggles the left panel", () => {
    render(<AssetLibraryPanel />);
    expect(screen.getByTestId("asset-card-asset_robot_arm")).toBeTruthy();

    fireEvent.change(screen.getByTestId("asset-search"), { target: { value: "传送" } });
    expect(screen.getByTestId("asset-card-asset_conveyor")).toBeTruthy();

    fireEvent.click(screen.getByTestId("collapse-left"));
    expect(useWorkspaceStore.getState().panels.leftCollapsed).toBe(true);
  });

  it("edits selected object name and position from properties panel", () => {
    render(<PropertiesPanel />);

    fireEvent.change(screen.getByTestId("property-name"), { target: { value: "Main Conveyor Renamed" } });
    fireEvent.change(screen.getByTestId("position-x"), { target: { value: "5.25" } });

    const selectedId = useWorkspaceStore.getState().selectedObjectId;
    const selected = useWorkspaceStore.getState().sceneObjects.find((object) => object.id === selectedId);

    expect(selected?.name).toBe("Main Conveyor Renamed");
    expect(selected?.transform.position[0]).toBe(5.25);
  });
});
