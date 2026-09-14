# CPack configuration for Memcached Windows
set(CPACK_PACKAGE_NAME "Memcached")
set(CPACK_PACKAGE_VENDOR "Memcached")
set(CPACK_PACKAGE_VERSION "1.6.45")
set(CPACK_PACKAGE_VERSION_MAJOR "1")
set(CPACK_PACKAGE_VERSION_MINOR "6")
set(CPACK_PACKAGE_VERSION_PATCH "45")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "High-performance, distributed memory object caching system.")
set(CPACK_PACKAGE_HOMEPAGE_URL "https://memcached.org")
set(CPACK_PACKAGE_CONTACT "Samuel Marks")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "Memcached")
set(CPACK_GENERATOR "ZIP;WIX;NSIS")

# WiX Settings
set(CPACK_WIX_UPGRADE_GUID "D62E10B3-5A38-4FBE-8628-9844F4BC8E01")
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/packaging/wix_patch.xml")
    set(CPACK_WIX_PATCH_FILE "${CMAKE_CURRENT_SOURCE_DIR}/packaging/wix_patch.xml")
endif()

# NSIS Settings
set(CPACK_NSIS_DISPLAY_NAME "Memcached")
set(CPACK_NSIS_PACKAGE_NAME "Memcached")
set(CPACK_NSIS_EXTRA_INSTALL_COMMANDS "ExecWait '$INSTDIR\bin\memcached-service.exe install'
ExecWait '$INSTDIR\bin\memcached-service.exe start'")
set(CPACK_NSIS_EXTRA_UNINSTALL_COMMANDS "ExecWait '$INSTDIR\bin\memcached-service.exe stop'
ExecWait '$INSTDIR\bin\memcached-service.exe uninstall'")
