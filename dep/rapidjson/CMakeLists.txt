# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

add_library(rapidjson INTERFACE)

target_include_directories(rapidjson
  INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR})

target_compile_definitions(rapidjson
  INTERFACE
    RAPIDJSON_HAS_STDSTRING
    RAPIDJSON_48BITPOINTER_OPTIMIZATION=0
    RAPIDJSON_ASSERT=WPAssert)

if(TRINITY_SYSTEM_PROCESSOR MATCHES "x86|amd64")
  target_compile_definitions(rapidjson INTERFACE -DRAPIDJSON_SSE2)
elseif(TRINITY_SYSTEM_PROCESSOR MATCHES "^arm")
  target_compile_definitions(rapidjson INTERFACE -DRAPIDJSON_NEON)
endif()
