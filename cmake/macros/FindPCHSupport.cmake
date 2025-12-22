# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

function(ADD_CXX_PCH TARGET_NAME_LIST PCH_HEADER)
  foreach(TARGET_NAME ${TARGET_NAME_LIST})
    target_precompile_headers(${TARGET_NAME} PRIVATE ${PCH_HEADER})
  endforeach()
endfunction(ADD_CXX_PCH)

function(REUSE_CXX_PCH TARGET_NAME_LIST REUSE_FROM_TARGET_NAME)
  foreach(TARGET_NAME ${TARGET_NAME_LIST})
    target_precompile_headers(${TARGET_NAME} REUSE_FROM ${REUSE_FROM_TARGET_NAME})
  endforeach()
endfunction(REUSE_CXX_PCH)
