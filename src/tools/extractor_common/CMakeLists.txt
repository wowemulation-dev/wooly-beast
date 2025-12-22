# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

CollectSourceFiles(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PRIVATE_SOURCES)

add_library(extractor_common STATIC ${PRIVATE_SOURCES})

target_link_libraries(extractor_common
  PRIVATE
    trinity-core-interface
  PUBLIC
    casc
    common
    network)

target_include_directories(extractor_common
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR})

set_target_properties(extractor_common
  PROPERTIES
    COMPILE_WARNING_AS_ERROR ${WITH_WARNINGS_AS_ERRORS}
    FOLDER "tools")
