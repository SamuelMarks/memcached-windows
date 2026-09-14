# CPack Source configuration for Memcached Windows
set(CPACK_SOURCE_GENERATOR "ZIP;TGZ")
set(CPACK_SOURCE_PACKAGE_FILE_NAME "Memcached-1.6.45-src")
set(CPACK_SOURCE_IGNORE_FILES
    "/\.git/"
    "/build.*/"
    "/\.vscode/"
    "/\.idea/"
    "/__pycache__/"
    "/\.DS_Store"
)
