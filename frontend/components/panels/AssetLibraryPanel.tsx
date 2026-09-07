"use client";

import { ChevronLeft, Cuboid, Folder, LayoutTemplate, Plus, Search } from "lucide-react";
import { useMemo } from "react";
import { filterCatalogAssets, useWorkspaceStore } from "@/stores/useWorkspaceStore";
import type { AssetCategory, CatalogAsset } from "@/types/scene";

const categoryLabels: Record<AssetCategory, string> = {
  device_model: "设备模型",
  scene_model: "场景模型",
};

function AssetIcon({ asset }: { asset: CatalogAsset }) {
  if (asset.category === "scene_model") {
    return <LayoutTemplate size={22} color={asset.color} />;
  }
  return <Cuboid size={22} color={asset.color} />;
}

function AssetCard({ asset, selected }: { asset: CatalogAsset; selected: boolean }) {
  const selectAsset = useWorkspaceStore((state) => state.selectAsset);
  const addAssetToScene = useWorkspaceStore((state) => state.addAssetToScene);

  function handleDragStart(event: React.DragEvent<HTMLDivElement>) {
    event.dataTransfer.setData("application/agent-components-asset-id", asset.id);
    event.dataTransfer.effectAllowed = "copy";
  }

  return (
    <div
      className={`asset-card ${selected ? "selected" : ""}`}
      data-testid={`asset-card-${asset.id}`}
      draggable
      role="button"
      tabIndex={0}
      onClick={() => selectAsset(asset.id)}
      onDoubleClick={() => addAssetToScene(asset.id)}
      onDragStart={handleDragStart}
      onKeyDown={(event) => {
        if (event.key === "Enter") selectAsset(asset.id);
      }}
      title="双击或点击加号添加到场景，也可拖拽到三维视口"
    >
      <div className="asset-thumb">
        <AssetIcon asset={asset} />
      </div>
      <div className="asset-meta">
        <div className="asset-name">{asset.name}</div>
        <div className="asset-description">{asset.description}</div>
      </div>
      <button
        className="asset-action"
        aria-label={`添加 ${asset.name}`}
        onClick={(event) => {
          event.stopPropagation();
          addAssetToScene(asset.id);
        }}
      >
        <Plus size={16} />
      </button>
    </div>
  );
}

export function AssetLibraryPanel() {
  const assetCategory = useWorkspaceStore((state) => state.assetCategory);
  const assetQuery = useWorkspaceStore((state) => state.assetQuery);
  const assets = useWorkspaceStore((state) => state.assets);
  const selectedAssetId = useWorkspaceStore((state) => state.selectedAssetId);
  const setAssetCategory = useWorkspaceStore((state) => state.setAssetCategory);
  const setAssetQuery = useWorkspaceStore((state) => state.setAssetQuery);
  const togglePanel = useWorkspaceStore((state) => state.togglePanel);
  const filteredAssets = useMemo(() => filterCatalogAssets(assets, assetCategory, assetQuery), [assets, assetCategory, assetQuery]);

  return (
    <section className="asset-library" data-testid="asset-library" aria-label="设备资产库">
      <div className="panel-heading">
        <div>
          <div className="panel-title">
            <Folder size={16} />
            电子目录
          </div>
          <div className="panel-subtitle">设备与场景 mock catalog</div>
        </div>
        <button className="collapse-button" data-testid="collapse-left" aria-label="收起资产库" onClick={() => togglePanel("leftCollapsed")}>
          <ChevronLeft size={16} />
        </button>
      </div>

      <div className="library-controls">
        <div className="search-row">
          <Search size={15} color="var(--text-muted)" />
          <input
            data-testid="asset-search"
            value={assetQuery}
            onChange={(event) => setAssetQuery(event.target.value)}
            placeholder="搜索模型、标签或描述"
            aria-label="搜索资产"
          />
        </div>

        <div className="segmented" aria-label="资产分类">
          {Object.entries(categoryLabels).map(([key, label]) => (
            <button
              key={key}
              className={assetCategory === key ? "active" : ""}
              onClick={() => setAssetCategory(key as AssetCategory)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="library-tree" aria-label="VC 目录结构占位">
          <div className="tree-row"><Folder size={14} /> 所有模型</div>
          <div className="tree-row"><Folder size={14} /> 公共模型 / Components</div>
          <div className="tree-row"><Folder size={14} /> 公共模型 / Layouts</div>
        </div>
      </div>

      <div className="asset-list">
        {filteredAssets.map((asset) => (
          <AssetCard key={asset.id} asset={asset} selected={asset.id === selectedAssetId} />
        ))}
        {filteredAssets.length === 0 && (
          <div className="empty-panel">
            <div>
              <Search size={28} />
              <p>没有匹配的模型。当前搜索只是本地 mock 过滤，后续会接后端 catalog API。</p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
