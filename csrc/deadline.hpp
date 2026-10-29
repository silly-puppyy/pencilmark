#pragma once
#include <chrono>

namespace cs {

// Wall-clock deadline for one rate() call (max_seconds), per thread. The solve loop, the technique searches, the rule
// enumeration, the refute search and the exact search check it and stop when it passes; the caller reads g_deadline_hit to
// report band "Unknown" (GRADE.md). Off unless set_deadline(seconds > 0).
inline thread_local std::chrono::steady_clock::time_point g_deadline{};
inline thread_local bool g_deadline_on = false;
inline thread_local bool g_deadline_hit = false;
inline bool deadline_passed() {
    if (!g_deadline_on) return false;
    if (!g_deadline_hit && std::chrono::steady_clock::now() >= g_deadline) g_deadline_hit = true;
    return g_deadline_hit;
}
inline void set_deadline(double seconds) {
    g_deadline_hit = false;
    g_deadline_on = seconds > 0;
    if (g_deadline_on)
        g_deadline = std::chrono::steady_clock::now() +
                     std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(seconds));
}

}  // namespace cs
