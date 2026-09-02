@echo off
echo.
echo  Wing Theatre Controller - Companion Module Installer
echo  =====================================================
echo.

REM Find Companion's node runtime
set NODE_PATH=
set COREPACK_PATH=

for %%d in (
  "%ProgramFiles%\Bitfocus\Companion\resources\node-runtimes\node22"
  "%ProgramFiles%\Companion\resources\node-runtimes\node22"
  "%LocalAppData%\Programs\Companion\resources\node-runtimes\node22"
) do (
  if exist "%%~d\node.exe" (
    set "NODE_PATH=%%~d"
    goto :found_node
  )
)

echo  ERROR: Could not find Companion's Node.js runtime.
echo  Please install Companion first from https://bitfocus.io/companion
pause
exit /b 1

:found_node
echo  Found Node.js at: %NODE_PATH%

REM Find corepack
for %%f in (
  "%NODE_PATH%\lib\node_modules\corepack\dist\corepack.js"
  "%NODE_PATH%\node_modules\corepack\dist\corepack.js"
) do (
  if exist "%%~f" (
    set "COREPACK_PATH=%%~f"
    goto :found_corepack
  )
)

echo  ERROR: Could not find corepack.
pause
exit /b 1

:found_corepack
echo  Found corepack at: %COREPACK_PATH%
echo.
echo  Installing dependencies (yarn install)...
echo.

cd /d "%~dp0"
"%NODE_PATH%\node.exe" "%COREPACK_PATH%" yarn install

if %ERRORLEVEL% EQU 0 (
  echo.
  echo  Done! Dependencies installed successfully.
  echo.
  echo  Next steps:
  echo  1. Open Companion Launcher
  echo  2. Click the cog top-right ^> Advanced Settings
  echo  3. Set Developer modules path to the PARENT folder of this module
  echo  4. Enable Developer Modules
  echo  5. Launch GUI ^> Connections ^> Add ^> Wing Theatre Controller
  echo  6. Set IP to your Mac's IP address and port 9001
  echo.
) else (
  echo.
  echo  ERROR: yarn install failed. Check output above.
  echo.
)

pause
