# Third Party Libraries

TrinityCore uses the following open source software, in parts or in whole.

## External Dependencies

These libraries are required but not bundled with TrinityCore:

| Library | Description | Version |
|---------|-------------|---------|
| [Boost](http://www.boost.org) | C++ libraries | 1.55+ |
| [libreadline](https://cnswww.cns.cwru.edu/php/chet/readline/rltop.html) | Command line editing | external |
| [OpenSSL](https://www.openssl.org/) | Cryptography library | external |

## Bundled Dependencies

These libraries are included in the `dep/` directory:

| Library | Description | Version |
|---------|-------------|---------|
| [argon2](https://github.com/P-H-C/phc-winner-argon2) | Password hashing | 62358ba |
| [Boost Process](http://www.highscore.de/boost/process0.5/) | Child process management | 0.5 |
| [bzip2](http://www.bzip.org/) | Data compression | 1.0.6 |
| [Catch2](https://github.com/catchorg/Catch2) | Testing framework | v2.13.0 |
| [efsw](https://github.com/SpartanJ/efsw) | File system watcher | 1.5.0+ (f94a661) |
| [fmt](https://github.com/fmtlib/fmt) | Formatting library | 9.1.0 |
| [G3D](http://g3d.sourceforge.net/) | 3D engine | 9.0-Release r4036 |
| [gSOAP](http://gsoap2.sourceforge.net/) | XML Web services toolkit | 2.8.117 |
| [jemalloc](https://github.com/jemalloc/jemalloc) | Memory allocator | 5.3.0 |
| [libmpq](https://github.com/mbroemme/libmpq/) | MPQ archive reader | d59b4cf |
| [recastnavigation](https://github.com/recastnavigation/recastnavigation) | Navigation mesh toolset | 54bb094 |
| [SFMT](https://github.com/MersenneTwister-Lab/SFMT) | Mersenne Twister PRNG | 73bcba2 |
| [short_alloc](https://howardhinnant.github.io/short_alloc.h) | Stack-based allocator | N/A |
| [utf8-cpp](https://github.com/nemtrif/utfcpp) | UTF-8 library | 4.0.8 |
| [zlib](http://www.zlib.net/) | Compression library | 1.3.1 |

## Custom Modifications

Some libraries have TrinityCore-specific modifications:

- **recastnavigation**: Custom changes at
  <https://github.com/TrinityCore/recastnavigation/tree/3.3.5>
