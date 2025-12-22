# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

set(SFMT_SOURCES
  SFMT.c
  SFMT.h
  SFMT-alti.h
  SFMT-common.h
  SFMT-neon.h
  SFMT-params.h
  SFMT-params607.h
  SFMT-params1279.h
  SFMT-params2281.h
  SFMT-params4253.h
  SFMT-params11213.h
  SFMT-params19937.h
  SFMT-params44497.h
  SFMT-params86243.h
  SFMT-params132049.h
  SFMT-params216091.h
  SFMT-sse2.h
  SFMT-sse2-msc.h)

add_library(sfmt STATIC ${SFMT_SOURCES})

target_include_directories(sfmt
  INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR})

# using the standard Mersenne exponent 19937
target_compile_definitions(sfmt PUBLIC SFMT_MEXP=19937)

# enable SIMD instructions if available
include(CheckCXXCompilerFlag)

# MSVC does not have any flags to check
if (CMAKE_CXX_COMPILER_ID MATCHES "MSVC")
  if (TRINITY_SYSTEM_PROCESSOR MATCHES "^arm")
    set(HAVE_NEON 1)
  else ()
    set(HAVE_SSE2 1)
  endif ()
else ()
  if (TRINITY_SYSTEM_PROCESSOR STREQUAL "arm")
    check_cxx_compiler_flag(-mfpu=neon HAVE_NEON)
    if (HAVE_NEON)
      target_compile_options(sfmt PRIVATE -mfpu=neon -ftree-vectorize)
    endif()
  elseif (TRINITY_SYSTEM_PROCESSOR STREQUAL "arm64")
    check_cxx_compiler_flag(-march=armv8-a+simd HAVE_NEON)
    if (HAVE_NEON)
      target_compile_options(sfmt PRIVATE -ftree-vectorize)
    endif ()
  elseif (TRINITY_SYSTEM_PROCESSOR MATCHES "x86|amd64")
    #SSE2 is always available
    set(HAVE_SSE2 1)
    target_compile_options(sfmt PRIVATE -msse2)
  endif ()
endif ()

if (HAVE_NEON)
  target_compile_definitions(sfmt PUBLIC HAVE_NEON)
endif ()

if (HAVE_SSE2)
  target_compile_definitions(sfmt PUBLIC HAVE_SSE2)
endif ()

set_target_properties(sfmt PROPERTIES LINKER_LANGUAGE CXX)

# inherit trinitycore generic build options (e.g. fPIC)
target_link_libraries(sfmt PRIVATE trinity-dependency-interface)

set_target_properties(sfmt
  PROPERTIES
    FOLDER
      "dep")
