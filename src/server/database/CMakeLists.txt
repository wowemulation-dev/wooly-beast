# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

CollectSourceFiles(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PRIVATE_SOURCES
  # Exclude
  ${CMAKE_CURRENT_SOURCE_DIR}/PrecompiledHeaders)

if(USE_COREPCH)
  set(PRIVATE_PCH_HEADER PrecompiledHeaders/databasePCH.h)
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

target_link_libraries(database
  PRIVATE
    trinity-core-interface
    mysql
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
