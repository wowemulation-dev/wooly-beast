# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

#
# Force out-of-source build
#

string(COMPARE EQUAL "${CMAKE_SOURCE_DIR}" "${CMAKE_BINARY_DIR}" BUILDING_IN_SOURCE)

if(BUILDING_IN_SOURCE)
  message(FATAL_ERROR "
    This project requires an out of source build. Remove the file 'CMakeCache.txt'
    found in this directory before continuing, create a separate build directory
    and run 'cmake path_to_project [options]' from there.
  ")
endif()
