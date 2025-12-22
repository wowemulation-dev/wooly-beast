# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Need to pass old ${CMAKE_BINARY_DIR} as param because its different at build stage
add_custom_target(revision_data.h ALL
  COMMAND "${CMAKE_COMMAND}" -DBUILDDIR="${CMAKE_BINARY_DIR}" -P "${CMAKE_SOURCE_DIR}/cmake/genrev.cmake" "${CMAKE_BINARY_DIR}"
  WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
)

set_target_properties(revision_data.h
    PROPERTIES
      FOLDER
        "server")
