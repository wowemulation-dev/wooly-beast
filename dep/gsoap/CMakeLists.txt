# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

file(GLOB sources *.cpp *.c *.h)

add_library(gsoap STATIC ${sources})

set_target_properties(gsoap PROPERTIES LINKER_LANGUAGE CXX)

target_include_directories(gsoap
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR})

target_compile_definitions(gsoap
  PUBLIC
    WITH_OPENSSL)

target_link_libraries(gsoap
  PRIVATE
    trinity-dependency-interface
  PUBLIC
    openssl)

set_target_properties(gsoap
    PROPERTIES
      FOLDER
        "dep")

if (MSVC)
  # Little fix for MSVC / Windows platforms
  target_compile_definitions(gsoap
    PRIVATE
      _CRT_SECURE_CPP_OVERLOAD_STANDARD_NAMES=0)
endif()
