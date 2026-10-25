# 3. Model loading

LearnOpenGL loads models with Assimp, through its Model and Mesh classes.
Here a Wavefront `.obj` is read directly: the format is plain text, and
`includes/learn/model.rasm` is about six hundred lines of rasm, comments
included.

## 1 Model loading

`src/3.model_loading/1.model_loading/model_loading.rasm`, `includes/learn/model.rasm`

An `.obj` file is a list of lines:

    v  0.56 -0.02 -0.14      a position
    vt 0.37  0.82            a texture coordinate
    vn 0.00  1.00  0.00      a normal
    f  1/1/1 3/2/2 4/3/3     a face: position/uv/normal for each corner
    mtllib backpack.mtl      the material file

Faces index positions, coordinates and normals separately, counting from 1. A
GPU vertex needs all three together, so every corner of every face becomes one
vertex. The reader makes two passes: the first only counts, so each array is
allocated once at its final size in an arena; the second fills them.

The material file names the textures (`map_Kd` diffuse, `map_Ks` specular,
`map_Bump` normal), which `model_load` loads alongside, so the lesson calls
`model_draw` without knowing a file name; it binds the diffuse texture to t0,
specular to t1 and normal to t2. Its vertices are 32 bytes, position, normal,
uv, described to the input assembler by `model_layout` and
`MODEL_LAYOUT_COUNT`:

    invoke(shader_create, s&, "src/.../model_loading.hlsl", model_layout&, MODEL_LAYOUT_COUNT)
    invoke(model_load, backpack&, "resources/objects/backpack/", "backpack.obj", 0)
    ...
    invoke(model_draw, backpack&)

MASM's locals (the path being built, the word just read, the three corners
of the face being split into a fan) are globals named after their proc,
`model_load_path`, `model_load_first`, ..., so the debugger shows them by
name mid-load; the text, the arrays and the vertices are pushed onto `arena`
and kept.

The `flip_v` argument exists because `.obj` coordinates usually assume GL's
bottom-up v. Whether a model needs flipping depends on how its textures were
saved: the backpack's suit D3D as they are, the planet and rock of 4.10.1
need the flip. The test is to look at it.

**Try:** count the vertices a deduplicating loader would produce (hash each
`a/b/c` triple), and compare with the 200,000 corners loaded now.
