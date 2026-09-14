Memcached Windows Native (MSVC) builds
======================================

[![License](https://img.shields.io/badge/license-CC0%20OR%20Apache--2.0%20OR%20MIT-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Build and Release Memcached Windows](https://github.com/SamuelMarks/memcached-windows/actions/workflows/release.yml/badge.svg)](https://github.com/SamuelMarks/memcached-windows/actions/workflows/release.yml)

This repository provides **native Windows builds** of [Memcached](https://github.com/memcached/memcached) using the Microsoft Visual C++ (MSVC) toolchain and CMake.

Memcached is an in-memory key-value store for small chunks of arbitrary data (strings, objects) from results of database calls, API calls, or page rendering. Historically, running Memcached on Windows required virtualization (WSL2), emulation layers (Cygwin/MSYS2), or outdated third-party ports that lagged years behind upstream.

This project's mission is to provide true native Windows binaries without compromising or forking upstream C codebases.

---

## Key Features

- **Pristine Upstream Compatibility:** Upstream Memcached C source and header files are completely untouched. All Windows support is provided non-invasively via CMake build orchestration and [`auto-win-msvc`](https://github.com/SamuelMarks/auto-win-msvc).
- **Pure CMake Build System:** Complete CMake configuration supporting MSVC 2019, 2022, and 2026, as well as cross-platform Linux and macOS builds.
- **Dual Test Suites:**
  - **C Test Runner:** Fast, native C test runner (`c_test_runner`) with 18 comprehensive feature suites covering text and binary protocols, CAS, slabs, flags, expiration, stats, and limits.
  - **Cross-Platform Python Test Suite:** Socket-level integration test harness (`tests/run_tests.py`) fully integrated with CTest.
- **Windows Service Ready:** Includes [WinSW](https://github.com/winsw/winsw) service wrapper preconfigured to register Memcached as an automatic background Windows Service.
- **Multiple Packaging Formats:** Generates MSI installer (WiX), NSIS executable installer, and standalone portable ZIP archives via CPack.
- **Automated CI/CD:** Weekly automated synchronization with upstream Memcached releases via GitHub Actions.

---

## Releases

Pre-compiled packages are available on the [Releases](../../releases) tab.

### Included Packages:
- **MSI Installer (`Memcached-*-win64.msi`):** Enterprise-ready Windows Installer that installs binaries and automatically registers Memcached as a Windows Service.
- **NSIS Installer (`Memcached-*-win64.exe`):** Standard setup installer with start/stop service integration.
- **Portable ZIP (`Memcached-*-win64.zip`):** Standalone archive containing `memcached.exe`, `memcached-service.exe`, and documentation.
- **Standalone Binaries:** Direct downloads for `memcached.exe` and `c_test_runner.exe`.

---

## Windows Service Management

When installed via the MSI or NSIS installer, Memcached is registered as a Windows Service named `Memcached`.

You can also manage the service manually using `memcached-service.exe`:

```cmd
:: Install Memcached as a Windows Service
memcached-service.exe install

:: Start the service
memcached-service.exe start

:: Check status / Stop the service
memcached-service.exe stop

:: Uninstall the service
memcached-service.exe uninstall
```

Configuration arguments (memory limit `-m 64`, port `-p 11211`, etc.) can be adjusted in `memcached-service.xml` located alongside the executable.

---

## Building Locally

### Prerequisites

- **Visual Studio 2022 or 2026** (with C++ CMake tools for Windows)
- **Git** in PATH
- **CMake 3.24+**
- **Python 3.8+** (optional, for running Python tests)

### Quick Start with `release.bat`

We provide an automated script (`release.bat` or `build-and-release.bat`) that clones upstream, applies the overlay, builds via MSVC, runs CTest and E2E verification, and generates CPack installers:

```cmd
:: Build, test, and package locally without publishing:
.\release.bat 1.6.45 --local-only

:: Specify MSVC version (e.g. 2022 or 2026):
.\release.bat 1.6.45 --local-only --msvc 2022

:: Build latest master branch:
.\release.bat master --local-only
```

### Manual Build Steps

1. Clone Memcached, `auto-win-msvc`, and this repository:
   ```cmd
   git clone https://github.com/memcached/memcached.git
   git clone https://github.com/SamuelMarks/auto-win-msvc.git
   git clone https://github.com/SamuelMarks/memcached-windows.git
   ```

2. Copy the overlay files into the Memcached directory:
   ```cmd
   xcopy /E /I /Y memcached-windows\overlay\* memcached\
   ```

3. Configure and build:
   ```cmd
   cd memcached
   :: Try Visual Studio 2026 first, or Visual Studio 2022:
   cmake -B build_msvc -S . -G "Visual Studio 18 2026" -A x64
   :: Or for Visual Studio 2022:
   :: cmake -B build_msvc -S . -G "Visual Studio 17 2022" -A x64
   cmake --build build_msvc --config Release
   ```

4. Run tests:
   ```cmd
   cd build_msvc
   ctest -C Release --output-on-failure -E testapp
   ```

5. Generate installers:
   ```cmd
   cpack -G WIX -C Release
   cpack -G NSIS -C Release
   cpack -G ZIP -C Release
   ```

Binaries will be located in `build_msvc\bin\Release\memcached.exe` (or `build_msvc\Release\memcached.exe`).

---

## How It Works: `auto-win-msvc`

Memcached relies on standard POSIX sockets and networking APIs (`sys/socket.h`, `netinet/in.h`, `arpa/inet.h`, `poll.h`, `unistd.h`).

Rather than altering Memcached upstream source files, our CMake build script configures MSVC to include headers and link against [`auto-win-msvc`](https://github.com/SamuelMarks/auto-win-msvc). This polyfills POSIX APIs to native Windows Winsock2 and Win32 functions at compile time with zero overhead.

---

## License

Licensed under any of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or
  <https://apache.org/licenses/LICENSE-2.0>)
- Creative Commons CC0, Version 1.0 [LICENSE-CC0](LICENSE-CC0) or <http://creativecommons.org/publicdomain/zero/1.0/>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
licensed as above, without any additional terms or conditions.
