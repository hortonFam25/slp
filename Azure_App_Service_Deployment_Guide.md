# Azure App Services Deployment Guide for Full-Stack Web Applications

## Overview
This guide provides comprehensive instructions for deploying full-stack web applications to Azure App Services using the proven deployment patterns, configurations, and best practices. Follow this guide to ensure successful deployment with proper authentication, database connectivity, and environment configuration.

## Architecture Pattern

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   Azure SQL     │
│   (React/Vite)  │◄──►│   (FastAPI)     │◄──►│   Database      │
│   App Service   │    │   App Service   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Azure AD      │
                       │   (MSAL Auth)   │
                       └─────────────────┘
```

## 🚀 Deployment Scripts

### Backend Deployment Script (`deploy-fixed.ps1`)

Create this PowerShell script in your project root:

```powershell
<#
  deploy-fixed.ps1  ―  Backend packer for Azure zip-deploy
  ▸ Copies backend → deploy_temp           (skips venv & __pycache__)
  ▸ Ensures Python packages have __init__.py files
  ▸ Builds backend_deploy.zip with POSIX paths (required for Linux App Service)
#>

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath "$PSScriptRoot"        # repo root

# ---------- fresh temp dir -----------------------------------------------------
$deployDir = Join-Path $PWD 'deploy_temp'
if (Test-Path $deployDir) { Remove-Item $deployDir -Recurse -Force }
$null = New-Item $deployDir -ItemType Directory

Write-Host "`nCopying backend → deploy_temp …"
Copy-Item '.\backend\*' $deployDir -Recurse -Force `
          -Exclude 'venv*','__pycache__'

# ---------- sanity check -------------------------------------------------------
$must = 'main.py','requirements.txt'
foreach ($item in $must) {
    if (-not (Test-Path (Join-Path $deployDir $item))) {
        throw "FATAL: '$item' missing from deploy_temp. aborting."
    }
}

# ensure Python packages have __init__.py (critical for absolute imports)
$packages = Get-ChildItem $deployDir -Directory | Where-Object { 
    $_.Name -notin @('__pycache__', 'venv', 'migrations', 'certs') 
}
foreach ($pkg in $packages) {
    $init = Join-Path $pkg.FullName '__init__.py'
    if (-not (Test-Path $init)) { 
        '' | Set-Content $init 
        Write-Host "Created missing __init__.py in $($pkg.Name)"
    }
}

# ---------- ZIP WITH POSIX PATHS (CRITICAL FOR LINUX) -------------------------
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

$zipPath = Join-Path $PWD 'backend_deploy.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath }

$zip = [IO.Compression.ZipFile]::Open(
           $zipPath,
           [IO.Compression.ZipArchiveMode]::Create
       )

Get-ChildItem $deployDir -Recurse -File | ForEach-Object {
    Write-ZipEntry -zip $zip -file $_ -root $deployDir
}
$zip.Dispose()

# ---------- deployment commands ------------------------------------------------
Write-Host "`nZIP created → $zipPath"
Write-Host 'Deploy with:'
Write-Host "  az webapp deployment source config-zip --resource-group <your-rg> --name <your-backend-app> --src `"$zipPath`""
```

### Frontend Deployment Script (`deploy-frontend.ps1`)

```powershell
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

# ---------- Sanity check ---------------------------------------------------
$must = 'index.html'
foreach ($item in $must) {
    if (-not (Test-Path (Join-Path $deployDir $item))) {
        throw "FATAL: '$item' missing from deploy_frontend_temp. Build may have failed."
    }
}

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

# ---------- deployment commands ---------------------------------------------
Write-Host "`nZIP created → $zipPath"
Write-Host "`nDeploy commands:"
Write-Host ""
Write-Host "STEP 1 - DEPLOY TO STAGING FIRST (recommended):"
Write-Host "  # Create staging slot if not exists:"
Write-Host "  az webapp deployment slot create --resource-group <your-rg> --name <your-frontend-app> --slot staging"
Write-Host ""
Write-Host "  # Deploy to staging:"
Write-Host "  az webapp deploy --resource-group <your-rg> --name <your-frontend-app> --src-path `"$zipPath`" --type zip --async --slot staging"
Write-Host ""
Write-Host "STEP 2 - DEPLOY TO PRODUCTION (when ready):"
Write-Host "  az webapp deploy --resource-group <your-rg> --name <your-frontend-app> --src-path `"$zipPath`" --type zip --async"
Write-Host ""
Write-Host "IMPORTANT - AFTER DEPLOYMENT, ENSURE STARTUP COMMAND IS SET:"
Write-Host "  Go to Azure Portal → App Service → Configuration → General Settings"
Write-Host "  Startup Command: pm2 serve /home/site/wwwroot --spa --no-daemon --port 8080"
Write-Host "  (This serves static files with SPA routing support - no dependencies needed!)"
```

## 🏗️ Backend Structure & Absolute Imports

### Required Python Project Structure

Your backend must use absolute imports for proper deployment. Ensure this structure:

```
backend/
├── main.py                 # FastAPI entry point
├── requirements.txt        # Python dependencies
├── __init__.py            # Makes backend a package
├── shared/                # Shared utilities
│   ├── __init__.py        # CRITICAL: Must exist
│   ├── auth.py           # Authentication handler
│   ├── database.py       # Database connection
│   └── models.py         # Shared models
├── apps/                  # Application modules
│   ├── __init__.py        # CRITICAL: Must exist
│   ├── your_app/
│   │   ├── __init__.py    # CRITICAL: Must exist
│   │   ├── api.py         # API routes
│   │   ├── models.py      # Pydantic models
│   │   └── db_models.py   # SQLAlchemy models
│   └── another_app/
│       ├── __init__.py    # CRITICAL: Must exist
│       └── ...
└── your_custom_modules/
    ├── __init__.py        # CRITICAL: Must exist
    └── ...
```

### Import Pattern Examples

✅ **Correct Absolute Imports:**
```python
# In main.py
from shared.auth import auth_handler
from shared.database import engine, get_db
from apps.your_app.api import router as your_app_router

# In apps/your_app/api.py
from shared.database import get_db
from shared.auth import auth_handler
from .models import YourModel
from .db_models import YourDBModel
```

❌ **Avoid Relative Imports for Deployment:**
```python
# These may fail in Azure App Service
from ..shared.auth import auth_handler
from ...shared.database import get_db
```

### Key Requirements for Backend

1. **Every directory must have `__init__.py`** - The deployment script creates missing ones
2. **Use absolute imports from project root**
3. **FastAPI app in `main.py`** - Azure looks for this by default
4. **POSIX paths in ZIP** - The script handles this automatically

## 🔐 Azure AD Authentication Setup

### Frontend MSAL Configuration

Create `frontend/src/shared/config/authConfig.ts`:

```typescript
import { Configuration, PopupRequest } from "@azure/msal-browser";

// MSAL configuration
export const msalConfig: Configuration = {
    auth: {
        clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
        authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
        redirectUri: import.meta.env.VITE_REDIRECT_URI || window.location.origin,
    },
    cache: {
        cacheLocation: "sessionStorage",
        storeAuthStateInCookie: false,
    }
};

// OBO scopes - ONLY for the custom API (≤ 20 scopes rule automatically satisfied)
export const appScopes = [
    "api://your-api-app-name.azurewebsites.net/access_as_user",
    "offline_access",
    "openid", 
    "profile"
];

// Login request for OBO flow
export const loginRequest: PopupRequest = {
    scopes: appScopes
};
```

### Backend Authentication Handler

Create `backend/shared/auth.py` (key patterns):

```python
import os
from msal import ConfidentialClientApplication
import jwt
import requests

class AuthHandler:
    def __init__(self):
        # Environment variables
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.client_id = os.getenv('AZURE_CLIENT_ID')
        self.client_secret = os.getenv('AZURE_CLIENT_SECRET')
        
        # Certificate authentication (production)
        self.cert_thumbprint = os.getenv('AZURE_CERT_THUMBPRINT')
        self.cert_private_key_path = os.getenv('AZURE_CERT_PRIVATE_KEY_PATH')
        
        # JWT validation settings - ⚠️ UPDATE THIS URI TO MATCH YOUR APP REGISTRATION
        self.audience = f"api://your-unique-api-identifier.azurewebsites.net"
        self.jwks_url = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        
        # Initialize MSAL client
        if self.client_secret:
            # Local development with client secret
            self.app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}"
            )
        elif self.cert_thumbprint and self.cert_private_key_path:
            # Production with certificate
            cert_credential = {
                "thumbprint": self.cert_thumbprint,
                "private_key": open(self.cert_private_key_path, 'r').read()
            }
            self.app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=cert_credential,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}"
            )

    def verify_token(self, token: str):
        """Verify JWT token from frontend"""
        # Implement JWT verification logic
        # Validate audience, issuer, signature, expiration
        pass
    
    async def get_graph_token(self, user_claims: dict):
        """Get Graph API token via On-Behalf-Of flow"""
        # Implement OBO token exchange
        pass
```

### 🚨 CRITICAL: Update Application ID URI in Your Code

**Before deploying, you MUST update the hardcoded Application ID URI in these files:**

1. **Update `backend/shared/auth.py`**:
```python
# Change this line:
self.audience = f"api://quoteit-api-h4aud7crc7bbgmcj.eastus2-01.azurewebsites.net"
# To your own Application ID URI:
self.audience = f"api://your-unique-api-identifier.azurewebsites.net"
```

2. **Update `frontend/src/shared/config/authConfig.ts`**:
```typescript
// Change this line:
"api://quoteit-api-h4aud7crc7bbgmcj.eastus2-01.azurewebsites.net/access_as_user",
// To your own Application ID URI:
"api://your-unique-api-identifier.azurewebsites.net/access_as_user",
```

3. **Create Azure AD App Registration with the same URI**:
   - In Azure Portal → Azure Active Directory → App registrations
   - Set **Application ID URI** to: `api://your-unique-api-identifier.azurewebsites.net`

## 🗄️ Required Dependencies

### Backend Dependencies (`requirements.txt`)

```txt
fastapi==0.115.12
uvicorn==0.24.0
gunicorn==21.2.0
sqlalchemy==2.0.23
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
azure-identity==1.15.0
azure-keyvault-secrets==4.7.0
pyodbc==5.0.1
python-dotenv==1.0.0
alembic==1.13.1
httpx>=0.24.0
msal==1.31.0
requests==2.31.0
email-validator>=2.0.0
cryptography>=3.4.8
```

### Frontend Dependencies (`package.json`)

```json
{
  "dependencies": {
    "@azure/msal-browser": "^3.28.1",
    "@azure/msal-react": "^2.0.12",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^7.6.0",
    "axios": "^1.4.0",
    "vite": "^4.3.9",
    "typescript": "^5.0.4"
  },
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  }
}
```

## ⚙️ Azure App Service Configuration

### Backend Environment Variables

Set these in Azure Portal → App Service → Configuration → Application Settings:

```bash
# Required Authentication
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-backend-app-registration-id
AZURE_CLIENT_SECRET=your-client-secret-for-local-dev

# Production Certificate Authentication (optional but recommended)
AZURE_CERT_THUMBPRINT=your-cert-thumbprint
AZURE_CERT_PRIVATE_KEY_PATH=/home/site/certs/your-cert.pem
AZURE_CERT_PASSWORD=your-cert-password

# Database Connection
DATABASE_URL=mssql+pyodbc://username:password@server.database.windows.net/database?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no

# CORS Configuration
FRONTEND_URL=https://your-frontend-app.azurewebsites.net

# Optional: Additional Services
OPENAI_API_KEY=your-openai-key
AZURE_STORAGE_CONNECTION_STRING=your-storage-connection-string
```

### Frontend Environment Variables

Set these in Azure Portal → App Service → Configuration → Application Settings:

```bash
# Azure AD Configuration
VITE_AZURE_CLIENT_ID=your-frontend-app-registration-id
VITE_AZURE_TENANT_ID=your-tenant-id
VITE_REDIRECT_URI=https://your-frontend-app.azurewebsites.net

# API Configuration
VITE_API_URL=https://your-backend-app.azurewebsites.net

# Optional: Additional Services
VITE_OPENAI_API_KEY=your-openai-key
```

## 🚀 Deployment Steps

### 1. Prerequisites

```bash
# Install Azure CLI
az --version

# Login to Azure
az login

# Set default subscription (optional)
az account set --subscription "your-subscription-id"
```

### 2. Deploy Backend

```bash
# Run the backend deployment script
.\deploy-fixed.ps1

# Deploy to Azure App Service
az webapp deployment source config-zip \
  --resource-group your-resource-group \
  --name your-backend-app-name \
  --src "backend_deploy.zip"
```

### 3. Deploy Frontend

```bash
# Run the frontend deployment script
.\deploy-frontend.ps1

# Deploy to Azure App Service
az webapp deploy \
  --resource-group your-resource-group \
  --name your-frontend-app-name \
  --src-path "frontend_deploy.zip" \
  --type zip \
  --async
```

### 4. Configure App Service Settings

#### Backend App Service
```bash
# Set Python version (if needed)
az webapp config set \
  --resource-group your-resource-group \
  --name your-backend-app-name \
  --linux-fx-version "PYTHON|3.11"

# Set startup command (FastAPI with Gunicorn)
az webapp config set \
  --resource-group your-resource-group \
  --name your-backend-app-name \
  --startup-file "gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"
```

#### Frontend App Service
```bash
# Set Node.js version
az webapp config set \
  --resource-group your-resource-group \
  --name your-frontend-app-name \
  --linux-fx-version "NODE|18-lts"

# Set startup command for SPA
az webapp config set \
  --resource-group your-resource-group \
  --name your-frontend-app-name \
  --startup-file "pm2 serve /home/site/wwwroot --spa --no-daemon --port 8080"
```

## 🔧 API Scope Configuration Pattern

### ⚠️ CRITICAL: Application ID URI Configuration

**The Application ID URI MUST be hardcoded in three places and they MUST match exactly:**

1. **Backend Auth Handler** (`backend/shared/auth.py`):
```python
self.audience = f"api://quoteit-api-h4aud7crc7bbgmcj.eastus2-01.azurewebsites.net"
```

2. **Frontend Auth Config** (`frontend/src/shared/config/authConfig.ts`):
```typescript
export const appScopes = [
    "api://quoteit-api-h4aud7crc7bbgmcj.eastus2-01.azurewebsites.net/access_as_user",
    "offline_access",
    "openid", 
    "profile"
];
```

3. **Azure AD App Registration** (Portal Configuration):
   - **Application ID URI**: `api://quoteit-api-h4aud7crc7bbgmcj.eastus2-01.azurewebsites.net`

### Azure AD App Registration Setup

1. **Backend App Registration (API)**:
   - **Application ID URI**: `api://quoteit-api-h4aud7crc7bbgmcj.eastus2-01.azurewebsites.net` ⚠️ **MUST MATCH CODE**
   - **Exposed Scopes**: `access_as_user` (User.Read permission type)
   - **App Roles**: Define custom roles if needed

2. **Frontend App Registration (SPA)**:
   - **Platform**: Single-page application
   - **Redirect URIs**: `https://your-frontend-app.azurewebsites.net`
   - **API Permissions**: Add permission to your backend API scope

### Important Notes:

- **The Application ID URI is NOT your App Service URL** - it's a unique identifier
- **Replace the hardcoded values** with your own Application ID URI in all three locations
- **Generate a unique identifier** like: `api://your-api-name-[random-string].azurewebsites.net`
- **All three locations must use the exact same URI** or authentication will fail

### Scope Pattern Usage (Update These Values)

```typescript
// Frontend: Request only your API scope
const scopes = [
    "api://your-unique-api-identifier.azurewebsites.net/access_as_user", // ⚠️ UPDATE THIS
    "offline_access",
    "openid",
    "profile"
];

// Backend: Validate audience matches your API
const audience = "api://your-unique-api-identifier.azurewebsites.net"; // ⚠️ UPDATE THIS
```

## 🛠️ Troubleshooting Common Issues

### 1. Import Errors in Backend
- **Symptom**: `ModuleNotFoundError` on deployment
- **Solution**: Ensure all directories have `__init__.py` files
- **Verification**: Run deployment script - it creates missing `__init__.py` files

### 2. Authentication Failures
- **Symptom**: 401 Unauthorized errors
- **Solution**: Check audience in JWT matches your API URI exactly
- **Verification**: Use debug endpoint `/api/debug/auth-test`

### 3. CORS Issues
- **Symptom**: Frontend can't reach backend API
- **Solution**: Add frontend URL to CORS origins in backend
- **Code**: Update `CORSMiddleware` configuration

### 4. Database Connection Issues
- **Symptom**: Connection timeouts or authentication failures
- **Solution**: Use proper connection string format with Azure SQL
- **Example**: Include `Encrypt=yes&TrustServerCertificate=no`

### 5. Frontend Build Issues
- **Symptom**: Build fails or assets not found
- **Solution**: Ensure all VITE_ environment variables are set
- **Verification**: Check build logs for missing environment variables

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] All `__init__.py` files exist in Python packages
- [ ] Backend uses absolute imports only
- [ ] Frontend builds successfully with `npm run build`
- [ ] Environment variables defined for both apps
- [ ] Azure AD app registrations configured
- [ ] Database connection string tested

### Post-Deployment
- [ ] Backend health check returns 200: `GET /api/health`
- [ ] Frontend loads without console errors
- [ ] Authentication flow works end-to-end
- [ ] Database queries execute successfully
- [ ] CORS configuration allows frontend-backend communication
- [ ] SSL certificates valid (automatic with App Service)

### Monitoring
- [ ] Application Insights configured (optional)
- [ ] Log streaming enabled for debugging
- [ ] Alert rules set up for failures
- [ ] Backup and disaster recovery plan

## 🔗 Useful Commands

```bash
# Monitor logs in real-time
az webapp log tail --resource-group your-rg --name your-app-name

# Restart app service
az webapp restart --resource-group your-rg --name your-app-name

# Get app service URL
az webapp show --resource-group your-rg --name your-app-name --query "defaultHostName" -o tsv

# List app settings
az webapp config appsettings list --resource-group your-rg --name your-app-name

# Set app setting
az webapp config appsettings set --resource-group your-rg --name your-app-name --settings KEY=VALUE
```

This guide provides a complete deployment strategy based on proven patterns. Follow each section carefully, and you'll have a robust, scalable application running on Azure App Services with proper authentication and security.

