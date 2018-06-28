---
title: Fixing macOS native tabs for Visual Studio Code
categories: macos, vscode
permalink: /vscodetabs/
---

I helped track down the misbehaving macOS compatibility patch that broke native tabs support in VS Code. I also learned to avoid introducing new bugs in bugfixes.

## Introduction

After writing the [AppKit Bundle ID post](/appkitcompat/), a Visual Studio Code developer [reached out to me](https://github.com/Microsoft/vscode/issues/35361#issuecomment-395971178) about one misbehaving bundle ID check.

VSCode, it turns out, couldn't display native macOS tabs on High Sierra: after selecting Window->Merge Window, there should be a tab bar at the top of the window:

![screenshot with tab bar on top of window]({{ "/assets/blog/vscodetabs/tabs_working.png" | absolute_url }})

But on High Sierra, the bar is completely empty:

![screenshot with an empty macOS tab bar]({{ "/assets/blog/vscodetabs/tabs_broken.png" | absolute_url }})

(screenshot by [@ddotlic](https://github.com/Microsoft/vscode/issues/35361#issuecomment-333064758))

The VS Code developers realized the issue only happens if the bundle ID begins with `com.microsoft.` Changing the bundle ID to `com.microsoft2.VSCode` fixes it.

This definitely sounds like a misbehaving compatibility patch, since it's only applied to specific bundle IDs. But which one? And how can we disable it?

## Narrowing down the issue

I was able to reproduce the issue, and confirmed that changing the bundle ID fixes it. 

I then started looking for the misbehaving patch. I found the "com.microsoft." text when running `strings` on AppKit: so it's checking it somewhere. However, IDA Free's "Xref" command showed multiple method all checking for `com.microsoft.` as a bundle prefix. Thus, I had to manually find which method is actually responsible for the bug.

My first approach was to attach a debugger to VS Code, and examine every access to the main bundle of the app.

All accesses to the main bundle, including Cocoa's `+[NSBundle mainBundle]` and Carbon's various methods, eventually uses [`CFBundleGetMainBundle()`](https://developer.apple.com/documentation/corefoundation/1537085-cfbundlegetmainbundle?language=objc). I thought putting a breakpoint on this method would allow me to find every place that checks for bundle IDs.

When I ran the app, I was greeted with a flood of calls, too many to analyze. I should've known: an app needs its main bundle for many reasons: for example, getting resources. There's no easy way to limit this breakpoint to the calls getting just the bundle ID.

## Dyld injection and swizzling

I decided instead to override `-[NSBundle bundleIdentifier]` such that, if the original return value is "com.microsoft.VSCodeInsiders", I return a non-Microsoft bundle ID. If this fixes the bug, then I'll know that the broken code uses `-[NSBundle bundleIdentifier]`, not CoreFoundation or any other bundle API.

To override an Objective-C method, I followed [New Relic's tutorial](- https://blog.newrelic.com/2014/04/16/right-way-to-swizzle/) for method swizzling. I look up the original `Method` on the `NSBundle` class, save the original implementation in a function pointer, and substitute my own implementation. When my method is called, I forward it to the original code, and change the return value if needed.

To load my code into VS Code, I used the `DYLD_INSERT_LIBRARIES` environmental variable, which specifies a shared library to load into the process at launch. (It's similar to `LD_PRELOAD` on Linux.) While there are [better ways](https://blog.timac.org/2012/1218-simple-code-injection-using-dyld_insert_libraries/) to get code to run once inserted, I chose to use a [constructor function](https://stackoverflow.com/questions/30700596/with-mach-o-is-there-a-way-to-register-a-function-that-will-run-before-main) because I wanted to try it.

My initial test code is shown below:

```
@import Darwin;
@import Foundation;
@import ObjectiveC;

NSString* (*NSBundle_bundleIdentifier_real)(NSBundle* bundle, SEL selector);

NSString* NSBundle_bundleIdentifier_hook(NSBundle* bundle, SEL selector) {
	NSString* retval = NSBundle_bundleIdentifier_real(bundle, selector);
	if ([retval isEqualToString:@"com.microsoft.VSCodeInsiders"]) {
		return @"com.worthdoingbadly.vscode";
	}
	return retval;
}

__attribute__((constructor))
void bundlehook_init() {
	Method method = class_getInstanceMethod([NSBundle class], @selector(bundleIdentifier));
	NSBundle_bundleIdentifier_real = method_getImplementation(method);
	method_setImplementation(method, &NSBundle_bundleIdentifier_hook);
}
```

```
$ clang -g -fmodules -Xlinker -dylib -o libbundlenameinject.dylib bundlenameinject.m
$ DYLD_INSERT_LIBRARIES=`pwd`/libbundlenameinject.dylib /Applications/Visual\ Studio\ Code.app/Contents/MacOS/Electron
```

and the result?

![screenshot of a working tab bar]({{ "/assets/blog/vscodetabs/tabs_working2.png" | absolute_url }})

Yep, the tab bar is working. So I know the issue is caused by some code calling `-[NSBundle bundleIdentifier]`. Now to find which one.

## Isolating the method

I need to find which method is calling us to obtain the main bundle ID. A [StackOverflow guide](https://stackoverflow.com/questions/220159/how-do-you-print-out-a-stack-trace-to-the-console-log-in-cocoa) told me to use the [`+[NSThread callStackSymbols]`](https://developer.apple.com/documentation/foundation/nsthread/1414836-callstacksymbols) method, which returns an Array of all the method names in the call stack. We're on the top of the call stack, so the method that called us must be at position `[1]` of that array.

Compatibility flags are calculated with code that have names ending with `DefaultValueFunction`. So I tried only overriding the bundle ID if the calling function's name contains `DefaultValueFunction`.

```
NSString* NSBundle_bundleIdentifier_hook(NSBundle* bundle, SEL selector) {
	NSString* retval = NSBundle_bundleIdentifier_real(bundle, selector);
	if ([retval isEqualToString:@"com.microsoft.VSCodeInsiders"]) {
		NSArray<NSString*>* stack = [NSThread callStackSymbols];
		bool override = [stack[1] containsString:@"DefaultValueFunction"];
		fprintf(stderr, "%s %s\n", override? "yes": "no", stack[1].UTF8String);
		if (override) {
			return @"com.worthdoingbadly.vscode";
		}
	}
	return retval;
}
```

Yep, the tab bar function is still fixed. So it's one of the compatibility calls. But which one?

I decided to use [binary search](https://en.wikipedia.org/wiki/Binary_search_algorithm) to eliminate half the candidate functions each time. 

I first logged the names of all the `DefaultValueFunction`s that got the main bundle ID, and put them into an Array.

Next, I made my hook only return an overridden bundle ID if the method's name is in my list.

Finally, I comment out half of the list at a time. If the tabs still work, then the method that checks the bundle ID is in the uncommented half. If the tabs broke, then the method is in the commented half.

Eliminate the wrong half, and eepeat until all but one method is commented out.

Here's my code:

```
@import Darwin;
@import Foundation;
@import ObjectiveC;

NSString* (*NSBundle_bundleIdentifier_real)(NSBundle* bundle, SEL selector);

NSArray<NSString*>* mystrs;

NSString* NSBundle_bundleIdentifier_hook(NSBundle* bundle, SEL selector) {
	NSString* retval = NSBundle_bundleIdentifier_real(bundle, selector);
	if ([retval isEqualToString:@"com.microsoft.VSCodeInsiders"]) {
		fprintf(stderr, "Bundle! %s\n", retval.UTF8String);
		NSArray<NSString*>* stack = [NSThread callStackSymbols];
		bool override = false;
		for (NSString* str in mystrs) {
			if ([stack[1] containsString:str]) {
				override = true;
				break;
			}
		}
		fprintf(stderr, "%s %s\n", override? "yes": "no", stack[1].UTF8String);
		if (override) {
			fprintf(stderr, "%s\n", [NSThread callStackSymbols].description.UTF8String);
			return @"com.worthdoingbadly.vscode";
		}
	}
	return retval;
}

__attribute__((constructor))
void bundlehook_init() {
	Method method = class_getInstanceMethod([NSBundle class], @selector(bundleIdentifier));
	NSBundle_bundleIdentifier_real = method_getImplementation(method);
	method_setImplementation(method, &NSBundle_bundleIdentifier_hook);

	mystrs = @[
/*
@"NSScreenGettingScreensHasSideEffectsDefaultValueFunction",
@"NSWindowAllowsImplicitFullScreenDefaultValueFunction",
@"NSApplicationLaunchMicrosoftUpdaterDefaultValueFunction",
@"NSApplicationFunctionRowControllerIsWebKitPluginProcessDefaultValueFunction",
@"NSSavePanelGuardAgainstSwizzledClassDefaultValueFunction",
*/
@"NSUseImprovedLayoutPassDefaultValueFunction",
/*
@"NSViewIsWebKitPluginProcessDefaultValueFunction",
@"NSIsPreLoboOmniGraffleDefaultValueFunction",
@"NSViewBuildLayerTreeOnForcibleDisplayDefaultValueFunction",
@"NSMightNeedToWorkAroundBadAdobeReleaseBugDefaultValueFunction",
@"NSViewKeepLayerSurfacesBehindTitlebarLayerSurfaceDefaultValueFunction",
@"NSCGSIsSynchronousM7DefaultValueFunction",
@"NSCGSIsSynchronousM7DefaultValueFunction",
@"NSViewAvoidDirtyLayoutWhenUpdatingAutoresizingConstraintsDefaultValueFunction",
*/
];

	fprintf(stderr, "Launched!\n");
}
```

Using this, I was able to isolate the method: `NSUseImprovedLayoutPassDefaultValueFunction`.

## Examining the method

Disassembling the method in IDA Free reveals that it does check for bundle IDs beginning with `com.microsoft.`.

<div style="font-size:10px">
<span style="white-space: pre; font-family: Courier; color: blue; background: #ffffff">
<span style="color:black">__text:00000000008E776D </span>_NSUseImprovedLayoutPassDefaultValueFunction <span style="color:black">proc near
__text:00000000008E776D                                         </span><span style="color:#8080ff">; DATA XREF: _NSUseImprovedLayoutPass+23↑o
</span><span style="color:black">__text:00000000008E776D                                         </span><span style="color:#8080ff">; _NSInvalidateSelfLayoutOnFrameChangesDefaultValueFunction+23↓o ...
</span><span style="color:black">__text:00000000008E776D                 </span><span style="color:navy">push    rbp
</span><span style="color:black">__text:00000000008E776E                 </span><span style="color:navy">mov     rbp, rsp
</span><span style="color:black">__text:00000000008E7771                 </span><span style="color:navy">push    rbx
</span><span style="color:black">__text:00000000008E7772                 </span><span style="color:navy">push    rax
</span><span style="color:black">__text:00000000008E7773                 </span><span style="color:navy">lea     rdi, cfstr_ComOvermacsPho </span><span style="color:gray">; &quot;com.overmacs.photosweeper&quot;
</span><span style="color:black">__text:00000000008E777A                 </span><span style="color:navy">movsd   xmm0, cs:qword_C170E0
</span><span style="color:black">__text:00000000008E7782                 </span><span style="color:navy">mov     esi, </span><span style="color:green">0Ch
</span><span style="color:black">__text:00000000008E7787                 </span><span style="color:navy">call    </span>__CFAppVersionCheckLessThan
<span style="color:black">__text:00000000008E778C                 </span><span style="color:navy">test    al, al
</span><span style="color:black">__text:00000000008E778E                 </span><span style="color:navy">jnz     loc_8E781B
</span><span style="color:black">__text:00000000008E7794                 </span><span style="color:navy">mov     rdi, cs:</span>classRef_NSBundle ; void *
<span style="color:black">__text:00000000008E779B                 </span><span style="color:navy">mov     rsi, cs:</span>selRef_mainBundle ; char *
<span style="color:black">__text:00000000008E77A2                 </span><span style="color:navy">mov     rbx, cs:</span>_objc_msgSend_ptr
<span style="color:black">__text:00000000008E77A9                 </span><span style="color:navy">call    rbx </span><span style="color:gray">; </span><span style="color:#ff00ff">_objc_msgSend
</span><span style="color:black">__text:00000000008E77AB                 </span><span style="color:navy">mov     rsi, cs:</span>selRef_bundleIdentifier ; char *
<span style="color:black">__text:00000000008E77B2                 </span><span style="color:navy">mov     rdi, rax        </span>; void *
<span style="color:black">__text:00000000008E77B5                 </span><span style="color:navy">call    rbx </span><span style="color:gray">; </span><span style="color:#ff00ff">_objc_msgSend
</span><span style="background-color: yellow"><span style="color:black">__text:00000000008E77B7                 </span><span style="color:navy">mov     rsi, cs:</span>selRef_hasPrefix_ ; char *
<span style="color:black">__text:00000000008E77BE                 </span><span style="color:navy">lea     rdx, cfstr_ComMicrosoft_0 </span><span style="color:gray">; &quot;com.microsoft.&quot;
</span><span style="color:black">__text:00000000008E77C5                 </span><span style="color:navy">mov     rdi, rax        </span>; void *
<span style="color:black">__text:00000000008E77C8                 </span><span style="color:navy">call    rbx </span><span style="color:gray">; </span><span style="color:#ff00ff">_objc_msgSend
</span></span><span style="color:black">__text:00000000008E77CA                 </span><span style="color:navy">test    al, al
</span><span style="color:black">__text:00000000008E77CC                 </span><span style="color:navy">jz      short loc_8E77E1
</span><span style="color:black">__text:00000000008E77CE                 </span><span style="color:navy">cmp     cs:</span>_NSViewLinkedOnFuji_onceToken<span style="color:navy">, </span><span style="color:green">0FFFFFFFFFFFFFFFFh
</span><span style="color:black">__text:00000000008E77D6                 </span><span style="color:navy">jnz     short loc_8E7847
</span>

</span>
</div>

This method returns `true` normally, but returns `false` if an app needs the old behaviour. However, like most compatibility patches, this value can be overridden by setting the relevant variable, `NSUseImprovedLayoutPass`, through [`NSUserDefaults`](https://developer.apple.com/documentation/foundation/nsuserdefaults?language=objc), macOS's preference system.

An `NSUserDefaults` value can be set temporarily by passing it on the command line. So I launched VS Code with `NSUseImprovedLayoutPass` temporarily set to true:

```
/Applications/Visual\ Studio\ Code.app/Contents/MacOS/Electron -- -NSUseImprovedLayoutPass true
```

And the tabs worked without changing the bundle ID.

## Making the pull request

So all I had to do was to set this option in VS Code, and the tabs should be fixed.

There are two ways to set an `NSUserDefaults` value in code: [`setBool:forKey`](https://developer.apple.com/documentation/foundation/nsuserdefaults/1408905-setbool?language=objc) sets it permanently, while [`registerDefaults`](https://developer.apple.com/documentation/foundation/nsuserdefaults/1417065-registerdefaults?language=objc) sets it temporarily until the program exits.

Electron exposes both methods: I decided to use [the temporary method](https://github.com/electron/electron/blob/master/docs/api/system-preferences.md#systempreferencesregisterdefaultsdefaults-macos) for this override since it seemed cleaner to me, so [all I had to do](https://github.com/zhuowei/vscode/commit/a7989f0a648af0b91dc0cea7c9cebe2f4f230654) was call 

```
systemPreferences.registerDefaults({ NSUseImprovedLayoutPass: true });
```

before any windows are created, and native tabs worked in VS Code.

I quickly sent [a Pull Request](https://github.com/Microsoft/vscode/pull/52775) to the VS Code GitHub repository.


## An ironic code review

Unlike [my previous attempt](/vscodetwofixes/) to submit pull requests to VS Code, I got a code review almost immediately - and found out I made an ironic mistake.

My fix enables the workaround for all Mac users, not just the minority that use Native Tabs support. This makes it much more likely to break something unintentionally. The workaround isn't specifically restricted to those with the issue - just like how Apple's original patch broke VS Code by not being specific enough when targeting the bundle ID. 

To avoid introducing new bugs, the VS Code developer [changed the patch](https://github.com/Microsoft/vscode/commit/368ab9c31b5c0930a40ab3f0e0d768ebbeeb9ef8) to only set the override when it's needed. (and also switched to `setUserDefault` since Electron 1.7.x didn't have `registerDefaults`.).

So while my original pull request wasn't up to VS Code's standards, I now know what to do in the future to avoid introducing new bugs.

## What I learned

- Overriding methods is easy with macOS and Objective-C
- When making a change, be as specific as possible to minimize side effects
- Try to fix issues without creating more bugs