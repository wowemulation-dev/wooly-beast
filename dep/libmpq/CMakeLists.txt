# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

file(GLOB sources libmpq/*.c libmpq/*.h)

add_library(mpq STATIC ${sources})

set_target_properties(mpq PROPERTIES LINKER_LANGUAGE CXX)

if(WIN32)
  set(WIN_EXTRA_INCLUDE ${CMAKE_CURRENT_SOURCE_DIR}/win)
endif()

target_include_directories(mpq
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${WIN_EXTRA_INCLUDE}
    ${CMAKE_SOURCE_DIR}/dep/zlib
    ${CMAKE_SOURCE_DIR}/dep/bzip2)

target_link_libraries(mpq
  PRIVATE
    trinity-dependency-interface
  PUBLIC
    zlib
    bzip2)

set_target_properties(mpq
    PROPERTIES
      FOLDER
        "dep")
