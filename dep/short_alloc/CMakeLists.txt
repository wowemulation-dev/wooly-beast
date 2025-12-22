# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

add_library(short_alloc INTERFACE)

target_include_directories(short_alloc
  INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR})
