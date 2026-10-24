# rasm

A rin-shaped assembler for x64 Windows, for playing with D3D11 graphics and raw
SIMD assembly. rin's declaration syntax and types, x64 instructions written as
they are, one per line. The assembler generates nothing you did not write: frames,
shadow space, saved registers and argument moves are yours, or your macros'.

The code is assembled by clang with a `.cv_loc` per statement and the data is
compiled as C, so Visual Studio steps through the `.rasm` source exactly as it
does through MASM source.

**Status:** design only. Nothing is implemented yet.

- [docs/](docs/README.md): the spec, design, roadmap, decisions, and a working
  debugging prototype ([docs/debug-proto](docs/debug-proto))
- [examples/](examples): LearnOpenGL's hello triangle and transformations,
  hand-written in the proposed syntax, with the call macros and SSE maths

Related: [rin](https://github.com/IbrahimHindawi/rin) (the language whose front
end rasm will reuse).
