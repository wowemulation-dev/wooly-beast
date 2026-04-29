# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

cmake_minimum_required(VERSION 3.30)

# add this options before PROJECT keyword
set(CMAKE_DISABLE_SOURCE_CHANGES ON)
set(CMAKE_DISABLE_IN_SOURCE_BUILD ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Set projectname (must be done AFTER setting configurationtypes)
project(TrinityCore)

if(POLICY CMP0144)
  cmake_policy(SET CMP0144 NEW) # find_package() uses upper-case <PACKAGENAME>_ROOT variables
endif()

if(POLICY CMP0153)
  cmake_policy(SET CMP0153 NEW) # The exec_program() command should not be called
endif()

# Set RPATH-handing (CMake parameters)
set(CMAKE_SKIP_BUILD_RPATH 0)
set(CMAKE_BUILD_WITH_INSTALL_RPATH 0)
list(APPEND CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_PREFIX}/lib")
set(CMAKE_INSTALL_RPATH_USE_LINK_PATH 1)

# set macro-directory
list(APPEND CMAKE_MODULE_PATH
  "${CMAKE_SOURCE_DIR}/cmake/macros")

# build in Release-mode by default if not explicitly set
if(CMAKE_GENERATOR STREQUAL "Ninja Multi-Config")
  set(CMAKE_DEFAULT_BUILD_TYPE "RelWithDebInfo" CACHE INTERNAL "")
endif()
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "RelWithDebInfo")
endif()

include(CheckCXXSourceRuns)
include(CheckIncludeFiles)
include(ConfigureScripts)

# set default buildoptions and print them
include(cmake/options.cmake)

# turn off PCH totally if enabled (hidden setting, mainly for devs)
if(NOPCH)
  set(USE_COREPCH 0)
  set(USE_SCRIPTPCH 0)
endif()

include(ConfigureBaseTargets)
include(CheckPlatform)

include(GroupSources)
include(AutoCollect)

find_package(PCHSupport)

if(NOT WITHOUT_GIT)
  find_package(Git 1.7)
endif()

# find mysql client binary (needed by genrev)
find_package(MySQL OPTIONAL_COMPONENTS binary)

# Find revision ID and hash of the sourcetree
include(cmake/genrev.cmake)

# print out the results before continuing
include(cmake/showoptions.cmake)

# add dependencies
add_subdirectory(dep)

# add core sources
add_subdirectory(src)

include(CTest)
if(BUILD_TESTING)
  list(APPEND CMAKE_MODULE_PATH
    "${Catch2_SOURCE_DIR}/contrib")
  include(Catch)

  add_subdirectory(tests)

  # Catch cmakefile messes with our settings we explicitly leave up to the user
  # restore user preference
  if (NOT WITH_SOURCE_TREE STREQUAL "hierarchical-folders")
    set_property(GLOBAL PROPERTY USE_FOLDERS OFF)
  endif()
endif()
