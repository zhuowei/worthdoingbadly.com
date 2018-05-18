---
title: These 299 macOS apps are so buggy, Apple had to fix them in AppKit
categories: macos
permalink: /appkitcompat/
---

What do Photoshop, Matlab, Panic Transmit, and Eclipse have in common? They are among the 299 apps for which macOS applies compatibillity fixes.

Here's the [full list of bundle IDs]({{"/assets/blog/appkitcompat/appkit_processed.html" | absolute_url }}), along with the functions that checks for them, and the first caller to those functions. It's also available in [CSV format]({{"/assets/blog/appkitcompat/appkit.csv" | absolute_url }}).

Note that this is just a list of apps Apple has developed compatibility tweaks to make them run on newer macOS versions. As the list demonstrates, even the best apps often needs some tweaks on newer macOS. In addition, most of these patches are only applied to older versions of apps.

Here's how I extracted the list, and some interesting things I found in it.

## How I learned about this

While browsing [@stroughtonsmith](https://twitter.com/stroughtonsmith)'s Twitter feed, I saw this tweet from [@b3ll](https://twitter.com/b3ll):

> You know you've really made it when NSImage explicitly checks for your bundle
>
> <img src="{{'/assets/blog/appkitcompat/b3ll_tweet.jpg' | absolute_url}}" width="560">
>
> Adam Bell (@b3ll), [May 10, 2018](https://twitter.com/b3ll/status/994665524448583682)

This was interesting: I always thought that Apple was not as thorough about compatibility as Microsoft. But a later reply dropped an even crazier tidbit:

> AppKit has hundreds of bundle ID checks for various reasons
>
> Guilherme Rambo (@_inside), [May 10, 2018](https://twitter.com/_inside/status/994669723731275777)

Hundreds? I gotta take a look at this.

Others, such as [0xced](https://twitter.com/0xced) had [asked about this](https://twitter.com/0xced/status/429727057594290176) before: it turns out Apple calls them ["checkfixes"](https://twitter.com/LegNeato/status/429885180275208192) internally.

## Which apps?

Compatibility fixes are applied by checking the

`bool __CFAppVersionCheckLessThan(CFStringRef, CFSystemVersion)`

function, which returns true if the current app matches the specified bundle ID and is linked on or prior to the macOS version. Thus, older versions of the app would have the fix applied, while newer versions built with a newer SDK would not.

I found 299 unique app IDs passed into `__CFAppVersionCheckLessThan` by statically analyzing AppKit, Foundation, and CoreFoundation on macOS 10.13.4. 

Apple itself tops the list with 64 unique app IDs: this is expected, since Apple likely used tricks and private APIs third parties couldn't use, causing compatibility issues down the line.

Adobe, of course, is second place with 31 bundle IDs.

Looking through the list of apps tells a lot about what apps Apple considers essential to the Mac platform: after all, they put special effort to make them work on newer system versions. So what apps do Apple consider important?

Productivity apps from large companies:
 - most of the Adobe suite
 - the Microsoft Office suite
 - Autodesk's AutoCAD and Maya
 - Matlab
 - Ableton Live
 - Intuit Quicken/QuickBooks
 - TurboCAD
 - VMWare Fusion

Communication apps:
 - Google Chrome
 - Opera Browser
 - Twitter for Mac
 - Tencent QQ, WeChat
 - AOL Messenger
 - Citrix GoToMeeting
 - Cisco Spark
 - HipChat
 - Sketch
 - Spotify
 - Evernote
 - Dropbox

Surprisingly high number of games. I suspect there are even more IDs in game-specific libraries such as OpenGL.
 - Blizzard's games: installer, Diablo 3, Heroes of the Storm, Starcraft 2, World of Warcraft, Hearthstone, and Battle.NET
 - Grid 2 Reloaded
 - Dragon Age 2 (of course)

Open-source apps:
 - Firefox
 - VLC
 - Blender
 - Eclipse
 - AquaMacs (an Emacs port)
 - OpenJDK
 - Textual IRC

Indie favorites:
 - Panic's Coda and Transmit
 - Omni Group's OmniFocus, OmniGraffle, OmniPlan, and OmniWeb
 - Sketch
 - 1Password
 - BBEdit/TextWrangler

Device drivers, because the manufacturers ain't gonna fix 'em
 - Garmin TrainingCenter
 - Epson xp640
 - HP Installer
 - Fujitsu ScanSnap

Apple Internal apps:
 - `com.apple.ist.Merlin`
 - `com.apple.ist.Radar7` (probably the most ironic)
 - `com.apple.ist.SoftwareDepot.Checker`
 - `com.apple.ist.appledirectory4`
 - `com.apple.ist.hr.Merlin`

and many other apps I haven't heard of. 

The breadth of software is staggering, and shows how much testing Apple must do to discover these bugs. (instead of testing for, say, the click-to-root bug in High Sierra ;) )

## What a patch looks like

The patches don't change behaviour drastically. They aren't as crazy as the Windows backward compatibility patches [Raymond Chen](https://blogs.msdn.microsoft.com/oldnewthing/) writes about. The patch to `NSOpenGLContext.currentContext()`, for example, is very simple: here's the IDA graph view of the function.

<img src="{{'/assets/blog/appkitcompat/nsopenglcontext.png' | absolute_url}}" width="797">

My attempt at translating it to pseudocode makes it clear that the only compatibility change is adding an `autoreleasepool`:

```
class NSOpenGLContext {
    class func currentContext() -> NSOpenGLContext {
        if __CFAppVersionCheckLessThan("com.microsoft.Powerpoint", CFSystemVersionYosemite) {
            autoreleasepool {
                let cglContext = _CGLGetCurrentContext();
                pthread_mutex_lock(__NSOpenGLContextToCGLContextObjMapLock)
                let context = __NSOpenGLContextToCGLContextObjMap[cglContext]
                pthread_mutex_unlock(__NSOpenGLContextToCGLContextObjMapLock)
                return context
            }
        } else {
            // no autorelease pool!
            let cglContext = _CGLGetCurrentContext();
            pthread_mutex_lock(__NSOpenGLContextToCGLContextObjMapLock)
            let context = __NSOpenGLContextToCGLContextObjMap[cglContext]
            pthread_mutex_unlock(__NSOpenGLContextToCGLContextObjMapLock)
            return context
        }
    }
}
```

Other patches are similarily small: the Dragon Age 2 patch @b3ll found makes [`-[NSBundle imageForResource:]`](https://developer.apple.com/documentation/foundation/bundle/1519901-image) call `-[Bundle pathForImageResource:` instead of `Bundle URLsForImageResource:]`, and creates the image using the file instead of the URLs.

## Stuff I noticed in the list of apps

Microsoft Excel/PowerPoint/Word have a patch in `_CFArraySortValues` to change the sorting algorithm slightly. How do you break sorting?!

25 apps had [automatic tabbing](https://indiestack.com/2016/10/window-tabbing-pox/) (introduced in Sierra) disabled using the compatibility feature.

Some compatiblity patches only affects apps from one company: for example,  `_NSSavePanelUseLocalhostURLsDefaultValueFunction` fixes the save panel for a bunch of Adobe apps.

Other compatibility patches affect apps from many different developers: for example, `NSTableView` related patches affected apps from HP Installer to Sketch to TeamViewer, demonstrating that Tables Are Hard<sup>TM</sup>.

Photoshop and VectorWorks CAD have Touch Bar API patches: The Touch Bar API is so new that I'm surposed there's already compatibility issues.

Most of the preference methods are named after the behaviours they change, but Eclipse, VMWare, Dragon Age 2, Apple Keynote, Apple Motion, and the Microsoft Office suite have the dubious honour of getting patch methods specifically named after them.

On the list, there are system apps such as `com.apple.loginwindow`: why would they need compatibility patches?! I guess Apple's using the compatibility system to patch other things/change behaviour for specific system apps. Shouldn't that be done via, say, method swizzling by the app itself, instead of in the framework?

Some patches seems to turn on slower code paths: for example, 12 apps are checked in `_NSCGSIsSynchronousM7DefaultValueFunction`, which likely slows down Core Graphics by using a synchronous method. This is a great use of backwards compatibility: it allows almost every app to run faster on a newer OS, but still prevent issues in a few applications.

## What if my app is on the list?

There are two reactions when someone finds their own app was fixed by Apple:

Reaction 1: from the developer of Comic Life

> @0xced Not sure if I should feel honored or ashamed to be on that list
>
> Airy (@aa10), [February 2, 2014](https://twitter.com/aa10/status/429902613526904832)

Reaction 2: from the developer of Textual IRC

> Fuck NSBundle
>
> emsquared committed on [Jul 7, 2014](https://github.com/Codeux-Software/Textual/commit/f218b6444cefae56576c3cef0ca40b977713604a#diff-6b21bb57b24f0261b8af06bac36a52af)

The Textual IRC example is actually very interesting, because I was able to find the commit that fixed the bug just by looking at the patch:

<img src="{{'/assets/blog/appkitcompat/nsbundle_unload.png' | absolute_url}}" width="594">

This patch disables `NSBundle.unload()` entirely, so that code wouldn't get unloaded. I simply searched for NSBundle in Textual's source, and actually found the [commit](https://github.com/Codeux-Software/Textual/commit/f218b6444cefae56576c3cef0ca40b977713604a#diff-6b21bb57b24f0261b8af06bac36a52af) that fixed the issue. 

Textual's plugin system deactivated plugins by first unloading the plugin bundle, then calling an unload handler on the plugin. Of course, with the new NSBundle implementation, the unload handler's code would be gone after the bundle unload, and calling the handler would crash the app. The fix, of course, was to call the unload handler before deallocating the bundle.

It's fascinating to see both sides of the application compat patch: how the bug manifested in the app, how it's worked around by Apple, and finally how it's fixed properly by the developer (after much cursing).

## What about iOS?

Surprisingly, iOS's UIKit has _zero_ bundle ID checks! Fixes are applied to all apps linked with old SDKs. However, 0xced found three bundle IDs in Foundation: I confirmed with

```
strings -a "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/Library/CoreSimulator/Profiles/Runtimes/iOS.simruntime/Contents/Resources/RuntimeRoot/System/Library/Frameworks/Foundation.framework/Foundation" |grep "^com\."|sort
```

and found:

- com.popcap.* - [0xced examined this:](https://twitter.com/0xced/status/429725803858128897) it returns a random resource from `-[NSBundle pathForResource:ofType]`
- com.ea.realracing3
- com.mackiev.
- com.stuckpixelinc.funnypictures ([@SlaunchaMan](https://twitter.com/SlaunchaMan/status/429756162100051968) found that this app was the most popular app on the App Store... in 2009.)

## How I extracted the data

Extracting this data wasn't hard: you can do this in an hour, without spending a dime.

I pulled this list using static analysis, since dynamic analysis (by putting a breakpoint on `__CFAppVersionCheckLessThan`) would require me to trigger every method containing a patch, which is impossible. 

To conduct static analysis, I needed a scriptable disassembler.

I chose [IDA Free 7.0](https://www.hex-rays.com/products/ida/support/download_freeware.shtml), since IDA's the industry standard for reverse engineering, and the free version supports disassembling macOS frameworks.

First, I loaded `/System/Library/Frameworks/AppKit.framework/Appkit`, Foundation, and CoreFoundation into IDA Free.

Next, I needed a script that:

- Looked for code that invokes `__CFAppVersionCheckLessThan`. These are called "xrefs" (cross-references) in IDA.
- for each xref:
  - find the argument passed into the function
  - find one function that calls this function
    - since we want to know, for example, what function actually uses `_NSBundleRunningDragonAge2Inf104DefaultValueFunction`.
    - (It's `-[NSBundle _newImageForResourceWithProspectiveName:imageClass:]`, by the way)
  - dump this information to IDA's output window

IDA is usually scripted using IDAPython, but the free version only supports IDC, a C-like scripting language. I've only written one IDC script before, so I had to consult other IDC scripts, such as [this script that also looks for xrefs](https://github.com/gdbinit/idc-scripts/blob/master/create_and_label_sysent_entries.idc). In addition, IDA renamed all IDC methods in IDA 6; while the older function names are still present in IDA 7, I decided to update to the newer names by checking IDA's `idc.idc` header file for the name mappings.

The resulting script [can be found here](https://github.com/zhuowei/worthdoingbadly.com/blob/master/assets/blog/appkitcompat/appkit_xrefs.idc). I loaded it via File->Script File in IDA, and it printed out the calling functions and ... most ... of the bundle IDs. A few didn't extract properly, so I fixed them by hand.

I then copied the lists, and generated [HTML](https://github.com/zhuowei/worthdoingbadly.com/blob/master/assets/blog/appkitcompat/appkit_process.py) and [CSV](https://github.com/zhuowei/worthdoingbadly.com/blob/master/assets/blog/appkitcompat/appkit_processCSV.py) versions with Python scripts.

Finally, to count the number of apps, I just took the CSV and

```
cut -d , -f 1 appkit.csv|sort|uniq|wc
     299     305    7080
```

## Conclusion

Apple [gets a bad reputation](https://www.quora.com/Why-is-Apple-so-bad-at-making-their-operating-systems-backwards-compatible) for their supposed lack of backwards compatibility. Nothing is further from the truth: macOS includes tweaks for specific important apps to keep them working on new OS versions. The list of 299 apps macOS checks is fascinating, and shows what Apple believes to be essential applications for the platform.

## What I learned

- Backwards compatbility is hard.
- Complicated user interface elements are hard. (See: the many, many NSTableView patches, and the wide list of apps affected)
- It's sometimes better to special-case some apps than to reduce performance for all apps - see the `_NSCGSIsSynchronousM7DefaultValueFunction` patch above
- IDA Free's scripting language, IDC, isn't that bad, compared to IDAPython. (IDASwift wen [&eta;](https://www.google.com/search?q=wen+eta))

Thanks to @theslinker for [advice on this post](https://twitter.com/theslinker/status/995505415394750465).