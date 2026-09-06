$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot\..
try {
  docker compose down
  supabase stop
} finally {
  Pop-Location
}

