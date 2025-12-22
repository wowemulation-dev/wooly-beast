# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

set(PRIVATE_SOURCES
  TileAssembler.cpp
  TileAssembler.h
  VMapAssembler.cpp)

add_executable(vmap4assembler ${PRIVATE_SOURCES})

target_link_libraries(vmap4assembler
  PRIVATE
    trinity-core-interface
  PUBLIC
    common
    casc
    zlib)

set_target_properties(vmap4assembler
  PROPERTIES
    COMPILE_WARNING_AS_ERROR ${WITH_WARNINGS_AS_ERRORS}
    FOLDER "tools")

if(UNIX)
  install(TARGETS vmap4assembler DESTINATION bin)
elseif(WIN32)
  install(TARGETS vmap4assembler DESTINATION "${CMAKE_INSTALL_PREFIX}")
endif()
