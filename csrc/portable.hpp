// Portability shims. With GCC / Clang on Linux and macOS nothing changes: the compiler builtins are used directly and
// pm_long is plain `long` (64-bit there), so those builds compile to the same code as the reference build.
//  - Windows (MSVC and clang-cl): `long` is 32-bit, so pm_long is `long long` (the engine assumes a 64-bit long).
//  - MSVC proper: no __builtin_popcount / ctz / clz; mapped to portable code and _BitScan* intrinsics.
#pragma once
#include <climits>
#include <cstdint>
#include <cstdlib>

#if LONG_MAX < INT64_MAX
typedef long long pm_long;
#define pm_labs(x) std::llabs(x)
#else
typedef long pm_long;
#define pm_labs(x) std::labs(x)
#endif

#if (defined(_MSC_VER) && !defined(__clang__)) || defined(PM_TEST_MSVC_SHIMS)
#ifndef PM_TEST_MSVC_SHIMS
#include <intrin.h>
#endif
static inline int pm_popcount32(unsigned int x) {
    x = x - ((x >> 1) & 0x55555555u);
    x = (x & 0x33333333u) + ((x >> 2) & 0x33333333u);
    return (int)((((x + (x >> 4)) & 0x0F0F0F0Fu) * 0x01010101u) >> 24);
}
static inline int pm_popcount64(unsigned long long x) {
    return pm_popcount32((unsigned int)x) + pm_popcount32((unsigned int)(x >> 32));
}
static inline int pm_ctz32(unsigned int x) { unsigned long i; _BitScanForward(&i, x); return (int)i; }
static inline int pm_clz32(unsigned int x) { unsigned long i; _BitScanReverse(&i, x); return 31 - (int)i; }
static inline int pm_ctz64(unsigned long long x) {
#if defined(_M_X64) || defined(_M_ARM64)
    unsigned long i; _BitScanForward64(&i, x); return (int)i;
#else
    unsigned long i;
    if ((unsigned int)x) { _BitScanForward(&i, (unsigned int)x); return (int)i; }
    _BitScanForward(&i, (unsigned int)(x >> 32)); return 32 + (int)i;
#endif
}
#define __builtin_popcount(x) pm_popcount32((unsigned int)(x))
#define __builtin_popcountll(x) pm_popcount64((unsigned long long)(x))
#define __builtin_ctz(x) pm_ctz32((unsigned int)(x))
#define __builtin_ctzll(x) pm_ctz64((unsigned long long)(x))
#define __builtin_clz(x) pm_clz32((unsigned int)(x))
#endif
