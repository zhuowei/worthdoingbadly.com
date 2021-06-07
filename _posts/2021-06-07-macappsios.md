---
title: Jailbroken iOS can't run macOS apps. I spent a week to find out why.
categories: ios, macos
permalink: /macappsios/
---

I ran command line macOS tools, such as Bash and Geekbench, on a jailbroken iPhone by replacing iOS's dyld shared cache (all of iOS's code) with macOS's. However, graphical apps will never work: macOS's WindowServer won't start, since iOS's drivers are too different.

# Introduction

On the eve of another WWDC, it's time to reflect on the theme that has linked the past 3 WWDCs: convergence between Apple's mobile and desktop lines.

In the past few years, we saw Apple unify:
- design: macOS Big Sur's iOS-inspired styling, iMacs adopting the iPhone's square lines and colourful back
- hardware: Apple Silicon on iPads and Macs, Smart Keyboard and trackpad on iPads
- software: Catalyst and iOS apps on macOS

With this unification, many were wondering: if the exact same processor can run macOS and iOS, what's stopping jailbreakers from running macOS apps on iOS?

As it turns out: many things.

Steve Jobs famously [announced](https://daringfireball.net/2007/01/os_x) that the iPhone "ran OS X". After a week's work, [we determined: that was a lie](https://miro.medium.com/max/600/1*bAUTC-8AK9WQ3A5BaZRhXw.jpeg). While iOS and macOS share a foundation, their driver are different enough to be incompatible.

Some part of the iOS kernel/drivers are shared with macOS. For example, both use the same kernel with the same Unix/Darwin foundation.

Thus, for running command line apps, all I needed to do was:
    - replace iOS's dyld with a patched macOS dyld
    - replace iOS's dyld cache with a re-signed macOS dyld cache
    - hook a few methods in the debugger

However, many drivers on iOS and macOS are different, even after Apple Silicon. macOS graphics code doesn't know how to talk to iOS kernel/drivers, so graphical apps cannot run.

There's also no way to replace the iOS kernel and drivers with the macOS equivalents: macOS only supports M1 devices, and no iOS devices past the iPhone X have known bootloader exploits. 

Getting macOS apps to run on iOS would require either a multi-year unification project comparable in scope to Catalyst, or isolate macOS in a VM similar to how Mac OS 9 ran in Classic mode on early OS X.

Neither of these options are available for jailbreakers, but they are available for Apple. So the best option is to cross my fingers for macOS-on-iOS in tomorrow's WWDC.

# Let's get started

So what happens if I just try to run a macOS application on a jailbroken phone?

All my tests are done on an iPhone 12 running iOS 14.1 and the Taurine (1.0.4) jailbreak. macOS files are taken from macOS 11.4 (although I did early tests with 11.3.1). 

If I run a macOS app directly on iOS, such as Geekbench's command line version, it errors immediately due to missing libraries:

```
Phone:~ root# /usr/local/zhuowei/geekbench_aarch64
dyld: warning: could not load inserted library '/usr/lib/pspawn_payload-stg2.dylib' into hardened process because no suitable image found.  Did find:
	/usr/lib/pspawn_payload-stg2.dylib: mach-o, but not built for platform macOS
	/usr/lib/pspawn_payload-stg2.dylib: mach-o, but not built for platform macOS
dyld: Library not loaded: /System/Library/Frameworks/Carbon.framework/Versions/A/Carbon
  Referenced from: /usr/local/zhuowei/geekbench_aarch64
  Reason: image not found
zsh: abort      /usr/local/zhuowei/geekbench_aarch64
```

For apps to run, we need to provide them with all the libraries available on macOS. To do that, we need to load the macOS dyld shared cache.

# The dyld platform

The dyld shared cache is a prelinked bundle of all the libraries of on iOS or macOS. It is loaded by `dyld`.

`/usr/bin/dyld` is the dynamic linker. When a program starts, the kernel loads that program and dyld into memory. dyld then loads all the other libraries needed by a program.

dyld has multiple debug options documented in `man dyld`, and its [source](https://opensource.apple.com/source/dyld/dyld-851.27/) is available online.

The dyld shared cache is usually shared by all the processes running on a device, but using two dyld flags, we can ask dyld to load our own shared cache file, separate from other processes.

If I put a macOS shared cache on my phone, I get:

```
Phone:~ root# DYLD_SHARED_REGION=private DYLD_SHARED_CACHE_DIR=/usr/local/zhuowei /usr/local/zhuowei/geekbench_aarch64 
dyld: dyld cache load error: shared cache file is for a different platform
```

This check is [performed](https://github.com/apple-opensource/dyld/blob/1128192c016372ae94793d88530bc5978c1fce93/dyld3/SharedCacheRuntime.cpp#L321) by `validatePlatform`: we can bypass it by forcing `MachOFile::currentPlatform` to return `Platform::macOS`:

I wasn't able to get my `debugserver` to launch an app in suspended mode, so I [made](https://github.com/zhuowei/iOS-run-macOS-executables-tools/blob/main/littlespawn/littlespawn.c) a tiny helper `littlespawn` tool which calls `posix_spawn` with the suspended flag.

```
Phone:~ root# xDYLD_SHARED_REGION=private xDYLD_SHARED_CACHE_DIR=/usr/local/zhuowei/System/Library/Caches/com.apple.dyld ./littlespawn /usr/local/zhuowei/bash 
```

This allows me to attach a debugger before dyld starts:

```
# debugserver 127.0.0.1:3335 --attach=bash
```

```
zhuowei-mac:src zhuowei$ lldb /bin/bash
(lldb) target create "/bin/bash"
Current executable set to '/bin/bash' (x86_64).
(lldb) process connect connect://localhost:3335
Process 858 stopped
* thread #1, stop reason = signal SIGSTOP
    frame #0: 0x00000001025d5000 dyld`_dyld_start
dyld`_dyld_start:
->  0x1025d5000 <+0>:  mov    x28, sp
    0x1025d5004 <+4>:  and    sp, x28, #0xfffffffffffffff0
    0x1025d5008 <+8>:  mov    x0, #0x0
    0x1025d500c <+12>: mov    x1, #0x0
Target 0: (bash) stopped.
(lldb) b dyld`dyld3::MachOFile::currentPlatform
Breakpoint 1: where = dyld`dyld3::MachOFile::currentPlatform(), address = 0x00000001025fe01c
(lldb) c
Process 858 resuming
Process 858 stopped
* thread #1, stop reason = breakpoint 1.1
    frame #0: 0x00000001025fe01c dyld`dyld3::MachOFile::currentPlatform()
dyld`dyld3::MachOFile::currentPlatform:
->  0x1025fe01c <+0>: mov    w0, #0x2
    0x1025fe020 <+4>: ret    

dyld`dyld3::MachOFile::isDylib:
    0x1025fe024 <+0>: ldr    w8, [x0, #0xc]
    0x1025fe028 <+4>: cmp    w8, #0x6                  ; =0x6 
Target 0: (bash) stopped.
(lldb) thread return 1
```

by returning 1 (Mac) in currentPlatform, the cache passes dyld's check... but now fails iOS's code signing check.

# The dyld cache

iOS rejects the signature on an unmodified macOS dyld shared cache, even when jailbroken:

```
Phone:~ root# xDYLD_SHARED_REGION=private xDYLD_SHARED_CACHE_DIR=/usr/local/zhuowei/System/Library/Caches/com.apple.dyld ./littlespawn /usr/local/zhuowei/bash 
dyld: dyld cache load error: code signature registration for shared cache failed
```

Looking at the logs, we see:

```
AMFI: '/private/var/root/osdoubler/macos/System/Library/dyld/dyld_shared_cache_arm64e' is adhoc signed.
AMFI: '/private/var/root/osdoubler/macos/System/Library/dyld/dyld_shared_cache_arm64e': unsuitable CT policy 0 for this platform/device, rejecting signature.
```

An ad-hoc signature is validated entirely in the kernel against a hard-coded list. This means that Taurine, a KPP-less jailbreak, can't override the signature check.

I needed to re-sign the shared cache with a normal, developer signature. Taurine can then intercept validations and instruct the `amfid` daemon to allow the code to execute.

To my surprise, Xcode's `codesign` can sign dyld caches, even though this feature is never used: the dyld cache builder always signs its own caches.

I wrote a [script](https://github.com/zhuowei/iOS-run-macOS-executables-tools/blob/main/resign_dyld_cache/resign.sh) to remove the existing signature and resign the dyld cache. However, loading the new cache causes Taurine's amfidebilitate to crash while computing the signed dyld cache's CDHash:

```
kernel	EXC_RESOURCE -> amfidebilitate[449] exceeded mem limit: InactiveHard 2098 MB (fatal)
kernel	1401.082 memorystatus: killing_specific_process pid 449 [amfidebilitate] (per-process-limit 3) 2331079KB - memorystatus_available_pages: 50117
kernel	AMFI: code signature validation failed.
osanalyticshelper	Process amfidebilitate [449] killed by jetsam reason per-process-limit
```

Thankfully, Taurine allows a user to [precompute](https://github.com/Odyssey-Team/Odyssey/blob/7682a881ffec2c43fe3ed856215ca08e1139fe9e/amfidebilitate/amfidhook.swift#L17) a file's CDHash by placing it in `/taurine/cstmp`, so I added a step to [extract](https://github.com/zhuowei/iOS-run-macOS-executables-tools/blob/c69d78f006b45874651ebec99adbf94264575174/resign_dyld_cache/resign.sh#L11) the CDHash.

After placing the file, the dyld cache started to load... until the iOS dyld set the wrong memory permission on a section:

```
Process 974 stopped
* thread #1, stop reason = EXC_BAD_ACCESS (code=2, address=0x1f53c8000)
    frame #0: 0x0000000100e85524 dyld`dyld3::loadDyldCache(dyld3::SharedCacheOptions const&, dyld3::SharedCacheLoadInfo*) + 700
dyld`dyld3::loadDyldCache:
->  0x100e85524 <+700>: str    x8, [x21]
    0x100e85528 <+704>: cbnz   x22, 0x100e85500          ; <+664>
    0x100e8552c <+708>: b      0x100e85554               ; <+748>
    0x100e85530 <+712>: add    x9, x24, w8, uxtw
Target 0: (bash) stopped.
(lldb) print (void*)$x21
(void *) $1 = 0x00000001f53c8000
```

That's fine: I just manually fixed the permission with a `mprotect`.

```
(lldb) print (int)mprotect((void*)$x21, 0x10000000, 0x3)
(int) $2 = 0
```

It's a kludge: we're going to replace dyld later anyways. For now, this gets us past dyld into a crash in the Objective-C runtime:

```
* thread #1, queue = 'com.apple.main-thread', stop reason = EXC_BAD_ACCESS (code=1, address=0x7c81fb1d9a80)
    frame #0: 0x000000018fef745c libobjc.A.dylib`addClassTableEntry(objc_class*, bool) + 32
libobjc.A.dylib`addClassTableEntry:
->  0x18fef745c <+32>: ldr    x8, [x0, #0x20]
    0x18fef7460 <+36>: and    x8, x8, #0x7ffffffffff8
    0x18fef7464 <+40>: ldrh   w8, [x8, #0x4]
    0x18fef7468 <+44>: adrp   x9, 438970
Target 0: (bash) stopped.
(lldb) bt
* thread #1, queue = 'com.apple.main-thread', stop reason = EXC_BAD_ACCESS (code=1, address=0x7c81fb1d9a80)
  * frame #0: 0x000000018fef745c libobjc.A.dylib`addClassTableEntry(objc_class*, bool) + 32
    frame #1: 0x000000018fedc5d8 libobjc.A.dylib`_read_images + 2624
    frame #2: 0x000000018fedb54c libobjc.A.dylib`map_images_nolock + 2464
    frame #3: 0x000000018feecc00 libobjc.A.dylib`map_images + 92
    frame #4: 0x0000000100e65b04 dyld`dyld::notifyBatchPartial(dyld_image_states, bool, char const* (*)(dyld_image_states, unsigned int, dyld_image_info const*), bool, bool) + 1672
    frame #5: 0x0000000100e65cf0 dyld`dyld::registerObjCNotifiers(void (*)(unsigned int, char const* const*, mach_header const* const*), void (*)(char const*, mach_header const*), void (*)(char const*, mach_header const*)) + 80
    frame #6: 0x000000019004e224 libdyld.dylib`_dyld_objc_notify_register + 284
```

# PAC

The address seems odd: `0x7c81fb1d9a80` is outside of memory, but if we remove the first three digits, `0x1fb1d9a80` is an actual Objective-C class. Where did those digits come from?

After putting breakpoints, I found that the crashing call is the second (recursive) `addClassTableEntry` call that adds the metaclass. To do that, it [fetches](https://github.com/apple-opensource/objc4/blob/a367941bce42b1515aeb2cc17020c65e3a57fa20/runtime/objc-runtime-new.mm#L534) the metaclass from the ISA pointer:

```
        addClassTableEntry(cls->ISA(), false);
```

the `ISA` call [strips](https://github.com/apple-opensource/objc4/blob/21ceada3638fefd874f7cdd10901276f84e9ee31/runtime/objc-object.h#L232) out the ISA PAC signing with a bitmask:

```
        clsbits &= objc_debug_isa_class_mask;
```

```
const uintptr_t objc_debug_isa_class_mask  = ISA_MASK & coveringMask(MACH_VM_MAX_ADDRESS - 1);
```

which is computed at compile time. However, `MACH_VM_MAX_ADDRESS` differs on iOS and macOS, since iOS has a smaller address space and uses more bits in the pointer for PAC signatures.

PAC is configured by the kernel, so a macOS app running on an iOS kernel will receive more bits of PAC signature than expected, causing PAC bits to be left over in the pointer after masking.

The solution was simple: [patch](https://github.com/zhuowei/iOS-run-macOS-executables-tools/blob/main/resign_any_executable/build.sh) any arm64e apps to launch as arm64 instead, disabling PAC.

# osvariant

The next crash came during libc startup:

```
(lldb) c
Process 1012 resuming
Process 1012 stopped
* thread #1, queue = 'com.apple.main-thread', stop reason = EXC_BREAKPOINT (code=1, subcode=0x182700e70)
    frame #0: 0x0000000182700e70 libsystem_darwin.dylib`_check_internal_content.cold.1 + 24
libsystem_darwin.dylib`_check_internal_content.cold.1:
->  0x182700e70 <+24>: brk    #0x1

libsystem_darwin.dylib`os_variant_has_internal_diagnostics.cold.1:
    0x182700e74 <+0>:  pacibsp 
    0x182700e78 <+4>:  stp    x29, x30, [sp, #-0x10]!
    0x182700e7c <+8>:  mov    x29, sp
Target 0: (bash_arm64) stopped.
(lldb) bt
```

Turns out macOS and iOS stores [information](https://github.com/apple-opensource/Libc/blob/1e58108100bb5978535e093c14e5a3eebc666b70/libdarwin/variant.c#L108) about build info (beta/internal) in the `kern.osvariant_status` sysctl variable. The iOS version has bits set that confused macOS.

Solution: hook `sysctlbyname` to return a known good macOS value.

This was, finally, enough to run `bash` from macOS:

```
Phone:~ root# xDYLD_SHARED_REGION=private xDYLD_SHARED_CACHE_DIR=/usr/local/zhuowei ./littlespawn /usr/local/zhuowei/bash_arm64
dyld: warning: could not load inserted library '/usr/lib/pspawn_payload-stg2.dylib' into hardened process because no suitable image found.  Did find:
	/usr/lib/pspawn_payload-stg2.dylib: mach-o, but not built for platform macOS
	/usr/lib/pspawn_payload-stg2.dylib: mach-o, but not built for platform macOS

The default interactive shell is now zsh.
To update your account to use zsh, please run `chsh -s /bin/zsh`.
For more details, please visit https://support.apple.com/kb/HT208050.
%m%::%~ %n%#
```

but many other executables still fail to load, because the dyld tries to load iOS libraries from disk:

```
xDYLD_SHARED_REGION=private xDYLD_SHARED_CACHE_DIR=/usr/local/zhuowei DYLD_ROOT_PATH=/usr/local/zhuowei ./littlespawn /usr/local/zhuowei/WindowServer_arm64
dyld: warning: could not load inserted library '/usr/lib/pspawn_payload-stg2.dylib' into hardened process because no suitable image found.  Did find:
	/usr/lib/pspawn_payload-stg2.dylib: mach-o, but not built for platform macOS
	/usr/lib/pspawn_payload-stg2.dylib: mach-o, but not built for platform macOS
dyld: Library not loaded: /usr/lib/libpam.2.dylib
  Referenced from: /System/Library/Frameworks/Security.framework/Versions/A/Security
  Reason: no suitable image found.  Did find:
	/usr/lib/libpam.2.dylib: mach-o, but not built for platform macOS
	/usr/lib/libpam.2.dylib: mach-o, but not built for platform macOS
	/usr/lib/libpam.2.dylib: mach-o, but not built for platform macOS
	/usr/lib/libpam.2.dylib: mach-o, but not built for platform macOS
```

Even adding `DYLD_ROOT_PATH` to prefix all the search paths didn't help.

# patching dyld to prevent loading libraries outside my dir

It turns out `dyld` will always try the [original, unprefixed path](https://github.com/apple-opensource/dyld/blob/1128192c016372ae94793d88530bc5978c1fce93/src/ImageLoaderMachO.cpp#L1548) as a last resort.

To bypass this, I decided to just patch `dyld`'s `stat64` method such that, if a path doesn't begin with `/usr/local/zhuowei`, always return file not found.

I used a macOS dyld as a base, and added [the extra code](https://github.com/zhuowei/iOS-run-macOS-executables-tools/blob/main/resign_dyld/thepatch.c) on [top](https://github.com/zhuowei/iOS-run-macOS-executables-tools/blob/main/resign_dyld/thepatch_full.s) of some ClosureWriter stuff that isn't usually used during app launch.

Since there's no way to specify which `dyld` to use during app launch, I start the app suspended, then run a [tool](https://github.com/zhuowei/iOS-run-macOS-executables-tools/blob/main/dyldloader/dyldloader.c) to replace the dyld in the app's memory using `vm_remap`.

This prevented dyld from attempting to load libraries outside my little sandbox.

As a bonus, using a real macOS dyld instead of the iOS one lets us get rid of the `currentPlatform` breakpoint and the `mprotect` workaround.

# A running command line app

This was enough to run Geekbench's command line version:

```
Phone:~ root# xDYLD_SHARED_REGION=private xDYLD_SHARED_CACHE_DIR=/usr/local/zhuowei ./littlespawn /usr/local/zhuowei/geekbench/Geekbench\ 5.app/Contents/Resources/geekbench_aarch64 
dyld: warning: could not load inserted library '/usr/lib/pspawn_payload-stg2.dylib' into hardened process because no suitable image found.  Did find:
	/usr/lib/pspawn_payload-stg2.dylib: stat() failed with errno=78
Geekbench 5.4.1 Tryout : https://www.geekbench.com/

Geekbench 5 requires an active Internet connection when in tryout mode and 
automatically uploads benchmark results to the Geekbench Browser.

Buy a Geekbench 5 license from the Primate Labs Store to enable offline use 
and unlock other features:

  https://store.primatelabs.com/v5

Enter your Geekbench 5 license using the following command line:

  /usr/local/zhuowei/geekbench/Geekbench 
5.app/Contents/Resources/geekbench_aarch64 --unlock <email> <key>

  Running Gathering system information
System Information
  Operating System              macOS 14.1 (Build 18A8395)
  Model                         D53gAP
  Model ID                      D53gAP
  Motherboard                   D53gAP
```

The results were [exactly](https://browser.geekbench.com/v5/cpu/8275456) 30% of a normal iPhone 12 benchmark, likely as a result of iOS throttling background processes.

# WindowServer

Command line apps run fine on iOS since the Unix API interface between a command line app and the kernel is 30 years old and doesn't differ from macOS and iOS.

Unfortunately, this doesn't apply to graphical apps, as iOS's graphics stack and macOS's graphics stack were developed separately over a decade.

Even after macOS adopted some of iOS's features (eg IOMobileFramebuffer) as part of the Apple Silicon transition, iOS's graphics and input drivers still present a different interface, and won't work with a macOS userspace.

I tried running `WindowServer`, responsible for rendering windows on macOS, using my tools. It didn't work, and shows how much convergence work Apple still needs to do to unify iOS and macOS.

- First, it errored out because [IOHIDSystem](https://opensource.apple.com/source/IOHIDFamily/IOHIDFamily-1633.100.36/IOHIDSystem/IOHIDSystem.cpp.auto.html), a driver responsible for mouse cursors and keyboard control, is completely missing on iOS. I bypassed that with `-virtualonly`, but..
- IOSurface looks for the `IOSurfaceRoot` driver instead of iOS's `IOCoreSurfaceRoot`. Patched that and got...
- Metal looking for macOS's `IOAccelerator` instead of iOS's `IOGPU`. I tried forcing this, and it didn't work.
- After I set breakpoints to pretend to have 0 screens, skip input initialization, and skip Metal initialization, WindowServer decided to just give up and segfault. (setting [memory debug flags](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/ManagingMemory/Articles/MallocDebug.html) suggest it's a use-after-free error, since the address is all 0x55s. I guess it didn't expect 0 screens?)

I, too, give up.

# Conclusion

Put macOS on iPad, you [cowards](https://www.theverge.com/2021/4/22/22396449/apple-ipad-pro-macbook-air-macos-2021).

# What I learned

- how to speedrun through writing yet another crappy Mach-O executable loader (any%, glitchless)
- how to deal with code signing on jailbroken iOS
- why Catalyst took Apple years to build
- if Apple ever implements reverse-Catalyst, it would probably be in a VM/Classic environment, not seamless: there's just too many differences and not enough demand to justify another multi-year unification project
- I should stop doing my research in the last hours before WWDC so I'd have time to revise this post instead of uploading my first draft