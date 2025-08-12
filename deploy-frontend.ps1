<#
  deploy-frontend.ps1  ―  Frontend packer for Azure zip-deploy
  ▸ Builds React app → frontend/dist
  ▸ Copies dist contents → deploy_frontend_temp (no nested folders)
  ▸ Builds frontend_deploy.zip with proper structure for Linux App Service
#>

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath "$PSScriptRoot"        # repo root

# ---------- Build frontend -------------------------------------------------
Write-Host "`nBuilding frontend application..."
Set-Location -Path "frontend"

# Clean previous build
if (Test-Path "dist") { 
    Remove-Item "dist" -Recurse -Force 
    Write-Host "Cleaned previous build"
}

# Run npm build
Write-Host "Running npm run build..."
& npm run build

# Check if build succeeded
if (-not (Test-Path "dist")) {
    throw "FATAL: Build failed - dist folder not created"
}

# Return to repo root
Set-Location -LiteralPath "$PSScriptRoot"

# ---------- Fresh temp dir -------------------------------------------------
$deployDir = Join-Path $PWD 'deploy_frontend_temp'
if (Test-Path $deployDir) { Remove-Item $deployDir -Recurse -Force }
$null = New-Item $deployDir -ItemType Directory

Write-Host "`nCopying dist contents → deploy_frontend_temp..."

# Copy CONTENTS of dist folder, not the folder itself
$distPath = Join-Path $PWD "frontend\dist"
Get-ChildItem -Path $distPath -Recurse | ForEach-Object {
    $relativePath = $_.FullName.Substring($distPath.Length + 1)
    $destPath = Join-Path $deployDir $relativePath
    
    if ($_.PSIsContainer) {
        # Create directory
        if (-not (Test-Path $destPath)) {
            New-Item $destPath -ItemType Directory -Force | Out-Null
        }
    } else {
        # Copy file
        $destDir = Split-Path $destPath -Parent
        if (-not (Test-Path $destDir)) {
            New-Item $destDir -ItemType Directory -Force | Out-Null
        }
        Copy-Item $_.FullName $destPath -Force
    }
}

# No server files needed - PM2 serve handles everything

# ---------- Sanity check ---------------------------------------------------
$must = 'index.html'
foreach ($item in $must) {
    if (-not (Test-Path (Join-Path $deployDir $item))) {
        throw "FATAL: '$item' missing from deploy_frontend_temp. Build may have failed."
    }
}

# ---------- Show structure -------------------------------------------------
Write-Host "`nResulting frontend structure:"
Get-ChildItem -LiteralPath $deployDir -Recurse | ForEach-Object {
    if ($_.PSIsContainer) {
        $fileCount = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File | Measure-Object).Count
        $indent = "  " * (($_.FullName.Substring($deployDir.Length) -split '\\').Length - 1)
        Write-Host "$indent[DIR]  $($_.Name) ($fileCount files)"
    } else {
        $indent = "  " * (($_.FullName.Substring($deployDir.Length) -split '\\').Length - 1)
        $size = [math]::Round($_.Length / 1KB, 1)
        Write-Host "$indent[FILE] $($_.Name) ($size KB)"
    }
} | Select-Object -First 20  # Limit output for readability

$totalFiles = (Get-ChildItem -LiteralPath $deployDir -Recurse -File | Measure-Object).Count
Write-Host "`nTotal files: $totalFiles"

# ─── ZIP WITH PROPER PATHS ─────────────────────────────────────────────────
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Write-ZipEntry {
    param ($zip, [IO.FileInfo]$file, $root)
    $relative = $file.FullName.Substring($root.Length + 1) -replace '\\','/'
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $file.FullName, $relative,
        [IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
}

$zipPath = Join-Path $PWD 'frontend_deploy.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath }

$zip = [IO.Compression.ZipFile]::Open(
           $zipPath,
           [IO.Compression.ZipArchiveMode]::Create
       )

Get-ChildItem $deployDir -Recurse -File | ForEach-Object {
    Write-ZipEntry -zip $zip -file $_ -root $deployDir
}
$zip.Dispose()

# ---------- Done -----------------------------------------------------------
Write-Host "`nZIP created → $zipPath"
Write-Host "`nDeploy commands:"
Write-Host ""
Write-Host "STEP 1 - DEPLOY TO STAGING FIRST (recommended):"
Write-Host "  # Create staging slot if not exists:"
Write-Host "  az webapp deployment slot create --resource-group EenhoornReporting --name property-update-frontend-linux-dtcwcnckgkh3fdcv --slot staging"
Write-Host ""
Write-Host "  # Deploy to staging:"
Write-Host "  az webapp deploy --resource-group EenhoornReporting --name property-update-frontend-linux-dtcwcnckgkh3fdcv --src-path `"$zipPath`" --type zip --async --slot staging"
Write-Host ""
Write-Host "STEP 2 - DEPLOY TO PRODUCTION (when ready):"
Write-Host "  az webapp deploy --resource-group EenhoornReporting --name property-update-frontend-linux-dtcwcnckgkh3fdcv --src-path `"$zipPath`" --type zip --async"
Write-Host ""
Write-Host "IMPORTANT - AFTER DEPLOYMENT, ENSURE STARTUP COMMAND IS SET:"
Write-Host "  Go to Azure Portal → App Service → Configuration → General Settings"
Write-Host "  Startup Command: pm2 serve /home/site/wwwroot --spa --no-daemon --port 8080"
Write-Host "  (This serves static files with SPA routing support - no dependencies needed!)"
Write-Host ""
Write-Host "VERIFY DEPLOYMENT:"
Write-Host "  az webapp log tail --resource-group EenhoornReporting --name property-update-frontend-linux-dtcwcnckgkh3fdcv"
Write-Host "" 