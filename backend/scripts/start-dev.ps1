$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot\..
try {
  if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
  }

  supabase start
  docker compose up -d redis
  python -m app.db.init_db
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
} finally {
  Pop-Location
}

