@echo off
setlocal EnableDelayedExpansion

if "%~1"=="" (
    echo Usage: %0 ^<tag_or_branch^> [--local-only] [--hash ^<git_hash^>] [--msvc ^<version^>]
    echo Example: %0 1.6.45
    echo Example: %0 1.6.45 --local-only
    echo Example: %0 master --local-only
    echo Example: %0 1.6.45 --msvc 2022
    exit /b 1
)

set MEMCACHED_REF=%~1
set LOCAL_ONLY=0
set GIT_HASH=
set MSVC_VER=

:parse_args
shift
if "%~1"=="" goto end_parse_args
if "%~1"=="--local-only" (
    set LOCAL_ONLY=1
    goto parse_args
)
if "%~1"=="--hash" (
    set GIT_HASH=%~2
    shift
    goto parse_args
)
if "%~1"=="--msvc" (
    set MSVC_VER=%~2
    shift
    goto parse_args
)
goto parse_args
:end_parse_args

set REPO_DIR=%~dp0
set WORK_DIR=%REPO_DIR%build_work
set SRC_DIR=%WORK_DIR%\memcached
set BUILD_DIR=build_msvc

echo =======================================================
echo Building Memcached for Windows at ref: %MEMCACHED_REF%
echo =======================================================

if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"
mkdir "%WORK_DIR%"
cd /d "%WORK_DIR%"

echo [1/6] Fetching upstream Memcached...
set REPO_URL=https://github.com/memcached/memcached.git

if not "%GIT_HASH%"=="" (
    echo Fetching full repository to checkout hash: %GIT_HASH%
    git clone %REPO_URL% "%SRC_DIR%"
    if errorlevel 1 (
        echo Failed to clone Memcached
        exit /b 1
    )
    cd /d "%SRC_DIR%"
    git checkout %GIT_HASH%
    if errorlevel 1 (
        echo Failed to checkout hash %GIT_HASH%
        exit /b 1
    )
) else (
    git clone --branch %MEMCACHED_REF% --depth 1 %REPO_URL% "%SRC_DIR%" 2>nul
    if errorlevel 1 (
        echo Clone with branch/tag %MEMCACHED_REF% failed, attempting full clone...
        git clone %REPO_URL% "%SRC_DIR%"
        if errorlevel 1 (
            echo Failed to clone Memcached repository.
            exit /b 1
        )
        cd /d "%SRC_DIR%"
        git checkout %MEMCACHED_REF%
        if errorlevel 1 (
            echo Failed to checkout ref %MEMCACHED_REF%
            exit /b 1
        )
    ) else (
        cd /d "%SRC_DIR%"
    )
)

echo [2/6] Applying overlay and packaging files...
xcopy /E /I /Y "%REPO_DIR%overlay\*" "%SRC_DIR%\" >nul

echo Preparing Windows Service Wrapper (WinSW)...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/winsw/winsw/releases/download/v3.0.0-alpha.11/WinSW-x64.exe' -OutFile '%SRC_DIR%\memcached-service.exe'"
copy /y "%REPO_DIR%packaging\memcached-service.xml" "%SRC_DIR%\memcached-service.xml" >nul

echo [3/6] Configuring CMake with MSVC...
cd /d "%SRC_DIR%"

if "!MSVC_VER!"=="2022" (
    cmake -G "Visual Studio 17 2022" -A x64 -B %BUILD_DIR% -S .
) else if "!MSVC_VER!"=="2026" (
    cmake -G "Visual Studio 18 2026" -A x64 -B %BUILD_DIR% -S .
) else (
    cmake -G "Visual Studio 18 2026" -A x64 -B %BUILD_DIR% -S . 2>nul
    if errorlevel 1 (
        cmake -G "Visual Studio 17 2022" -A x64 -B %BUILD_DIR% -S .
    )
)
if errorlevel 1 (
    echo CMake configuration failed.
    exit /b 1
)

echo [4/6] Building Memcached (Release)...
cmake --build %BUILD_DIR% --config Release
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo [5/6] Running Test Suite...
cd /d "%SRC_DIR%\%BUILD_DIR%"
ctest -C Release --output-on-failure -E testapp
if errorlevel 1 (
    echo Some unit tests failed.
) else (
    echo Unit test suite passed successfully.
)

echo Running E2E Smoke Tests...
set MEMCACHED_EXE="%SRC_DIR%\%BUILD_DIR%\Release\memcached.exe"
if not exist %MEMCACHED_EXE% set MEMCACHED_EXE="%SRC_DIR%\%BUILD_DIR%\bin\Release\memcached.exe"
if not exist %MEMCACHED_EXE% set MEMCACHED_EXE="%SRC_DIR%\%BUILD_DIR%\memcached.exe"

if not exist %MEMCACHED_EXE% (
    echo Memcached executable not found!
    exit /b 1
)

start "Memcached Server" %MEMCACHED_EXE% -p 11211
powershell -Command "Start-Sleep -Seconds 2"

powershell -Command "$client = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 11211); $stream = $client.GetStream(); $writer = New-Object System.IO.StreamWriter($stream); $reader = New-Object System.IO.StreamReader($stream); $writer.AutoFlush = $true; $writer.WriteLine('version'); $ver = $reader.ReadLine(); Write-Host 'Server responded:' $ver; $writer.WriteLine('set testkey 0 0 5'); $writer.WriteLine('hello'); $setres = $reader.ReadLine(); Write-Host 'Set responded:' $setres; $writer.WriteLine('get testkey'); $line1 = $reader.ReadLine(); $line2 = $reader.ReadLine(); $line3 = $reader.ReadLine(); Write-Host 'Get responded:' $line1 $line2 $line3; $writer.WriteLine('quit'); $client.Close(); if ($setres -ne 'STORED' -or $line2 -ne 'hello') { exit 1 }"
if errorlevel 1 (
    echo E2E smoke test failed!
    taskkill /f /im memcached.exe 2>nul
    exit /b 1
)

echo E2E smoke tests passed!
taskkill /f /im memcached.exe 2>nul

echo [6/6] Packaging with CPack...
cd /d "%SRC_DIR%\%BUILD_DIR%"
cpack -G WIX -C Release
cpack -G NSIS -C Release
cpack -G ZIP -C Release

if "!LOCAL_ONLY!"=="1" (
    echo.
    echo =======================================================
    echo --local-only specified. Skipping Git tagging and GitHub Release.
    echo Artifacts generated in: %SRC_DIR%\%BUILD_DIR%
    echo Done!
    exit /b 0
)

echo Tagging repository and publishing GitHub Release...
cd /d "%REPO_DIR%"
set TAG_NAME=%MEMCACHED_REF%

git tag -d %TAG_NAME% 2>nul
git push origin :refs/tags/%TAG_NAME% 2>nul
gh release delete %TAG_NAME% -y --cleanup-tag 2>nul

git tag %TAG_NAME%
git push origin %TAG_NAME%

set ASSETS="%SRC_DIR%\%BUILD_DIR%\Memcached-*.msi" "%SRC_DIR%\%BUILD_DIR%\Memcached-*.exe" "%SRC_DIR%\%BUILD_DIR%\Memcached-*.zip" %MEMCACHED_EXE%
gh release create %TAG_NAME% %ASSETS% --title "Memcached %MEMCACHED_REF% for Windows" --notes "Automated Windows MSVC native builds for Memcached %MEMCACHED_REF%"

if errorlevel 1 (
    echo Failed to create GitHub release.
    exit /b 1
)

echo Done! Release %TAG_NAME% published successfully.
