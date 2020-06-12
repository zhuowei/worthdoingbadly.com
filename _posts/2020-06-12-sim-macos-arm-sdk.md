---
title: Build macOS ARM apps in Xcode without a real macOS ARM SDK
categories: macos
permalink: /sim-macos-arm-sdk/
image: /assets/blog/sim-macos-arm-sdk/app.png
---
Here's a script that modifies Xcode's macOS SDK to build for ARM. You can use this to find code that won't compile on ARM, to get a head start on porting before Apple releases Xcode for an ARM Mac.

![Screenshot saying "You can't open the application MacOSSwiftEvaluation.app because it's not supported on this type of Mac](/assets/blog/sim-macos-arm-sdk/arm64eapp.png){: width="425" height="150"}

# What it's for

An app built with this SDK **won't actually work** on ARM.

[The script](https://github.com/zhuowei/fake-arm-macOS-sdk) literally just replaces every instance of `x86_64` in the current macOS SDK with `arm64e`, so most structures and methods won't match a real ARM macOS.

This is only intended to help you identify code and third-party libraries that won't compile on ARM.

# Thanks

Thanks to [@stroughtonsmith](https://twitter.com/stroughtonsmith), who [discovered](https://twitter.com/stroughtonsmith/status/807664599260688384) how to [modify Xcode](https://twitter.com/stroughtonsmith/status/1232104689069674496) to [build for ARM macOS](https://twitter.com/stroughtonsmith/status/1270902332373585922).

# How to use

First, generate the SDK. I tested this with Xcode 11.0 on macOS 10.15.5, but it'll likely work for newer Xcode versions.

Clone the generator script to a path without spaces, and generate the modified SDK:

```
git clone https://github.com/zhuowei/fake-arm-macOS-sdk
cd fake-arm-macOS-sdk
./makesdk.sh
```

This will print something like

```
Deleting and recopying /Users/zhuowei/Documents/fake-arm-macOS-sdk/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk
Copying some iOS files over
Editing tbd files
Editing headers
Editing Swift modules
```

Edit your Xcode project to use this SDK:

- Base SDK: the path of the generated SDK.
- Architectures: `arm64e`
- Valid architectures: `x86_64 arm64e`

![Screenshot of Xcode with the above settings](/assets/blog/sim-macos-arm-sdk/xcodeproject.png)

Product -> Clean Build Folder, then Product -> Build.

If it works, you'll end up with an app that shows this when opened:

![Screenshot saying "You can't open the application MacOSSwiftEvaluation.app because it's not supported on this type of Mac](/assets/blog/sim-macos-arm-sdk/arm64eapp.png){: width="425" height="150"}

Alternatively, you can also compile on the command line:

```
clang -target arm64e-apple-macosx10.15.0 -isysroot <path to MacOSX.sdk> hello.c
swiftc -target arm64e-apple-macosx10.15.0 -sdk <path to MacOSX.sdk> hello.swift
```

# Known issues

- `./makesdk.sh` won't work in a path with spaces.
- Apps built with this (probably) won't work on an actual ARM macOS.
- Deprecated methods are still present, since this is just a find-and-replace on the current macOS SDK.

Apple is known to remove deprecated APIs during transitions; for example, Catalyst doesn't include any deprecated methods from iOS, and Carbon was never made available to 64-bit.

You should look at the compiler warnings and remove uses of deprecated APIs.

- Core Data doesn't compile:

```
error: Cannot run cdtool because either it or the simulator runtime cannot be found. ('(null)' : 'Cannot find a simulator runtime for platform (null).') [0]
```
- LLVM's Sanitizers are not supported.

# Example: auditing iTerm 2's source for ARM incompatibilities

Building iTerm2 with the modified SDK identifies [one piece of code](https://github.com/gnachman/iTerm2/blob/72e74adcab00c3395cd65f6601146bf06197972b/sources/iTermBacktrace.mm#L115) that is x86 specific (and that the iTerm2 author noted won't work on ARM)

![Screenshot of the linked code](/assets/blog/sim-macos-arm-sdk/iterm2havefun.png)

as well as a number of third-party binary libraries without ARM versions:

```
ld: warning: ignoring file /Users/zhuowei/Documents/repos/iTerm2/ThirdParty/libsixel/lib/libsixel.a, building for macOS-arm64e but attempting to link with file built for macOS-x86_64
```

```
ld: warning: ignoring file /Users/zhuowei/Documents/repos/iTerm2/BetterFontPicker/BetterFontPicker.framework/BetterFontPicker, building for macOS-arm64e but attempting to link with file built for macOS-x86_64
ld: warning: ignoring file /Users/zhuowei/Documents/repos/iTerm2/SearchableComboListView/SearchableComboListView.framework/SearchableComboListView, building for macOS-arm64e but attempting to link with file built for macOS-x86_64
ld: warning: ignoring file /Users/zhuowei/Documents/repos/iTerm2/ThirdParty/NMSSH.framework/NMSSH, building for macOS-arm64e but attempting to link with file built for macOS-x86_64
ld: warning: ignoring file /Users/zhuowei/Documents/repos/iTerm2/ColorPicker/ColorPicker.framework/ColorPicker, building for macOS-arm64e but attempting to link with file built for macOS-x86_64
ld: warning: ignoring file /Users/zhuowei/Documents/repos/iTerm2/ThirdParty/CoreParse.framework/CoreParse, building for macOS-arm64e but attempting to link with file built for macOS-x86_64
ld: warning: ignoring file /Users/zhuowei/Documents/repos/iTerm2/ThirdParty/Sparkle.framework/Sparkle, building for macOS-arm64e but attempting to link with file built for macOS-x86_64
```

# What I learned

- Thanks to `.tbd` files, it's not too difficult to modify the SDKs shipped in Xcode
- modern Xcode only reads SDKSettings.json, not SDKSettings.plist
- float to int casts saturate on ARM, [just like PowerPC](https://twitter.com/zhuowei/status/1270878992007155718)
- When Swift compiles a .swiftinterface to a binary .swiftmodule, errors aren't printed until the process completes. This means that it could get stuck for [20 minutes](https://twitter.com/zhuowei/status/1270897523176214529) with no output.
- Apple's Metal compiler actually checks if the SDK path contains "MacOSX.platform" to determine whether to compile for macOS or iOS