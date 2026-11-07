/// @file
/// The engine's debug switches: stderr traces for development, off in normal use. Each is an environment variable,
/// read once (a getenv per move was a linear scan of the environment in hot loops). Add a switch here, not a getenv
/// at the call site.
#pragma once
#include <array>
#include <cstdlib>

namespace cs {

enum DebugFlag { DBG_COLOR, DBG_IMPLIED, DBG_MENTAL, DBG_TIE, DBG_BAND, DBG_BAND_DUMP, DBG_N };

inline bool debug_on(DebugFlag f) {
    static const std::array<bool, DBG_N> on = [] {
        const char* names[DBG_N] = {"COLOUR_DEBUG",     "CSOLVER_IMPLIED_DEBUG", "CSOLVER_MENTALDEBUG",
                                    "CSOLVER_TIEDEBUG", "BAND_DEBUG",            "BAND_DUMP"};
        std::array<bool, DBG_N> a{};
        for (int i = 0; i < DBG_N; ++i) a[i] = std::getenv(names[i]) != nullptr;
        return a;
    }();
    return on[f];
}

}  // namespace cs
