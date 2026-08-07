@ECHO OFF
TITLE Enterprise AI Assistant

SET "NODE=C:\Users\Madhan\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
SET "NPM_CLI=%~dp0npm-extracted\package\bin\npm-cli.js"

ECHO ============================================
ECHO  Enterprise AI Assistant - Development Server
ECHO ============================================
ECHO.

IF NOT EXIST "frontend\node_modules" (
  ECHO [1/2] Installing frontend dependencies...
  "%NODE%" "%NPM_CLI%" --prefix frontend install --legacy-peer-deps
  ECHO.
)

ECHO [2/2] Starting Vite dev server...
ECHO  Open: http://localhost:5173
ECHO.
"%NODE%" "%NPM_CLI%" --prefix frontend run dev

