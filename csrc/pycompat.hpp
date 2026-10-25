// Bit-exact emulation of the bits of CPython 3.14 the reference solver's
// behaviour depends on:
//   * set iteration order (setobject.c: linear probing + perturbation,
//     resize policy, merge / intersection construction order),
//   * tuple hashing (xxHash-style tuplehash, used for set-of-tuples order),
//   * builtin sum() over floats (Neumaier compensated summation, 3.12+),
//   * float ** float special cases.
// Only what the solver needs: keys are non-negative ints (hash == value) or
// interned tuple ids carrying a precomputed hash.
#pragma once
#include "portable.hpp"
#include <cmath>
#include <cstdint>
#include <vector>

namespace cs {

// builtin sum() over floats (CPython >= 3.12)
struct CompSum {
    double hi = 0.0, lo = 0.0;
    inline void add(double x) {
        double t = hi + x;
        if (std::fabs(hi) >= std::fabs(x))
            lo += (hi - t) + x;
        else
            lo += (x - t) + hi;
        hi = t;
    }
    inline double value() const {
        if (lo != 0.0 && std::isfinite(lo)) return hi + lo;
        return hi;
    }
};

// float.__pow__ for the cases the solver hits (positive finite bases)
inline double py_pow(double iv, double iw) {
    if (iw == 0.0) return 1.0;
    if (iv == 1.0) return 1.0;
    return std::pow(iv, iw);
}

// tuplehash() for a tuple of small non-negative ints
inline int64_t py_tuple_hash(const int* items, int len) {
    const uint64_t P1 = 11400714785074694791ULL, P2 = 14029467366897019727ULL, P5 = 2870177450012600261ULL;
    uint64_t acc = P5;
    for (int i = 0; i < len; ++i) {
        uint64_t lane = (uint64_t)(int64_t)items[i];
        acc += lane * P2;
        acc = (acc << 31) | (acc >> 33);
        acc *= P1;
    }
    acc += (uint64_t)len ^ (P5 ^ 3527539ULL);
    if (acc == (uint64_t)-1) return 1546275796;
    return (int64_t)acc;
}

// CPython set emulator. Keys must be unique per value (ints, or interned ids).
class PySet {
public:
    struct E {
        int64_t key;
        int64_t hash;
        uint8_t st;  // 0 empty, 1 active, 2 dummy
    };
    std::vector<E> t;
    size_t mask = 7;
    int64_t fill = 0, used = 0;

    PySet() { t.assign(8, E{0, 0, 0}); }
    void clear() {
        t.assign(8, E{0, 0, 0});
        mask = 7;
        fill = used = 0;
    }
    int64_t size() const { return used; }

    void add(int64_t key, int64_t hash) {
        size_t m = mask;
        size_t i = (size_t)hash & m;
        size_t perturb = (size_t)hash;
        E* freeslot = nullptr;
        size_t j;
        while (true) {
            j = i;
            int probes = (i + 9 <= m) ? 9 : 0;
            do {
                E& e = t[j];
                if (e.st == 0) goto found_unused_or_dummy;
                if (e.st == 1 && e.hash == hash) {
                    if (e.key == key) return;  // found active
                } else if (e.st == 2) {
                    freeslot = &e;
                }
                ++j;
            } while (probes--);
            perturb >>= 5;
            i = (i * 5 + 1 + perturb) & m;
        }
    found_unused_or_dummy:
        if (freeslot) {
            ++used;
            *freeslot = E{key, hash, 1};
            return;
        }
        ++fill;
        ++used;
        t[j] = E{key, hash, 1};
        if ((size_t)fill * 5 < m * 3) return;
        resize(used > 50000 ? used * 2 : used * 4);
    }
    void add(int64_t intkey) { add(intkey, intkey); }

    bool contains(int64_t key, int64_t hash) const { return lookup(key, hash) >= 0; }
    bool contains(int64_t intkey) const { return contains(intkey, intkey); }

    void discard(int64_t key, int64_t hash) {
        pm_long k = lookup(key, hash);
        if (k < 0) return;
        t[k].st = 2;
        t[k].hash = -1;
        --used;
    }
    void discard(int64_t intkey) { discard(intkey, intkey); }

    // set_merge (s |= other, set(other), s.update(other))
    void merge(const PySet& o) {
        if (&o == this || o.used == 0) return;
        if ((size_t)(fill + o.used) * 5 >= mask * 3) resize((used + o.used) * 2);
        if (fill == 0 && mask == o.mask && o.fill == o.used) {
            t = o.t;
            fill = o.fill;
            used = o.used;
            return;
        }
        if (fill == 0) {
            fill = o.used;
            used = o.used;
            for (const E& e : o.t)
                if (e.st == 1) insert_clean(e.key, e.hash);
            return;
        }
        for (size_t i = 0; i <= o.mask; ++i) {
            const E& e = o.t[i];
            if (e.st == 1) add(e.key, e.hash);
        }
    }

    // set_intersection(a, b): new set
    static PySet intersection(const PySet& a, const PySet& b) {
        PySet r;
        if (&a == &b) {
            r.merge(a);
            return r;
        }
        const PySet* so = &a;
        const PySet* other = &b;
        if (other->used > so->used) std::swap(so, other);
        for (const E& e : other->t)
            if (e.st == 1 && so->contains(e.key, e.hash)) r.add(e.key, e.hash);
        return r;
    }

    template <class F>
    void for_each(F&& f) const {
        for (const E& e : t)
            if (e.st == 1) f(e.key);
    }
    std::vector<int64_t> items() const {
        std::vector<int64_t> out;
        for_each([&](int64_t k) { out.push_back(k); });
        return out;
    }

private:
    pm_long lookup(int64_t key, int64_t hash) const {
        size_t m = mask;
        size_t i = (size_t)hash & m;
        size_t perturb = (size_t)hash;
        while (true) {
            size_t j = i;
            int probes = (i + 9 <= m) ? 9 : 0;
            do {
                const E& e = t[j];
                if (e.st == 0) return -1;
                if (e.st == 1 && e.hash == hash && e.key == key) return (pm_long)j;
                ++j;
            } while (probes--);
            perturb >>= 5;
            i = (i * 5 + 1 + perturb) & m;
        }
    }
    void insert_clean(int64_t key, int64_t hash) {
        size_t perturb = (size_t)hash;
        size_t i = (size_t)hash & mask;
        while (true) {
            if (t[i].st == 0) {
                t[i] = E{key, hash, 1};
                return;
            }
            if (i + 9 <= mask) {
                for (size_t j = 1; j <= 9; ++j)
                    if (t[i + j].st == 0) {
                        t[i + j] = E{key, hash, 1};
                        return;
                    }
            }
            perturb >>= 5;
            i = (i * 5 + 1 + perturb) & mask;
        }
    }
    void resize(int64_t minused) {
        size_t newsize = 8;
        while (newsize <= (size_t)minused) newsize <<= 1;
        if (newsize == 8 && mask == 7 && fill == used) return;
        std::vector<E> old;
        old.swap(t);
        t.assign(newsize, E{0, 0, 0});
        mask = newsize - 1;
        if (fill != used) fill = used;
        for (const E& e : old)
            if (e.st == 1) insert_clean(e.key, e.hash);
    }
};

}  // namespace cs
