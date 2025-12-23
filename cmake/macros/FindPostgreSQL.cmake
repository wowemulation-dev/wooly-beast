# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Find the PostgreSQL installation.
#
# This module defines:
#  PostgreSQL_FOUND            - True if PostgreSQL found
#  PostgreSQL_INCLUDE_DIRS     - PostgreSQL include directories
#  PostgreSQL_LIBRARIES        - PostgreSQL libraries
#  PostgreSQL_VERSION          - PostgreSQL version
#  PostgreSQL_VERSION_STRING   - PostgreSQL version string

# Look for pg_config
find_program(PostgreSQL_CONFIG_EXECUTABLE
    NAMES pg_config
    HINTS
        ENV PostgreSQL_ROOT
        ${PostgreSQL_ROOT}
    PATH_SUFFIXES
        bin
    DOC "Path to pg_config utility"
)

if(PostgreSQL_CONFIG_EXECUTABLE)
    # Get include directory
    execute_process(
        COMMAND ${PostgreSQL_CONFIG_EXECUTABLE} --includedir-server
        OUTPUT_VARIABLE PostgreSQL_INCLUDE_DIR_SERVER
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    
    execute_process(
        COMMAND ${PostgreSQL_CONFIG_EXECUTABLE} --includedir
        OUTPUT_VARIABLE PostgreSQL_INCLUDE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    
    # Get library directory
    execute_process(
        COMMAND ${PostgreSQL_CONFIG_EXECUTABLE} --libdir
        OUTPUT_VARIABLE PostgreSQL_LIBRARY_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    
    # Get version
    execute_process(
        COMMAND ${PostgreSQL_CONFIG_EXECUTABLE} --version
        OUTPUT_VARIABLE PostgreSQL_VERSION_STRING
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    
    # Extract version number
    if(PostgreSQL_VERSION_STRING MATCHES "PostgreSQL ([0-9]+)\\.([0-9]+)(\\.([0-9]+))?")
        set(PostgreSQL_VERSION_MAJOR ${CMAKE_MATCH_1})
        set(PostgreSQL_VERSION_MINOR ${CMAKE_MATCH_2})
        if(CMAKE_MATCH_4)
            set(PostgreSQL_VERSION_PATCH ${CMAKE_MATCH_4})
        else()
            set(PostgreSQL_VERSION_PATCH 0)
        endif()
        set(PostgreSQL_VERSION "${PostgreSQL_VERSION_MAJOR}.${PostgreSQL_VERSION_MINOR}.${PostgreSQL_VERSION_PATCH}")
    endif()
endif()

# Find headers
find_path(PostgreSQL_INCLUDE_DIR
    NAMES libpq-fe.h
    HINTS
        ${PostgreSQL_INCLUDE_DIR}
        ENV PostgreSQL_ROOT
        ${PostgreSQL_ROOT}
    PATH_SUFFIXES
        include
        include/postgresql
        include/pgsql
        postgresql/include
        pgsql/include
)

# Find library
find_library(PostgreSQL_LIBRARY
    NAMES pq libpq
    HINTS
        ${PostgreSQL_LIBRARY_DIR}
        ENV PostgreSQL_ROOT
        ${PostgreSQL_ROOT}
    PATH_SUFFIXES
        lib
        lib64
        lib/postgresql
        lib64/postgresql
)

# Find type header for constants
find_path(PostgreSQL_TYPE_INCLUDE_DIR
    NAMES catalog/pg_type_d.h
    HINTS
        ${PostgreSQL_INCLUDE_DIR_SERVER}
        ${PostgreSQL_INCLUDE_DIR}
        ENV PostgreSQL_ROOT
        ${PostgreSQL_ROOT}
    PATH_SUFFIXES
        postgresql/server
        postgresql/*/server
        pgsql/server
        server
)

# Set the include directories
if(PostgreSQL_INCLUDE_DIR AND PostgreSQL_TYPE_INCLUDE_DIR)
    set(PostgreSQL_INCLUDE_DIRS ${PostgreSQL_INCLUDE_DIR} ${PostgreSQL_TYPE_INCLUDE_DIR})
else()
    set(PostgreSQL_INCLUDE_DIRS ${PostgreSQL_INCLUDE_DIR})
endif()

set(PostgreSQL_LIBRARIES ${PostgreSQL_LIBRARY})

# Handle the QUIETLY and REQUIRED arguments and set PostgreSQL_FOUND
include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(PostgreSQL
    REQUIRED_VARS
        PostgreSQL_LIBRARY
        PostgreSQL_INCLUDE_DIR
    VERSION_VAR
        PostgreSQL_VERSION
)

mark_as_advanced(
    PostgreSQL_CONFIG_EXECUTABLE
    PostgreSQL_INCLUDE_DIR
    PostgreSQL_INCLUDE_DIR_SERVER
    PostgreSQL_TYPE_INCLUDE_DIR
    PostgreSQL_LIBRARY_DIR
    PostgreSQL_LIBRARY
)