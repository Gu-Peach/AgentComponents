CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.projects (
  id TEXT PRIMARY KEY DEFAULT ('project_' || replace(gen_random_uuid()::text, '-', '')),
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.assets (
  id TEXT PRIMARY KEY DEFAULT ('asset_' || replace(gen_random_uuid()::text, '-', '')),
  bucket TEXT NOT NULL,
  path TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT 'supabase',
  mime_type TEXT,
  size_bytes INTEGER,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (bucket, path, provider)
);

CREATE TABLE IF NOT EXISTS public.device_specs (
  id TEXT PRIMARY KEY,
  spec_key TEXT UNIQUE NOT NULL,
  device_type TEXT NOT NULL,
  version TEXT NOT NULL,
  display_name TEXT NOT NULL,
  document JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_device_specs_device_type ON public.device_specs(device_type);

CREATE TABLE IF NOT EXISTS public.scenes (
  id TEXT PRIMARY KEY DEFAULT ('scene_' || replace(gen_random_uuid()::text, '-', '')),
  project_id TEXT NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  schema_version TEXT NOT NULL DEFAULT 'scene/v0.2',
  revision INTEGER NOT NULL DEFAULT 0,
  current_document JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scenes_project_id ON public.scenes(project_id);

CREATE TABLE IF NOT EXISTS public.scene_events (
  id TEXT PRIMARY KEY DEFAULT ('evt_' || replace(gen_random_uuid()::text, '-', '')),
  scene_id TEXT NOT NULL REFERENCES public.scenes(id) ON DELETE CASCADE,
  revision INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scene_events_scene_revision ON public.scene_events(scene_id, revision);

CREATE TABLE IF NOT EXISTS public.scene_topologies (
  id TEXT PRIMARY KEY,
  scene_id TEXT NOT NULL REFERENCES public.scenes(id) ON DELETE CASCADE,
  scene_revision INTEGER NOT NULL,
  graph_hash TEXT,
  document JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scene_topologies_scene_revision ON public.scene_topologies(scene_id, scene_revision DESC);

CREATE TABLE IF NOT EXISTS public.simulation_runs (
  id TEXT PRIMARY KEY DEFAULT ('simrun_' || replace(gen_random_uuid()::text, '-', '')),
  project_id TEXT NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  scene_id TEXT NOT NULL REFERENCES public.scenes(id) ON DELETE CASCADE,
  base_scene_revision INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'created',
  runtime_snapshot JSONB,
  metrics_summary JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_simulation_runs_project_id ON public.simulation_runs(project_id);

CREATE TABLE IF NOT EXISTS public.simulation_events (
  id TEXT PRIMARY KEY DEFAULT ('simevt_' || replace(gen_random_uuid()::text, '-', '')),
  simulation_run_id TEXT NOT NULL REFERENCES public.simulation_runs(id) ON DELETE CASCADE,
  sim_time_s DOUBLE PRECISION,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_simulation_events_run_time ON public.simulation_events(simulation_run_id, sim_time_s, created_at);

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
  ('models', 'models', false, 104857600, ARRAY['model/gltf-binary', 'model/gltf+json', 'application/octet-stream']),
  ('thumbnails', 'thumbnails', false, 10485760, ARRAY['image/png', 'image/jpeg', 'image/webp']),
  ('uploads', 'uploads', false, 104857600, NULL),
  ('exports', 'exports', false, 104857600, NULL)
ON CONFLICT (id) DO NOTHING;

