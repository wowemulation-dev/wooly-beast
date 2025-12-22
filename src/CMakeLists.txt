# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

add_subdirectory(genrev)
add_subdirectory(common)

if(SERVERS)
  add_subdirectory(server)
endif(SERVERS)

if(TOOLS)
  add_subdirectory(tools)
endif(TOOLS)
