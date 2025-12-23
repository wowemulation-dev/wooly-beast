# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Database backend selection
if(WITH_POSTGRESQL OR DATABASE_TYPE STREQUAL "PostgreSQL")
  find_package(PostgreSQL 14 REQUIRED)
  set(USING_POSTGRESQL TRUE)
else()
  set(USING_POSTGRESQL FALSE)
endif()

if(USING_POSTGRESQL)
  # Collect all sources excluding MySQL files and PCH
  CollectSourceFiles(
    ${CMAKE_CURRENT_SOURCE_DIR}
    PRIVATE_SOURCES
    # Exclude
    ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/MySQL)

  # Exclude MySQL-specific files from Database directory
  set(MYSQL_FILES_TO_EXCLUDE
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLConnection.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLConnection.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLHacks.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLPreparedStatement.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLPreparedStatement.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLThreading.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLThreading.h
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/MySQLWorkaround.h)

  foreach(file ${MYSQL_FILES_TO_EXCLUDE})
    list(REMOVE_ITEM PRIVATE_SOURCES ${file})
  endforeach()
else()
  # MySQL build - exclude PostgreSQL directory
  CollectSourceFiles(
    ${CMAKE_CURRENT_SOURCE_DIR}
    PRIVATE_SOURCES
    # Exclude
    ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/PostgreSQL
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/PostgreSQL)
endif()

if(USE_COREPCH)
  set(PRIVATE_PCH_HEADER PrecompiledHeaders/databasePCH.h)
endif()

GroupSources(${CMAKE_CURRENT_SOURCE_DIR})

add_library(database
  ${PRIVATE_SOURCES}
)

if(USING_POSTGRESQL)
  # Collect includes excluding MySQL-specific directories
  CollectIncludeDirectories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    PUBLIC_INCLUDES
    # Exclude
    ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/MySQL)

  target_include_directories(database
    PUBLIC
      ${PUBLIC_INCLUDES}
      ${PostgreSQL_INCLUDE_DIRS}
    PRIVATE
      ${CMAKE_CURRENT_BINARY_DIR})

  target_link_libraries(database
    PRIVATE
      trinity-core-interface
      ${PostgreSQL_LIBRARIES}
    PUBLIC
      common)

  target_compile_definitions(database
    PUBLIC
      WITH_POSTGRESQL)
else()
  CollectIncludeDirectories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    PUBLIC_INCLUDES
    # Exclude
    ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/Implementation/PostgreSQL
    ${CMAKE_CURRENT_SOURCE_DIR}/Database/PostgreSQL)

  target_include_directories(database
    PUBLIC
      ${PUBLIC_INCLUDES}
    PRIVATE
      ${CMAKE_CURRENT_BINARY_DIR})

  target_link_libraries(database
    PRIVATE
      trinity-core-interface
      mysql
    PUBLIC
      common)
endif()

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
