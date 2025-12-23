# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

if(USE_COREPCH)
  set(PRIVATE_PCH_HEADER PrecompiledHeaders/databasePCH.h)
endif()

# Collect source files based on database backend
if(WITH_POSTGRESQL OR DATABASE_TYPE STREQUAL "PostgreSQL")
  # When building with PostgreSQL, collect all sources then exclude MySQL files
  CollectSourceFiles(
    ${CMAKE_CURRENT_SOURCE_DIR}
    PRIVATE_SOURCES
    # Exclude
    ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders)

  # Remove MySQL-specific files from compilation
  set(MYSQL_FILES_TO_REMOVE
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLConnection.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLConnection.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLPreparedStatement.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLPreparedStatement.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLThreading.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLThreading.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLWorkaround.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLHacks.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/LoginDatabase.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/LoginDatabase.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/CharacterDatabase.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/CharacterDatabase.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/WorldDatabase.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/WorldDatabase.h)

  # Mark MySQL files as header-only to exclude from compilation
  foreach(file ${MYSQL_FILES_TO_REMOVE})
    if(EXISTS ${file})
      set_source_files_properties(${file} PROPERTIES HEADER_FILE_ONLY TRUE)
    endif()
  endforeach()
else()
  # When building with MySQL, exclude PostgreSQL directories
  CollectSourceFiles(
    ${CMAKE_CURRENT_SOURCE_DIR}
    PRIVATE_SOURCES
    # Exclude
    ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/PostgreSQL
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/PostgreSQL)
endif()

GroupSources(${CMAKE_CURRENT_SOURCE_DIR})

add_library(database
  ${PRIVATE_SOURCES}
)

CollectIncludeDirectories(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PUBLIC_INCLUDES
  # Exclude
  ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders)

target_include_directories(database
  PUBLIC
    ${PUBLIC_INCLUDES}
  PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR})

# Configure database backend
if(WITH_POSTGRESQL OR DATABASE_TYPE STREQUAL "PostgreSQL")
  find_package(PostgreSQL 14 REQUIRED)
  target_compile_definitions(database PUBLIC WITH_POSTGRESQL)
  set(database_LIBS ${PostgreSQL_LIBRARIES})
  target_include_directories(database PRIVATE ${PostgreSQL_INCLUDE_DIRS})
else()
  set(database_LIBS mysql)
endif()

target_link_libraries(database
  PRIVATE
    trinity-core-interface
    ${database_LIBS}
  PUBLIC
    common)

set_target_properties(database
  PROPERTIES
    COMPILE_WARNING_AS_ERROR ${WITH_WARNINGS_AS_ERRORS}
    DEFINE_SYMBOL TRINITY_API_EXPORT_DATABASE
    FOLDER "server")

if(BUILD_SHARED_LIBS)
  if(UNIX)
    install(TARGETS database
      LIBRARY
        DESTINATION lib)
  elseif(WIN32)
    install(TARGETS database
      RUNTIME
        DESTINATION "${CMAKE_INSTALL_PREFIX}")
  endif()
endif()

# Generate precompiled header
if(USE_COREPCH)
  add_cxx_pch(database ${PRIVATE_PCH_HEADER})
endif()
