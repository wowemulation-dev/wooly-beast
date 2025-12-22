# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

set(Detour_STAT_SRCS
    Source/DetourAlloc.cpp 
    Source/DetourAssert.cpp 
    Source/DetourCommon.cpp 
    Source/DetourNavMesh.cpp 
    Source/DetourNavMeshBuilder.cpp 
    Source/DetourNavMeshQuery.cpp 
    Source/DetourNode.cpp 
)

add_library(Detour STATIC ${Detour_STAT_SRCS})

target_include_directories(Detour
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/Include)

target_link_libraries(Detour
  PRIVATE
    trinity-dependency-interface
  PUBLIC
    zlib)

set_target_properties(Detour
    PROPERTIES
      FOLDER
        "dep")
