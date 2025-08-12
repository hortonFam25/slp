<#
  deploy.ps1  ―  flat-layout packer for Azure zip-deploy
  ▸ Copies backend → deploy_temp           (skips venv & __pycache__)
  ▸ Ensures mcp/ and agents_openai/ are Python packages
  ▸ Builds backend_deploy.zip with POSIX paths (mcp/api.py, not mcp\api.py)
#>

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath "$PSScriptRoot"        # repo root

# ---------- fresh temp dir -----------------------------------------------------
$deployDir = Join-Path $PWD 'deploy_temp'
if (Test-Path $deployDir) { Remove-Item $deployDir -Recurse -Force }
$null = New-Item $deployDir -ItemType Directory

Write-Host "`nCopying backend → deploy_temp …"
Copy-Item '.\backend\*' $deployDir -Recurse -Force `
          -Exclude 'venv*','.venv*','__pycache__','*.pyc'

# ---------- sanity check -------------------------------------------------------
$must = 'main.py','requirements.txt'
foreach ($item in $must) {
    if (-not (Test-Path (Join-Path $deployDir $item))) {
        throw "FATAL: '$item' missing from deploy_temp. aborting."
    }
}

# ensure Python packages have __init__.py (critical for absolute imports)
$packages = Get-ChildItem $deployDir -Directory | Where-Object { 
    $_.Name -notin @('__pycache__', 'venv', 'certs', '.git') 
}
foreach ($pkg in $packages) {
    $init = Join-Path $pkg.FullName '__init__.py'
    if (-not (Test-Path $init)) { 
        '' | Set-Content $init 
        Write-Host "Created missing __init__.py in $($pkg.Name)"
    }
}

# ---------- mini tree ----------------------------------------------------------
Write-Host "`nResulting top-level structure:"
Get-ChildItem -LiteralPath $deployDir | ForEach-Object {
    if ($_.PSIsContainer) {
        $fileCount = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File |
                      Measure-Object).Count
        "{0,-4} {1,-20} {2,4} files" -f '[DIR]', $_.Name, $fileCount
    } else {
        "[FILE] {0}" -f $_.Name
    }
} | Write-Host

# ─── ZIP WITH POSIX PATHS ──────────────────────────────────────────────────────
Add-Type -AssemblyName System.IO.Compression          # ← NEW
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Write-ZipEntry {
    param ($zip, [IO.FileInfo]$file, $root)
    $relative = $file.FullName.Substring($root.Length + 1) -replace '\\','/'
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $file.FullName, $relative,
        [IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
}

$zipPath = Join-Path $PWD 'backend_deploy.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath }

$zip = [IO.Compression.ZipFile]::Open(
           $zipPath,
           [IO.Compression.ZipArchiveMode]::Create   # ← now resolves
       )

Get-ChildItem $deployDir -Recurse -File | ForEach-Object {
    Write-ZipEntry -zip $zip -file $_ -root $deployDir
}
$zip.Dispose()

# ---------- done ---------------------------------------------------------------
Write-Host "`nZIP created → $zipPath"
Write-Host 'Deploy with:'
Write-Host "  az webapp deployment source config-zip --resource-group <rg> --name <app> --src `"$zipPath`""
Write-Host ""
Write-Host "IMPORTANT - Set the startup command in Azure Portal:"
Write-Host "  gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"
