---
title: Compile Metal shader Bitcode to x86 and ARM assembly
categories: ios, llvm
permalink: /metalbitcode/
---

Here's how I reverse engineered Apple's `metallib` archive format to extract the LLVM Bitcode for compiled Metal shaders. I proved that normal LLVM can read the Bitcode and compile it to x86-64 and ARM64 assembly.

## Introduction

Apple introduced the Metal graphics API in 2014. It shares many ideas with the other next-gen graphics APIs. In particular, like Vulkan's SPIR-V, Metal's shaders are compiled ahead of time to a binary shader format.

So what is Metal's shader format? Posts such as [this Stack Overflow question](https://gamedev.stackexchange.com/questions/136246/what-is-the-shader-format-for-metal-shaders-shipped-with-ios-applications) and [this Twitter exchange](https://twitter.com/zeuxcg/status/785516557925425152) agree that Metal shaders are compiled to modified LLVM Bitcode, but how compatible is this Bitcode with normal LLVM? Can regular LLVM tools operate on compiled Metal shaders?

Let's find out.

All source code is on [my GitHub](https://github.com/zhuowei/MetalShaderTools).

## What's an air file?

I downloaded [Apple's HelloTriangle](https://developer.apple.com/documentation/metal/hello_triangle) shader [sample](https://github.com/zhuowei/MetalShaderTools/blob/master/sampleshader/AAPLShaders.metal), and followed [Apple's instructions](https://developer.apple.com/documentation/metal/tools_profiling_and_debugging/building_a_library_with_metal_s_command_line_tools) to compile the shader:

```
xcrun -sdk iphoneos metal -c AAPLShaders.metal -o MyLibrary.air
```

The `MyLibrary.air` file is the compiled version of the shader: it's similar to the `.o` files output by a regular compiler.

What is the type of the file? I can use the `file` utility to check:

```
$ file sampleshader/MyLibrary.air 
sampleshader/MyLibrary.air: LLVM bitcode, wrapper
```

... it's that simple? It's just straight up LLVM Bitcode? I checked the header in a hex editor:

```
00000000   DE C0 17 0B  00 00 00 00  14 00 00 00  30 0E 00 00  ............0...
00000010   FF FF FF FF  42 43 C0 DE  35 14 00 00  03 00 00 00  ....BC..5.......
```

Yep: it has LLVM Bitcode's "`DE C0 17 0B`" magic number (that's [`0x0b17c0de`](https://llvm.org/docs/BitCodeFormat.html#bitcode-wrapper-format) in little endian order.)

So .air files are just normal Bitcode files. But that's not what the Metal API loads.

## What's a metallib file?

The Apple documentation states that, in order to load the shader I compiled, I need to convert the `.air` file to a `.metallib` file.

```
xcrun -sdk iphoneos metallib MyLibrary.air -o MyLibrary.metallib
```

The output `MyLibrary.metallib` file is definitely custom: `file` doesn't recognize it.

```
$ file sampleshader/MyLibrary.metallib 
sampleshader/MyLibrary.metallib: data
```

Let's see what's inside.

## Extracting a metallib file

So how do I reverse engineer a binary format? By recognizing patterns and making guesses.

### How to understand a simple container format

I started with the hex dump of the file:

```
00000000: 4d 54 4c 42 01 00 02 00 02 00 00 00 00 00 00 00  MTLB............
00000010: 32 15 00 00 00 00 00 00 58 00 00 00 00 00 00 00  2.......X.......
00000020: 06 01 00 00 00 00 00 00 62 01 00 00 00 00 00 00  ........b.......
00000030: 10 00 00 00 00 00 00 00 72 01 00 00 00 00 00 00  ........r.......
00000040: 10 00 00 00 00 00 00 00 82 01 00 00 00 00 00 00  ................
00000050: b0 13 00 00 00 00 00 00 02 00 00 00 82 00 00 00  ................
00000060: 4e 41 4d 45 0d 00 76 65 72 74 65 78 53 68 61 64  NAME..vertexShad
00000070: 65 72 00 54 59 50 45 01 00 00 48 41 53 48 20 00  er.TYPE...HASH .
00000080: 6d 1c 6e 48 df 84 fe 19 5a ad 33 01 96 29 15 20  m.nH....Z.3..). 
00000090: ec fd 0e 31 08 a8 82 bd 39 de c3 69 cf ac b8 ff  ...1....9..i....
000000a0: 4d 44 53 5a 08 00 f0 0a 00 00 00 00 00 00 4f 46  MDSZ..........OF
000000b0: 46 54 18 00 00 00 00 00 00 00 00 00 00 00 00 00  FT..............
000000c0: 00 00 00 00 00 00 00 00 00 00 00 00 56 45 52 53  ............VERS
000000d0: 08 00 02 00 00 00 02 00 00 00 45 4e 44 54 84 00  ..........ENDT..
000000e0: 00 00 4e 41 4d 45 0f 00 66 72 61 67 6d 65 6e 74  ..NAME..fragment
000000f0: 53 68 61 64 65 72 00 54 59 50 45 01 00 01 48 41  Shader.TYPE...HA
00000100: 53 48 20 00 21 8a 2e 33 ea 7a 11 6b 76 97 bb 2d  SH .!..3.z.kv..-
00000110: b8 d0 5d ca 9d d8 67 57 68 b0 2c 24 05 c3 63 45  ..]...gWh.,$..cE
00000120: 3e b6 cb 8c 4d 44 53 5a 08 00 c0 08 00 00 00 00  >...MDSZ........
00000130: 00 00 4f 46 46 54 18 00 08 00 00 00 00 00 00 00  ..OFFT..........
00000140: 08 00 00 00 00 00 00 00 f0 0a 00 00 00 00 00 00  ................
00000150: 56 45 52 53 08 00 02 00 00 00 02 00 00 00 45 4e  VERS..........EN
00000160: 44 54 04 00 00 00 45 4e 44 54 04 00 00 00 45 4e  DT....ENDT....EN
00000170: 44 54 04 00 00 00 45 4e 44 54 04 00 00 00 45 4e  DT....ENDT....EN
00000180: 44 54 de c0 17 0b 00 00 00 00 14 00 00 00 dc 0a  DT..............
00000190: 00 00 ff ff ff ff 42 43 c0 de 35 14 00 00 03 00  ......BC..5.....
```
(more lines omitted)

### Immediately visible things

- There's a 4 byte magic number: "MTLB". I searched online: the only mention is [a Golang file](https://github.com/martinlindhe/formats/blob/master/parse/macos/macos_mtlb.go), which only checks for this magic number. That doesn't tell me anything. I'm on my own.
- Many 4 character strings, e.g. "NAME", "TYPE" - probably types of structures. Apple is fond of using four character [FourCC](https://en.wikipedia.org/wiki/FourCC) codes in file formats to denote tag types.
- The "`de c0 17 0b`" magic number shows up near the end! so there's some embedded Bitcode. A search shows that "`de c0 17 0b`" occurs twice...
- Once for each of the exported functions in the original shader: "vertexShader" and "fragmentShader".
- Those two function names from the shader also shows up, each after a "NAME" tag name.

**Hypothesis**: each exported function in the original .air file is split into a separate Bitcode file, and the header contains info on each exported function, including its name and the location of its Bitcode file in the container.

**Goal**: extract the embedded Bitcode for each function.

### Tag length

- After the "NAME" FourCC tag type, but before the function name string, there's two bytes: 

<pre><code>00000060: 4e 41 4d 45 <span style="color: red">0d 00</span> 76 65 72 74 65 78 53 68 61 64  NAME<span style="color: red">..</span>vertexShad
00000070: 65 72 00 54 59 50 45 <span style="color: blue">01 00</span> 00 48 41 53 48 20 00  er.TYPE<span style="color: blue">..</span>.HASH .
</code></pre>

it's "`0d 00`" here: if we interpret that as a 16-bit little endian integer, that's 13 bytes - exactly the length of the string that follows.

Looks like each function name has a length in front of it.

Next, look at the TYPE tag after the NAME tag: it's 3 bytes: if we also interpret the first two bytes as a length, we get "1" - matching the 1 byte payload.

**Hypothesis**: each tag consists of:

```
char tagtype[4]; // eg "NAME"
uint16_t size; // eg 0xd
char payload[]; // length of payload is equal to size. eg "vertexShader\0"
```

Note that while using 16-bit integers in file format is sometimes <i>short</i>sighted (see Android's [65k method limit](https://developer.android.com/studio/build/multidex)), in this case, it's justified: the longest tag is the NAME tag, and no shader will have a 65,000 character long function name. Thus, 16-bit integers can be used because they're comfy and easy to parse.

### Offsets

By searching for the "`de c0 17 0b`" magic, I found Bitcode at offsets `0x182` and `0xc72`.

Thus, the first Bitcode blob's size is `0xc72 - 0x182 = 0xaf0` bytes long. The file is `0x1532` bytes, , so the second blob's size is `0x8c0` bytes long.

I searched for these offsets and sizes in the file, to see if anything in the header points to these locations:

search for "82 01" (that's 0x182, the first Bitcode's offset, in little endian) shows "82 01 00 00" at offset 0x48:

<pre><code>00000000: 4d 54 4c 42 01 00 02 00 02 00 00 00 00 00 00 00  MTLB............
00000010: 32 15 00 00 00 00 00 00 58 00 00 00 00 00 00 00  2.......X.......
00000020: 06 01 00 00 00 00 00 00 62 01 00 00 00 00 00 00  ........b.......
00000030: 10 00 00 00 00 00 00 00 72 01 00 00 00 00 00 00  ........r.......
00000040: 10 00 00 00 00 00 00 00 <span style="color: red">82 01 00 00</span> 00 00 00 00  ................
</code></pre>

**Hypothesis**: Offset `0x48` in the header holds the file offset of the first Bitcode payload

search for "`f0 0a`" (the first Bitcode's length, 0xaf0) gives:

<pre><code>000000a0: 4d 44 53 5a 08 00 <span style="color: red">f0 0a 00 00</span> 00 00 00 00 4f 46  MDSZ..........OF
</code></pre>

**Hypothesis**: the "SZ" in "MDSZ" stands for "Size", and refers to the size of the Bitcode for that function

If these hypotheses are true, then we can read out each Bitcode file by:

- finding the first Bitcode offset from offset 0x48
- going to this offset
- reading the file using the size as shown in the MDSZ tag
- this brings us to the start of the next file.

To do this, I need to read through the tags describing each function - but where to start reading tags?

### Finding the offset of the first NAME tag

The first NAME tag occurs at offset `0x60`.

My previous strategy of searching for the offset didn't quite work: searching for `60` in the header didn't turn up anything. However, when examining the header, there is one integer: `0x58` at offset `0x18`:

<pre><code>00000000: 4d 54 4c 42 01 00 02 00 02 00 00 00 00 00 00 00  MTLB............
00000010: 32 15 00 00 00 00 00 00 <span style="color: red">58 00 00 00</span> 00 00 00 00  2.......X.......
</code></pre>

hmm, that's exactly 8 bytes before the NAME tag. What's there?

<pre><code>00000050: b0 13 00 00 00 00 00 00 <span style="color: red">02 00 00 00</span><span style="color: blue"> 82 00 00 00</span>  ................
00000060: 4e 41 4d 45 0d 00 76 65 72 74 65 78 53 68 61 64  NAME..vertexShad
</code></pre>

Let's look at the `82 00 00 00`: 0x82 bytes past the first NAME tag is exactly 4 bytes before the next NAME tag: (`0x82 + 0x60 = 0xe2`)

```
000000d0: 08 00 02 00 00 00 02 00 00 00 45 4e 44 54 84 00  ..........ENDT..
000000e0: 00 00 4e 41 4d 45 0f 00 66 72 61 67 6d 65 6e 74  ..NAME..fragment
```

**Hypothesis**: The `82 00 00 00` immediately before the NAME tag is the size of one function's header entry in the metallib

what's that "`02 00 00 00`" then? Remember, there's two Bitcode files, and two exported functions.

**Hypothesis**: this is the number of header entries in the metallib.

So it looks like the header entries follow this format:

- number of entries (2)
- first entry size (0x82)
- a bunch of tags (0x82 bytes long)
- second entry size (0x84)
- a bunch of tags (0x84 bytes long)

### Actually extracting metallib

Now that I know how a metallib is stored, I can try extracting the functions' Bitcode.

Procedure:

- find number of entries by following the offset at `0x18`
- for each entry:
  - read its length
  - parse its NAME tag for the function name
  - parse its MDSZ tag for its Bitcode's size
- now, start at the first Bitcode
- for each entry:
  - read its Bitcode, using the size from its MDSZ, and write it to a file based on its name

[I wrote a simple Python script](https://github.com/zhuowei/MetalShaderTools/blob/master/unmetallib.py) to do this, giving me .air Bitcode files bac. As expected, each contained one function, as shown by [disassembling with llvm-dis](https://github.com/zhuowei/MetalShaderTools/blob/master/sampleshader/out_vertexShader.air.ll).

### Limitations

I only tested this against a single metallib file, so more files would probably disprove my assumptions. This limited example does show how my reverse engineering process works.

## Lowering LLVM Bitcode to x86-64 and ARM64

Now that I have Bitcode, what to do with it? I know: I'll use it to settle an argument.

The purpose of LLVM Bitcode is often disputed. Sure, it's designed to provide a language independent representation of a program for link-time optimization and analysis. However, many people believe that Bitcode also allows cross compiling any program to any architecture. Indeed, when the iOS App Store added submission of LLVM Bitcode, some developers thought Apple was going to run iOS apps on Macs by translating the Bitcode to run on Intel processors.

Other developers promptly refuted that argument, arguing that Bitcode is absolutely tied to the original platform because the Bitcode contains the original architectures' calling conventions, alignment, data sizes, and memory model. They assert that without [significant work](https://llvm.org/devmtg/2011-09-16/EuroLLVM2011-MoreTargetIndependentLLVMBitcode.pdf), there's no hope of retargetting LLVM Bitcode to a new architecture. Instead, they explained, the App Store could only use Bitcode to re-compile a program for the same architecture to take advantage of compiler improvements.

The Metal shader Bitcode provides a great opportunity to test how much of each argument is true. After all, a GPU shader targets a very different programming model than regular CPUs. I can see how much target dependence is inherent in Bitcode by compiling a shader to x86 or ARM and observing what doesn't make sense.

I chose the `vertexShader` function from the sample shader: the original Metal shader source is:

```
vertex RasterizerData
vertexShader(uint vertexID [[vertex_id]],
             constant AAPLVertex *vertices [[buffer(AAPLVertexInputIndexVertices)]],
             constant vector_uint2 *viewportSizePointer [[buffer(AAPLVertexInputIndexViewportSize)]])
{
    RasterizerData out;
    out.clipSpacePosition = vector_float4(0.0, 0.0, 0.0, 1.0);
    float2 pixelSpacePosition = vertices[vertexID].position.xy;
    vector_float2 viewportSize = vector_float2(*viewportSizePointer);

    out.clipSpacePosition.xy = pixelSpacePosition / (viewportSize / 2.0);
    out.color = vertices[vertexID].color;
    return out;
}
```

Which is compiled to the Bitcode:

```
define %struct.RasterizerData @vertexShader(i32, %struct.AAPLVertex addrspace(2)* nocapture readonly, <2 x i32> addrspace(2)* nocapture readonly) local_unnamed_addr #0 {
  %4 = zext i32 %0 to i64
  %5 = getelementptr inbounds %struct.AAPLVertex, %struct.AAPLVertex addrspace(2)* %1, i64 %4, i32 0
  %6 = load <2 x float>, <2 x float> addrspace(2)* %5, align 16
  %7 = load <2 x i32>, <2 x i32> addrspace(2)* %2, align 8, !tbaa !16
  %8 = tail call fast <2 x float> @air.convert.f.v2f32.u.v2i32(<2 x i32> %7)
  %9 = fmul fast <2 x float> %6, <float 2.000000e+00, float 2.000000e+00>
  %10 = fdiv fast <2 x float> %9, %8
  %11 = shufflevector <2 x float> %10, <2 x float> undef, <4 x i32> <i32 0, i32 1, i32 undef, i32 undef>
  %12 = shufflevector <4 x float> <float undef, float undef, float 0.000000e+00, float 1.000000e+00>, <4 x float> %11, <4 x i32> <i32 4, i32 5, i32 2, i32 3>
  %13 = getelementptr inbounds %struct.AAPLVertex, %struct.AAPLVertex addrspace(2)* %1, i64 %4, i32 1
  %14 = load <4 x float>, <4 x float> addrspace(2)* %13, align 16, !tbaa !19
  %15 = insertvalue %struct.RasterizerData undef, <4 x float> %12, 0
  %16 = insertvalue %struct.RasterizerData %15, <4 x float> %14, 1
  ret %struct.RasterizerData %16
}
```

I finally use `llc` to [convert the Bitcode](https://github.com/zhuowei/MetalShaderTools/blob/master/sampleshader/process.sh#L5) to [x86_64](https://github.com/zhuowei/MetalShaderTools/blob/master/sampleshader/out_vertexShader.air.x86_64.s) and [ARM64](https://github.com/zhuowei/MetalShaderTools/blob/master/sampleshader/out_vertexShader.air.arm64.s) assembly. Here's the ARM64 assembly version:

```
	.globl	vertexShader
	.p2align	2
	.type	vertexShader,@function
vertexShader:                           // @vertexShader
// %bb.0:
	str	d8, [sp, #-32]!         // 8-byte Folded Spill
	stp	x29, x30, [sp, #16]     // 8-byte Folded Spill
	mov	w8, w0
	str	x19, [sp, #8]           // 8-byte Folded Spill
	add	x19, x1, x8, lsl #5
	ldr	d0, [x2]
	ldr	d8, [x19]
	add	x29, sp, #16            // =16
	bl	air.convert.f.v2f32.u.v2i32
	adrp	x8, .LCPI0_0
	ldr	q2, [x8, :lo12:.LCPI0_0]
	fadd	v3.2s, v8.2s, v8.2s
	ldr	q1, [x19, #16]
	ldp	x29, x30, [sp, #16]     // 8-byte Folded Reload
	ldr	x19, [sp, #8]           // 8-byte Folded Reload
	fdiv	v0.2s, v3.2s, v0.2s
	ext	v0.16b, v2.16b, v0.16b, #8
	ext	v0.16b, v0.16b, v0.16b, #8
	ldr	d8, [sp], #32           // 8-byte Folded Reload
	ret
.Lfunc_end0:
	.size	vertexShader, .Lfunc_end0-vertexShader
                                        // -- End function
```

## A look at the output

The output ARM assembly:

- actually follows the ARM calling convention: as expected, the first uint argument is passed in register `w0`, and the two pointers to structs are passed in `x1` and `x2`.
- The call to the Metal supporting library also respects the hardfloat calling convention, passing in the first vector argument in `d0`.
- the shader uniform annotation, specified with `constant` in the original Metal shader, and denoted by `addrspace(2)` in the LLVM bitcode, are completely discarded, since there's only one address space on ARM64, unlike GPUs with separate address spaces for varying attributes and uniform constants.
- uses ARM NEON to perform the vector divisions

So, to my surprise, LLVM produced fairly reasonable ARM assembly code from this shader. This suggests that a Bitcode based binary compatibility scheme is plausible: the basic code is faithfully translated, although running the code would require significant support code to paper over differences between the original and new architecture.

I wasn't surprised, though, that LLVM didn't produce fast assembly code suitable for a software renderer. Shaders use the [Single-Program, Multiple Data](https://en.wikipedia.org/wiki/SPMD) programming model, where the same shader code is run in parallel using many GPU cores to process many pixels at the same time. 

(More specifically, GPUs use [Single instruction, multiple threads](https://en.wikipedia.org/wiki/Single_instruction,_multiple_threads)).

To get fast performance in software renderers, the same model must be used. Aras-P [demonstrated with a raytracer](https://aras-p.info/blog/2018/04/10/Daily-Pathtracer-Part-7-Initial-SIMD/) that simply using SIMD instructions to compute one ray intersection at a time wasn't enough. SIMD only helped when the renderer was restructured to test multiple ray intersections at the same time.

There are custom programming languages [such as Intel ISPC](https://pharr.org/matt/blog/2018/04/18/ispc-origins.html) to make writing Single-Program, Multiple Data programs easier on CPUs, but as far as I know, there's no general purpose tool that takes any program written for GPU's implicit hardware parallelism and generates explicit parallelism for CPU SIMD instructions.

Without parallelism or a software renderer, compiling a Metal shader to ARM/x86 assembly code is mostly a curiousity, to demonstrate that LLVM can process bitcode from Metal shaders.

## Related projects

Other developers have already created really cool projects to work with Metal's Bitcode format:

a2flo made a [library named libfloor](https://github.com/a2flo/floor) that translates C++ to many GPU compute platforms; it generates Metal .air files using a patched LLVM

gzorin [built a wrapper](https://github.com/gzorin/LLAIR) around the `metal` and `metallib` Xcode tools to simplify generating and analyzing Metal bitcode from C++ programs.

## What I learned

- Metal shaders are just normal LLVM Bitcode and can be manipulated using the usual LLVM tools
- Experience in reverse engineering simple file formats often comes in handy
- A common shader IR is useful.
    - Without a common intermediate representation, each GPU vendor's driver must know how to parse, compile, optimize, and emit the shader. This causes duplication of work and [compatibility issues](https://dolphin-emu.org/blog/2013/09/26/dolphin-emulator-and-opengl-drivers-hall-fameshame/).
    - With one intermediate representation, the compile and optimize pass is done ahead of time, so drivers don't have to implement it themselves. In fact, with Metal, thanks to LLVM, even codegen can be shared between GPUs. This makes compatibility and driver development easier.
    - Perhaps this is why DirectX had an intermediate bytecode early on.
- LLVM won't magically turn your shader written for GPU into fast code for the CPU
- Apple's investment in LLVM is justified by LLVM's amazing versatility: Apple uses it in their:
    - OpenGL software renderer
    - compiler toolchain
    - App Store, with Bitcode submissions
    - Swift
    - and - now - Metal.
- I should revisit my old projects more often.
    - I first looked into Metal shader bitcode in 2016, but couldn't figure out how to turn it into a blog post until I added the metallib reverse engineering tutorial and the clickbait x86/ARM assembly recompile.