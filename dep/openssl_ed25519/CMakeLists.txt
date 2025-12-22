# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

file(GLOB RECURSE sources *.cpp *.c *.h)

add_library(openssl_ed25519
  SHARED
    curve25519.c
    ed25519/ed25519.h
    ec_lcl.h
    internal/refcount.h)

set_target_properties(openssl_ed25519 PROPERTIES LINKER_LANGUAGE CXX)

target_include_directories(openssl_ed25519
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR})

target_compile_definitions(openssl_ed25519
  PRIVATE
    OPENSSL_ED25519_EXPORT
)

target_link_libraries(openssl_ed25519
  PRIVATE
    trinity-dependency-interface
  PUBLIC
    openssl)

set_target_properties(openssl_ed25519
    PROPERTIES
      FOLDER
        "dep")

if(UNIX)
  install(TARGETS openssl_ed25519
    LIBRARY
      DESTINATION lib)
elseif(WIN32)
  install(TARGETS openssl_ed25519
    RUNTIME
      DESTINATION "${CMAKE_INSTALL_PREFIX}")
endif()
