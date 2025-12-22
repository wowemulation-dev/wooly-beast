# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

add_library(valgrind INTERFACE)

target_include_directories(valgrind
  INTERFACE
    "${VALGRIND_INCLUDE_DIR}")
