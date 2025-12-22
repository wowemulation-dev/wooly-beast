# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

CollectSourceFiles(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PRIVATE_SOURCES)

add_executable(mapextractor
  ${PRIVATE_SOURCES}
)

target_include_directories(mapextractor
  PUBLIC
    ${CMAKE_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/loadlib)

target_link_libraries(mapextractor
  PRIVATE
    trinity-core-interface
  PUBLIC
    extractor_common)

CollectIncludeDirectories(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PUBLIC_INCLUDES)

target_include_directories(mapextractor
  PUBLIC
    ${PUBLIC_INCLUDES}
  PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR})

set_target_properties(mapextractor
  PROPERTIES
    COMPILE_WARNING_AS_ERROR ${WITH_WARNINGS_AS_ERRORS}
    FOLDER "tools")

if(UNIX)
  install(TARGETS mapextractor DESTINATION bin)
elseif(WIN32)
  install(TARGETS mapextractor DESTINATION "${CMAKE_INSTALL_PREFIX}")
endif()
