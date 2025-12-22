# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

set(Recast_STAT_SRCS
    Source/Recast.cpp 
    Source/RecastAlloc.cpp 
	Source/RecastAssert.cpp 
    Source/RecastArea.cpp 
    Source/RecastContour.cpp 
    Source/RecastFilter.cpp 
    Source/RecastLayers.cpp
    Source/RecastMesh.cpp 
    Source/RecastMeshDetail.cpp 
    Source/RecastRasterization.cpp 
    Source/RecastRegion.cpp 
)

add_library(Recast STATIC ${Recast_STAT_SRCS})

target_include_directories(Recast
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/Include)

target_link_libraries(Recast
  PRIVATE
    trinity-dependency-interface
  PUBLIC
    zlib)

set_target_properties(Recast
    PROPERTIES
      FOLDER
        "dep")
