# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

CollectSourceFiles(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PRIVATE_SOURCES)

add_executable(mmaps_generator ${PRIVATE_SOURCES})

target_link_libraries(mmaps_generator
  PRIVATE
    trinity-core-interface
  PUBLIC
    common
    extractor_common
    Recast
    Detour
    zlib)

CollectIncludeDirectories(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PUBLIC_INCLUDES)

target_include_directories(mmaps_generator
  PUBLIC
    ${PUBLIC_INCLUDES}
  PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR})

set_target_properties(mmaps_generator
  PROPERTIES
    COMPILE_WARNING_AS_ERROR ${WITH_WARNINGS_AS_ERRORS}
    FOLDER "tools")

if(UNIX)
  install(TARGETS mmaps_generator DESTINATION bin)
elseif(WIN32)
  install(TARGETS mmaps_generator DESTINATION "${CMAKE_INSTALL_PREFIX}")
endif()
