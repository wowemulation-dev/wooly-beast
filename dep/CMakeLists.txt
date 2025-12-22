# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

add_subdirectory(threads)

if(SERVERS OR TOOLS)
  add_subdirectory(boost)
  add_subdirectory(zlib)
  add_subdirectory(g3dlite)
  add_subdirectory(recastnavigation)
  add_subdirectory(fmt)
  add_subdirectory(SFMT)
  add_subdirectory(utf8cpp)
  add_subdirectory(valgrind)
  add_subdirectory(openssl)
  add_subdirectory(jemalloc)
  add_subdirectory(argon2)
  add_subdirectory(openssl_ed25519)
  add_subdirectory(short_alloc)
endif()

if(SERVERS)
  add_subdirectory(mysql)
  add_subdirectory(readline)
  add_subdirectory(gsoap)
  add_subdirectory(rapidjson)
  add_subdirectory(efsw)
  add_subdirectory(protobuf)
endif()

if(TOOLS)
  add_subdirectory(CascLib)
endif()

if(BUILD_TESTING)
  include(FetchContent)
  FetchContent_Declare(Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG        v2.13.9
    GIT_SHALLOW    1)
  FetchContent_MakeAvailable(Catch2)
endif()
