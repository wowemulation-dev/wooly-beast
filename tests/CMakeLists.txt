# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

CollectSourceFiles(
  ${CMAKE_CURRENT_SOURCE_DIR}
  TEST_SOURCES
)

GroupSources(${CMAKE_CURRENT_SOURCE_DIR})

add_executable(tests ${TEST_SOURCES})

target_link_libraries(tests
  PRIVATE
    trinity-core-interface
    game
    Catch2::Catch2)

CollectIncludeDirectories(
  ${CMAKE_CURRENT_SOURCE_DIR}
  TEST_INCLUDES)

target_include_directories(tests
  PUBLIC
    ${TEST_INCLUDES}
  PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR})

catch_discover_tests(tests)

set_target_properties(tests
    PROPERTIES
      FOLDER
        "tests")
