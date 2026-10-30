"""Builds the C++ engine (pencilmark._csolver) with pybind11.

Compile flags are fixed on purpose: -ffp-contract=off / -fno-fast-math (MSVC: /fp:precise) keep floating-point results
identical to the reference build, so the same puzzle always gets the same card. The interpreter's own CFLAGS
(-march=native, -flto, -DNDEBUG, ...) are not inherited; on macOS the -arch / -isysroot / deployment-target flags are
kept so universal and cross builds work. CXX picks the compiler; PENCILMARK_CXXFLAGS adds flags.
"""
import os
import shlex
import sys

import pybind11
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

SOURCES = ["model", "nary", "solver", "chains", "extra", "rich", "canon", "mental", "explain", "forcing", "colour",
           "human", "sudokuwiki", "desc", "refute", "bindings"]          # order as in the reference build
GCC_FLAGS = ["-O3", "-std=c++17", "-ffp-contract=off", "-fno-fast-math", "-Wall", "-Wno-unused-function", "-pthread"]
MSVC_FLAGS = ["/O2", "/std:c++17", "/fp:precise", "/EHsc", "/bigobj"]   # also accepted by clang-cl


def _keep_platform_flags(cmd):
    """macOS: -arch X, -isysroot X, -mmacosx-version-min=..., -target X from the interpreter's compiler command."""
    out, i = [], 0
    while i < len(cmd):
        t = cmd[i]
        if t in ("-arch", "-isysroot", "-target") and i + 1 < len(cmd):
            out += [t, cmd[i + 1]]; i += 2; continue
        if t.startswith("-mmacosx-version-min=") or t.startswith("--target="):
            out.append(t)
        i += 1
    return out


class BuildExt(build_ext):
    def build_extensions(self):
        c = self.compiler
        extra = shlex.split(os.environ.get("PENCILMARK_CXXFLAGS", ""))
        if c.compiler_type == "unix":
            cxx = shlex.split(os.environ.get("CXX", "c++"))
            plat = _keep_platform_flags(list(getattr(c, "compiler_so", []))) if sys.platform == "darwin" else []
            compile_cmd = cxx + plat + ["-fPIC"]
            link_cmd = cxx + plat + (["-bundle", "-undefined", "dynamic_lookup"] if sys.platform == "darwin" else ["-shared"])
            for attr in ("compiler", "compiler_so", "compiler_cxx", "compiler_so_cxx"):
                if hasattr(c, attr):
                    c.set_executable(attr, compile_cmd)
            for attr in ("linker_so", "linker_so_cxx"):
                if hasattr(c, attr):
                    c.set_executable(attr, link_cmd)
            for ext in self.extensions:
                ext.extra_compile_args = GCC_FLAGS + extra
                ext.extra_link_args = ["-pthread"]
        elif c.compiler_type == "msvc":
            for ext in self.extensions:
                ext.extra_compile_args = MSVC_FLAGS + extra
        super().build_extensions()


ext = Extension("pencilmark._csolver", [f"csrc/{s}.cpp" for s in SOURCES], include_dirs=["csrc", pybind11.get_include()],
                language="c++")   # flags set in BuildExt

setup(ext_modules=[ext], cmdclass={"build_ext": BuildExt})
