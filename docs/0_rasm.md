# From MASM64 to rasm

The lessons are masm64-dx11's, rewritten in rasm: the same instructions, one
call at a time, so they can be read side by side with LearnOpenGL and with the
MASM versions. rasm adds nothing to the code: every instruction in the
program is one written in a `.rasm` file, in the lesson or in an include's
macro. What it changes is everything around the instructions: declarations
are rin's, data is typed and compiled as C, and there are no MASM macros
doing work behind the reader's back. This page is how that turned out in
practice, the conventions every lesson follows and the traps that cost time
once. The language itself is in rin's
[`rasm/docs/spec.md`](https://github.com/IbrahimHindawi/rin/blob/main/rasm/docs/spec.md).

## One file, one program

A lesson is one `.rasm` that `import`s what it uses; every file is read once
per program, however many times it is imported, so includes import what they
need themselves and nothing is guarded. Paths are relative to the importing
file: a lesson says `import "../../../includes/learn/window.rasm"`.

    python build.py              every lesson
    python build.py camera       the lessons whose names contain "camera"

runs, for each lesson,

    rin asm src/.../camera.rasm -o build/camera.exe -l d3d11 -l d3dcompiler -l dxguid -l ole32 -l windowscodecs

which writes `build/rasm/camera.s` (the code, with a `.cv_loc` per
statement) and `build/rasm/camera_data.c` (every type and global, as C), has
clang assemble and compile them, and links `build/camera.exe` and its `.pdb`
with lld. kernel32 and user32 are always linked; the C runtime's start-up
calls `main` as an ordinary proc. `build.py` treats anything `rin asm`
prints besides its "built" line as a failure: a lesson builds clean.

## Checking a lesson

    build\camera.exe --shot shots\camera.png [--time 2.5] [--mode 1]

renders with the clock stopped at `--time` (1 second by default), saves the
backbuffer as a PNG and exits, with the window hidden (`learn/window.rasm`).
`python tools/screenshot.py` does that for every built lesson; 1.1 and 2.1
write their window out by hand and take no `--shot`, as in masm64-dx11, so
the script captures their window from outside.

The reference is masm64-dx11 itself. Its `build\<name>.exe --shot` at the
same `--time` and `--mode` is the comparison that matters, and every lesson so
far matches it **pixel for pixel**. masm64-dx11's stored `shots/*.png` were
taken at other moments, so anything that moves with time differs from them;
the static parts must still match.

## Calling convention

Everything follows Win64, as in masm64-dx11:

- the first four arguments go in `rcx`, `rdx`, `r8`, `r9`, the rest on the
  stack above 32 bytes of *shadow space*
- a float argument goes in the `xmm` register of its *position*: the second
  argument in `xmm1` whatever the first one was
- results come back in `rax`, or `xmm0` for a float
- `rbx`, `rsi`, `rdi`, `rbp`, `r12`-`r15` and `xmm6`-`xmm15` survive a call;
  everything else may not

An include proc's comment says what it takes and returns in registers, with
the size: `; ecx: bind flags, rdx: data, r8d: size -> rax: ID3D11Buffer`. A
32-bit parameter (`ecx`) reads only the low half, so passing a 64-bit
register there is fine. The parameter list in the declaration
(`create_buffer: proc(bind: u32, data: *const void, size: u32) -> *ID3D11Buffer`)
is documentation and the C prototype; a parameter name is not an operand.

## Frames

There is no `STACKFRAME`, no `USING`/`SaveRegs`, no prologue: every proc
writes its own. The shape is always

    window_begin: proc(color: *const f32) = {
        push rbx
        sub rsp, 48                ; ClearDepthStencilView takes 5: 32 + 8; entry 8 + push 8 + 48 lands on 16
        ...
        add rsp, 48
        pop rbx
        ret
    }

- **push** the callee-saved registers the proc uses, first.
- **sub rsp, N**: N is at least 32 (shadow space) plus 8 for every stack
  argument of the biggest call the proc makes (an `invoke` with 7 arguments
  needs 32 + 24, a `vcall` counts `this` too: 6 arguments past it need
  32 + 24), and rsp must end on 16. At entry rsp is 8 mod 16, so with k
  pushes, `8 + 8k + N` must be a multiple of 16. The comment on the `sub`
  says both: why N, and that it lands on 16.
- the epilogue undoes it in reverse, before every `ret`.
- `main` ends in `invoke(ExitProcess, 0)`, which does not return, so it has
  no epilogue.

Variations used on purpose, each with a comment where it happens:

- **A leaf** (no calls) has no frame: most of `math.rasm` and `cstr.rasm`.
- **A tail call** is a `jmp`: `window_proc` jumps to `DefWindowProcA` with
  all four arguments still in place; `camera_create` ends in
  `jmp camera_update_vectors`.
- **A call to a known leaf of the same file** may skip alignment and shadow
  space when the callee touches neither the stack nor aligned memory:
  `m4_translate` calls `m4_identity` straight away. Stated at each place,
  because nothing checks it.
- **The shadow space is the callee's scratch**: `sinf` stores xmm0 at
  `[rsp + 8]`, its own rcx home; `m4_rotate` keeps `out` and `angle` in its
  homes `[rsp + 48]`, `[rsp + 56]` after its `sub rsp, 40`.
- **Your own stack arguments** are at `[rsp + 40]`, `[rsp + 48]`, ... at entry,
  so after k pushes and `sub rsp, N` the fifth is at `[rsp + 40 + 8k + N]`:
  `shader_compile` reads its target at `[rsp + 144]` (40 + 8 + 96), and
  `draw_vertices` its model at `[rsp + 128]` (40 + 32 + 56). Write the sum in
  the comment.

## No locals: globals, named after their proc

MASM's `local` variables are globals. Each is named after the include or proc
that owns it (`window_create_wc`, `shader_create_blob`, `load_texture_desc`,
`look_at_f`), declared with its real type from the binding, and initialised
with everything that is known before the program runs:

    load_texture_desc: D3D11_TEXTURE2D_DESC = {
        .MipLevels = 0,                        ; the whole chain
        .ArraySize = 1,
        .SampleDesc = { .Count = 1 },
        .BindFlags = D3D11_BIND_FLAG.D3D11_BIND_SHADER_RESOURCE | D3D11_BIND_FLAG.D3D11_BIND_RENDER_TARGET,
        .MiscFlags = D3D11_RESOURCE_MISC_FLAG.D3D11_RESOURCE_MISC_GENERATE_MIPS,
    }

so the code stores only what changes (`Width`, `Height`, `Format`), and the
`mem_zero` + field stores MASM needed are gone. A struct written once and
never changed (a rasterizer desc, a depth buffer's desc) is all initialiser.
The debugger shows every one by name, type and field.

What a proc keeps across calls lives in callee-saved registers (`rbx`,
`rsi`, `rdi`, `r12`-`r15`), saved by its own pushes. A value handed to a COM
method by address ("an array of one", an out-parameter) is a global too:
`bind_constants_buffer`, `create_buffer_out`. The price is that these procs
are not reentrant, which nothing here needs.

A lesson's globals are named as masm64-dx11 names them, minus MASM's
workarounds: `offset`, `scale`, `width`, `size` are all free (rasm quotes
every symbol it emits). Two namespaces still bite:

- **C's.** Every global is a C variable in the data file, which includes
  `windows.h`. C keywords cannot be names, and neither can the macros
  `windows.h` defines: `near`, `far`, `min`, `max`, `small`, `interface`,
  `IN`, `OUT`, `CONST`, `VOID`, `TRUE`, `FALSE`, `ERROR`... (`far: f32` fails
  with "expected identifier" in `build/rasm/<name>_data.c`). `z_near`/`z_far`.
- **The program's.** All globals and procs of a program share one namespace,
  includes' included, which is why they carry their include's prefix.
  Labels do not: a label is local to its proc (`.Lrasm_<proc>_<label>`), so
  `done:` and `scan:` are used everywhere.

## invoke and vcall

`invoke(f, a1, ..., an)` and `vcall(obj, Vtbl.Method, a1, ...)` are macros in
`includes/calls.rasm`, one definition per argument count. What they emit is
exactly:

    invoke(f, a, b, c, d, e)        mov r11, e / mov qword ptr [rsp + 32], r11
                                    mov rcx, a / mov rdx, b / mov r8, c / mov r9, d
                                    call f
    vcall(obj, M, a, b, c, d)       mov r11, d / mov qword ptr [rsp + 32], r11
                                    mov rcx, obj / mov rdx, a / mov r8, b / mov r9, c
                                    mov r10, [rcx] / call [r10].M

The rules that follow from that, all of which were hit at least once:

- **Stack arguments first, through r11; then rcx, rdx, r8, r9 in order.** So
  r11 is never an argument to a call with more than four (three for vcall),
  and a register must not be passed after the register it would be moved
  into has been written: `invoke(D3DCompile, rdx, r8, rcx, ...)` passes the
  source as the path. Move it aside first (`shader_compile` keeps the path in
  rbx). In a vcall, rcx is written first of the registers (it is `this`), so
  rcx can only be a stack argument; `window_begin` keeps its colour in rbx.
- **rax and r10 are safe as any argument** of either (vcall loads r10 only
  after every argument has moved): every return value can be passed on
  directly (`invoke(load_texture, rax, 0)`).
  `window_create` passes its computed width and height as `rax, r10`,
  stack arguments 7 and 8.
- **Values move as 64 bits.** `mov rcx, some_u32_global` is a size error. A
  32-bit global goes into its argument register first and is passed as
  itself, `mov r8d, filesystem_read_size.u.LowPart` then
  `invoke(ReadFile, h, buf, r8, ...)` (the `mov r8, r8` this expands to is
  harmless), or into another 64-bit register (`mov edx, desc.Width`, passed
  as `rdx`). Immediates, `x&` addresses, pointer globals, 64-bit fields and
  typed memory operands (`[rbx].shader.layout`, `[rdi + rbx * 8]`,
  `window_create_wc.hInstance`) go straight in.
- **No arguments is `call f`**, not `invoke(f)`.
- **vcall's method is `Vtbl.Method`**, the struct of function pointers the
  binding has for every interface: `ID3D11DeviceContextVtbl.Draw`,
  `IWICBitmapEncoderVtbl.Commit`. The vtable goes through r10.
- **An undefined proc is not an assembler error**: a name the assembler does
  not know is taken as an external code symbol, so a missing `import` shows up
  as lld's "undefined symbol: filesystem_path", with the `.rasm` line.
- `release(obj)` (`includes/macros.rasm`) is `vcall(obj, IUnknownVtbl.Release)`;
  `assert_hr()` stops in the debugger (`int 3`) when eax holds a failed
  HRESULT, `assert_eq(a, b)` and `assert_not_eq(a, b)` check anything else.

## Floats

A float argument is set in its xmm register by hand, before the call, and a
placeholder stands in the argument list:

    movss xmm3, 1.0                        ; ClearDepthStencilView(this, dsv, flags, depth, stencil): depth is the 4th
    vcall(context, ID3D11DeviceContextVtbl.ClearDepthStencilView, depth_dsv,
          D3D11_CLEAR_FLAG.D3D11_CLEAR_DEPTH | D3D11_CLEAR_FLAG.D3D11_CLEAR_STENCIL, 0, 0)

A call that takes only floats and pointers is often clearer written out:
`lea rcx, rotation` / `movss xmm1, current_frame` / `lea r8, z_axis` /
`call m4_rotate`. A float stack argument is stored by hand into the outgoing
area: `movss dword ptr [rsp + 32], xmm0` (m4_perspective's z_far). A double
on the stack that is 0.0 can be passed as the integer 0
(`IWICFormatConverter::Initialize`'s alpha threshold).

Float literals replace `movf`, `storef` and `floats()`:

- **A float literal is memory**, a constant pooled in `.rdata`:
  `movss xmm0, 1.0`, `mulss xmm0, 0.5`, `divss xmm0, 120.0`. Instructions
  ending in `sd`/`pd` get a double: `movsd xmm1, 10.0`.
- `mov eax, 1.0` is therefore a *load* of the float's bits, legal and
  occasionally handy. A float **immediate** is written as its bits:
  `mov dword ptr [rcx].mat4.m[15], 0x3F800000`, `mov c.tint.w, 0x3F800000`.
- **A constant array** (a clear colour) is `const` data passed by address:
  `clear_color: [4]const f32 = { 0.2, 0.3, 0.3, 1.0 }`, then `clear_color&`.
- `andps`/`xorps` with a memory operand need it 16-aligned:
  `math_sign_mask: [4]const u32[align(16)]`. A 16-byte type sizes the operand
  as an xmmword by itself.
- `math.rasm` touches only xmm0-xmm5. `radians`, `sinf`, `cosf`, `tanf` and
  `m4_identity` touch xmm0 (and eax) only, and its own procs keep values in
  other registers across them, a private convention stated at the top of the
  file.

## Data and the binding

`includes/d3d11.rin` imports `gen/win32_d3d11.rin`, rinbind's declarations of
everything in the Win32, COM, D3D11, DXGI, D3DCompiler and WIC headers the
lessons use: every struct with clang's layout, every interface's `*Vtbl`,
every enum and object-like `#define`. `gen/gen_bindings.py` regenerates it,
one header per rinbind run; add a header to its list when an include needs
something new. GUIDs the headers declare `extern` are listed at the bottom
of `d3d11.rin` (`IID_ID3D11Texture2D: IID;`, `GUID_ContainerFormatPng: GUID;`)
and come from dxguid.lib and windowscodecs.lib. The WIC factory is
`CLSID_WICImagingFactory2`, which is what the header's
`CLSID_WICImagingFactory` means today.

Every offset the code uses is checked against C with a `_Static_assert` in
the data file, so a layout mistake is a build error naming the field.

- **Enum members are qualified**, in code and in data:
  `D3D11_USAGE.D3D11_USAGE_IMMUTABLE`, `DXGI_FORMAT.DXGI_FORMAT_R32_UINT`,
  `D3D11_BIND_FLAG.D3D11_BIND_VERTEX_BUFFER | ...`. An enum reached through
  a typedef works too (`D3D11_PRIMITIVE_TOPOLOGY.` is `D3D_PRIMITIVE_TOPOLOGY`).
  Header `#define`s (`WM_KEYDOWN`, `GENERIC_READ`, `D3DCOMPILE_DEBUG`) are
  plain names.
- **A `#define` is the compile-time constant**: an immediate in code, a value
  in an initialiser (`SCR_WIDTH`, `CUBE_STRIDE`). Function-like header macros
  are not evaluated: `IDC_ARROW` is `#define IDC_ARROW 32512` in the lesson.
  A `#define` line takes no `;` comment. A string `#define` is not an
  operand; write the literal, or read a pointer global
  (`window_create_wc.lpszClassName`).
- **`const` has storage** (`.rdata`, read-only): `scr_width: const u32` is
  what `cvtsi2ss xmm2, scr_width` reads. C does not accept a const variable
  in an initialiser, so initialisers use `SCR_WIDTH`.
- **Initialisers are C constant expressions**, folded by C:
  `cast(SCR_WIDTH, f32)`, `sizeof(WNDCLASSEXA)`, string literals, `x&`
  addresses (`.lpfnWndProc = window_proc&`), nested designated initialisers.
- **An array count is one number or one name**: `[288]const f32`, not
  `[36 * 8]` (rin's parser). Use a `#define` for anything computed.
- **Indices count elements**: `textures[1]` is the second pointer, 8 bytes
  in (MASM's `textures[8]`). An index on a global must be a constant; at run
  time, `lea rsi, name` and index `[rsi + rcx * 8]`.
- **A typed operand needs no size**: `mov eax, desc.Width`,
  `cmp window_msg.message, WM_QUIT`, `cmp filesystem_root[0], 0` (a byte).
  An explicit `T ptr` wins (`movups xmmword ptr [rcx], xmm0` into an f32
  field). A field through a register is `[rbx].shader.layout` or
  `[rcx].mat4.m[5]`.
- **Addresses**: `x&` (also `c.transform&`) is a 64-bit link-time constant,
  legal only as `mov r64, x&` (what invoke does with it) and in initialisers;
  `lea rcx, x` is the RIP-relative address. A string literal operand is the
  address of a pooled string.
- **Anonymous members are looked through, as in C**: rinbind writes a
  header's anonymous unions and structs as fields named `_anonN`, which C
  does not have, so a path skips them: `size.LowPart` (in `LARGE_INTEGER`),
  `rtv_desc.Texture2DArray.MipSlice` (in a view description's union).
- **A character literal is one character**: `'\\'`, `'1'`; MASM's two-char
  `'?#'` is an error now (it used to read only the first): write `0x3F23`.
  (Write `.rasm` files with an editor, not a shell here-document: a shell
  that eats one backslash turns `'\\'` into an unterminated `'\'`.)
- A struct body is one field per line; `;` starts a comment everywhere in a
  `.rasm` file.

## Macros

Textual, overloaded by argument count, with labels renamed per use. No
loops: MASM's `for row, <0, 16, 32, 48>` became a macro taking `row`,
invoked four times (`m4_mul_row`), and `row * 4 + 1` folds once substituted.
A macro cannot add an offset to a memory operand it was given, so `v3load`
and `v3store` take a base register (`lea rax, [rsi].camera.position` /
`v3load(xmm0, rax)`); `v3load_var(reg, global)` and `v3store_var` take a vec3
global, whose `.z` is an ordinary field once substituted. `m4_copy(dst, src)`
copies a mat4 between two registers' addresses through xmm0.

## Memory

There is no `malloc`. `saha.rasm` is the arena: one 4 GB reservation,
committed a page at a time; `filesystem` and `image` start it on first use.
Files, paths and images are pushed onto `arena` and kept for the life of the
program; `arenaGetPos(arena, saved)` / `invoke(arenaSetPos, arena&, saved)`
undo temporary work.

## The includes

What each takes and returns; the full comments are at each proc.

| include | procs (registers in -> out) |
|---|---|
| `calls.rasm` | `invoke`, `vcall` |
| `macros.rasm` | `assert_hr()`, `assert_eq(a, b)`, `assert_not_eq(a, b)`, `release(obj)` |
| `print.rasm` | `print`: rcx format, rdx/r8/r9 up to three values (wsprintfA: `%d %u %x %s %c`, no `%f`) |
| `cstr.rasm` | `cstr_length` rcx -> rax; `cstr_copy`, `cstr_append` rcx dst, rdx src; `cstr_equals`, `cstr_starts_with` -> eax; `cstr_find` -> rax offset or -1; `mem_copy` rcx, rdx, r8 count; `mem_zero` rcx, rdx count; `parse_int` rcx -> rax, rdx past; `parse_float` rcx -> xmm0, rax past |
| `saha.rasm` | `arena` (global), `arenaInit` rcx; `arenaPush`/`arenaPushZero` rcx arena, rdx size, r8 align -> rax; `arenaSetPos` rcx, rdx; macros `arenaGetPos(a, pos)`, `arenaPushArray(a&, T, count, align)` |
| `math.rasm` | `vec2 vec3 vec4 mat4`; `radians sinf cosf tanf` xmm0 -> xmm0; `powf` xmm0, xmm1; `clampf` xmm0, xmm1 lo, xmm2 hi; `srand` ecx, `rand` -> eax; `v3_add/sub/mul/cross` rcx out, rdx a, r8 b; `v3_scale` rcx, rdx, xmm2; `v3_dot` rcx, rdx -> xmm0; `v3_length` rcx -> xmm0; `v3_normalize` rcx, rdx; `v3_lerp` rcx, rdx, r8, xmm3; `v3_set` rcx, xmm1-3; `m4_identity` rcx; `m4_mul` rcx = rdx * r8; `m4_mul_v4`; `m4_transpose`, `m4_inverse`, `m4_normal_matrix`, `m4_without_translation` rcx, rdx; `m4_translate`, `m4_scale` rcx, rdx vec3; `m4_translate_scale` rcx, rdx, xmm2; `m4_rotate` rcx, xmm1 angle, r8 axis; `m4_perspective` rcx, xmm1 fovy, xmm2 aspect, xmm3 near, [rsp+32] far; `m4_ortho` rcx, xmm1-3, [rsp+32..48]; `m4_look_at` rcx, rdx eye, r8 target, r9 up; macros `v3load v3store v3load_var v3store_var splat m4_copy`; consts `math_one math_half math_pi math_sign_mask math_abs_mask` |
| `image.rasm` | `image` struct; `image_load` rcx image, rdx path -> rax pixels or 0; `image_load_hdr` same, float RGBA |
| `learn/filesystem.rasm` | `filesystem_path` rcx relative to the repository root -> rax; `filesystem_read` rcx path, rdx &size or 0 -> rax bytes + a zero, or 0 |
| `learn/window.rasm` | globals `window device context swap_chain backbuffer backbuffer_rtv raster_state viewport depth_texture depth_dsv scr_width scr_height`, `SCR_WIDTH SCR_HEIGHT`, `window_mouse_dx/dy window_scroll`; `window_create` rcx caption; `window_create_depth`; `window_begin` rcx colour (binds, clears colour and depth); `window_poll` -> eax 0 when closed; `window_present`; `get_time` -> xmm0; `key_down`, `key_pressed` ecx vk -> eax; `window_mode` ecx count -> eax; `window_mode_default` ecx |
| `learn/shader.rasm` | `shader` struct; `shader_create` rcx shader, rdx path, r8 layout, r9 count; `shader_use` rcx |
| `learn/gpu.rasm` | `create_buffer` ecx bind, rdx data, r8d size -> rax; `create_constant_buffer` ecx size; `update_buffer` rcx, rdx data, r8 size; `bind_constants` ecx slot, rdx buffer; `load_texture` rcx path, edx srgb -> rax srv; `create_sampler` ecx filter, edx address; `bind_texture` ecx slot, rdx srv; `unbind_textures`; `set_viewport` ecx w, edx h; `render_target` struct, `create_render_target` rcx, edx w, r8d h, r9d format, [rsp+32] samples; `create_depth_buffer` ecx w, edx h, r8d samples -> rax dsv; `load_cubemap` rcx 6 paths -> rax; `load_hdr` rcx path -> rax; `create_shadow_sampler` -> rax |
| `learn/cube.rasm` | `cube_vertices` (36 x 32 bytes), `cube_layout`, `CUBE_STRIDE`, `CUBE_LAYOUT_COUNT`, `cube_positions`, `cube_rotation_axis`; `cube_model` rcx out, edx i |
| `learn/camera.rasm` | `camera` struct; `camera_create` rcx, rdx position, xmm2 yaw, xmm3 pitch; `camera_view` rcx out, rdx cam; `camera_projection` rcx out, rdx cam; `camera_process_input` rcx cam, rdx &delta_time |
| `learn/transforms.rasm` | `transforms` struct (b0); `transforms_from_camera` rcx t, rdx cam; `draw_cube` rcx buffer, rdx t, r8 model; `draw_vertices` rcx buffer, rdx t, r8 vb, r9d count, [rsp+32] model |
| `learn/model.rasm` | `model_vertex` (32 bytes), `model` struct, `model_layout`, `MODEL_LAYOUT_COUNT`; `model_load` rcx model, rdx directory, r8 file, r9d flip_v; `model_draw` rcx model; `model_draw_instanced` rcx model, edx count |
| `learn/srgb.rasm` | `window_use_srgb`: backbuffer_rtv becomes an sRGB view |
| `learn/wall.rasm` | `wall_layout`, `WALL_STRIDE`, `WALL_LAYOUT_COUNT`; `create_wall` -> rax vertex buffer |
| `learn/shadow.rasm` | `shadow_map` struct {dsv, srv}; `create_shadow_map`, `create_depth_cube` rcx map, edx size; `cube_face_matrices` rcx out[6], rdx centre, xmm2 near, xmm3 far; `shadow_bias_state` -> rax |
| `learn/pbr.rasm` | `sphere`, `cube_target` structs; `create_sphere` rcx sphere, rdx segments; `draw_sphere` rcx buffer, rdx transforms, r8 sphere, r9 model; `load_material` rcx folder, rdx out[5]; `create_cube_target` rcx, edx size, r8d mips, r9d generate; `render_to_cube` rcx target, edx mip, r8 constants, r9 cube vb |

## Debugging

Visual Studio: `devenv /debugexe build\camera.exe`, open the `.rasm`, set a
breakpoint, F5. F10 steps a statement (a whole `invoke(...)` is one step:
every instruction of a macro carries the invocation's line), F11 enters a
call, and Watch shows any global with its type and fields.

lldb works too: `lldb build\camera.exe`, `b coordinate_systems.rasm:120`,
`r --shot x.png`, `bt`, `p cam`. Two snags:

- this LLVM's lldb needs `python311.dll` on `PATH` (and `PYTHONHOME` set to
  that Python) or it crashes at start-up;
- a file name is matched by its base name, and `src/.../7.1.camera/camera.rasm`
  and `includes/learn/camera.rasm` share one: `b camera.rasm:135` lands in
  the include. Give more of the path.

The generated `build/rasm/<name>.s` is worth reading when an instruction is
not what you meant: each line carries the field path it came from as a
comment (`mov qword ptr [rbx + 32], rax    # Arena.pagesize`).
