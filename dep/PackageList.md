# Third Party Libraries

TrinityCore uses the following open source software, in parts or in whole.

## External Dependencies

These libraries are required but not bundled with TrinityCore:

| Library | Description | Version |
|---------|-------------|---------|
| [Boost](http://www.boost.org) | C++ libraries | 1.86+ |
| [libreadline](https://cnswww.cns.cwru.edu/php/chet/readline/rltop.html) | Command line editing | external |
| [MySQL](https://www.mysql.com/) or [MariaDB](https://mariadb.org/) | Database server / client library | MySQL 8.0+ / MariaDB 10.6+ |
| [OpenSSL](https://www.openssl.org/) | Cryptography library | 3.0+ |
| [PostgreSQL](https://www.postgresql.org/) | Database server (optional, with `WITH_POSTGRESQL`) | 16+ |
| [zlib](https://www.zlib.net/) | Compression library | 1.3+ (system on UNIX, bundled 1.3 on Windows) |

## Bundled Dependencies

These libraries are included in the `dep/` directory:

| Library | Description | Version |
|---------|-------------|---------|
| [argon2](https://github.com/P-H-C/phc-winner-argon2) | Password hashing | 62358ba |
| [CascLib](https://github.com/ladislav-zezula/CascLib) | CASC storage reader | 3.0 |
| [Catch2](https://github.com/catchorg/Catch2) | Testing framework | v2.13.9 |
| [efsw](https://github.com/SpartanJ/efsw) | File system watcher | 1.0.0 (e6afbec) |
| [fmt](https://github.com/fmtlib/fmt) | Formatting library | 10.2.1 |
| [G3D](http://g3d.sourceforge.net/) | 3D engine | 9.0-Release r4036 |
| [gSOAP](http://gsoap2.sourceforge.net/) | XML Web services toolkit | 2.8.117 |
| [jemalloc](http://www.canonware.com/jemalloc/) | Memory allocator | 5.2.1 |
| [openssl_ed25519](https://github.com/openssl/openssl) | Ed25519 reference implementation | embedded |
| [protobuf](https://github.com/protocolbuffers/protobuf) | Protocol Buffers (pinned, see Custom Modifications) | 2.6.1 |
| [rapidjson](https://github.com/Tencent/rapidjson) | JSON parser/generator | 1.1.0 |
| [recastnavigation](https://github.com/recastnavigation/recastnavigation) | Navigation mesh toolset | 54bb094 |
| [SFMT](https://github.com/MersenneTwister-Lab/SFMT) | Mersenne Twister PRNG | 73bcba2 |
| [short_alloc](https://howardhinnant.github.io/short_alloc.h) | Stack-based allocator | N/A |
| [utf8-cpp](https://github.com/nemtrif/utfcpp) | UTF-8 library | 3.2.3 |
| [zlib](http://www.zlib.net/) | Compression library | 1.3 |

## Custom Modifications

Some libraries have TrinityCore-specific modifications:

- **recastnavigation**: Custom changes at
  <https://github.com/TrinityCore/recastnavigation/tree/3.3.5>

- **protobuf**: Pinned to 2.6.1 with local patches in `dep/protobuf/tc_custom/`
  and `dep/protobuf/*.diff`. This version cannot be upgraded: the on-the-wire
  protocol must match the World of Warcraft client, and Blizzard ships
  protobuf 2.6.1 (with their own custom fixes) in every WoW product. The pin
  can only be revisited if Blizzard themselves move to a newer protobuf
  release in the client.
