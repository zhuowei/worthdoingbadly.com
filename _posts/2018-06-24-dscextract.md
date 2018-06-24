---
title: Extracting libraries from dyld_shared_cache
categories: macos, ios
permalink: /dscextract/
---

I learned to extract working shared libraries from macOS's dyld shared cache, and learned a bit about Mach-O executables, Objective-C, and problem solving along the way.

## Introduction

A computer program uses many **libraries**, which contains shared code used by different programs. When a program starts up, it needs to load all the libraries it needs, and link all the libraries to allow them to call each other's functions. In addition, the Objective-C runtime must initialize each library when it's loaded. These tasks slows down launching programs.

macOS and iOS improve startup time and memory usage by combining all system libraries into the [**dyld shared cache**](http://iphonedevwiki.net/index.php/Dyld_shared_cache): a file containing every library built into the operating system, all linked together and with the Objective-C runtime already initialized, so instead of loading and processing hundreds of files, the program just loads one file at startup, already preprocessed.

On iOS, since all the system libraries are in the shared cache, the individual libraries are removed to save space. I'm working on a project that needs to load an iOS system library separately, so to get the library, I must extract it from the shared cache. This means undoing all the preprocessing when building the shared cache.

## The current available tools

The [iPhone Dev wiki](http://iphonedevwiki.net/index.php/Dyld_shared_cache#Cache_extraction) lists multiple tools for extracting the dyld_shared_cache: however, each has its shortcomings.

- [jtool](http://www.newosxbook.com/tools/jtool.html): by Jonathan Levin of NewOSXBook, frequently updated, but doesn't fix Objective-C selectors.
- [decache](https://github.com/phoenix3200/decache) by Phoenix3200 doesn't work past iOS 9.
- Apple's own [dsc_extractor](https://opensource.apple.com/source/dyld/dyld-519.2.2/launch-cache/dsc_extractor.cpp.auto.html), used in Xcode when you first plug in a device for debugging (that's what "Preparing debugger support" does). Libraries are only usable for providing symbols to debuggers.
- [imaon2](https://github.com/comex/imaon2) by @comex. The wiki says it produces the highest quality output, but that it's hard to compile.

The last two seems to be the most promising, since they both support iOS 11. It sounded like imaon2 is the only one that can produce a usable library, but I instead chose to improve Apple's dsc_extractor, because I couldn't compile imaon2, and because I didn't need imaon2's complexity. 

So what does imaon2 fix that dsc_extractor doesn't? To understand this, we need to learn about how macOS executables work.

## A primer of MachO

[**Mach-O**](https://en.wikipedia.org/wiki/Mach-O) is the executable format used on macOS and iOS.

There are many guides on Mach-O files; for example, [@qwertyoruiopz's presentation](https://news.ycombinator.com/item?id=17378829), which, as of this writing, is on the front page of HN. You should probably read one of those to get the full picture, but here's a very brief summary of Mach-O files.

A MachO file contains a header comprised of a series of **load commands** - commands telling **dyld**, macOS's dynamic library loader, information about the file. Some load commands specify metadata about the file, such as the version of macOS it is compiled for, or the file's entry point.

The most important load commands define **segments**, which are the parts of the MachO file that are loaded into memory at a specified address.

There are three segments in most libraries:

- __TEXT: holds code and data that don't change
- __DATA: holds data that do change
- __LINKEDIT: holds instructions for the dynamic linker to:
  - relocate the library to the correct memory address
  - import functions it needs
  - export functions it contains

Each segment can also define **sections**, which further subdivides the segment into named parts. For example, the __DATA section includes sections such as __objc_cfstring, containing NSStrings, and __objc_classlist, containing pointers to ObjC classes defined in the file.

(This concept of segments and sections is also in [ELF](https://en.wikipedia.org/wiki/Executable_and_Linkable_Format), the executable format used by Linux and other modern Unix systems.)

## imaon2: Do I really need that?

I spent way too much time trying to get Comex's imaon2 to compile. It turns out that Comex didn't add the [Cargo.lock](https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html) file to the repository. This file specifies all the Rust dependencies required by the program, similar to the Podfile.lock for CocoaPods or the Yarnfile for Yarn. Without this file, it's impossible to compile the program.

So instead I studied imaon2's source code to find out why it's so complicated. What are all those 11448 lines of code doing?

I found that imaon2 does [fix up all of dyld's optimizations](https://github.com/comex/imaon2/blob/master/src/fmt-macho_dsc_extraction/macho_dsc_extraction.rs#L319) when extracting the library. This was helpful in finding out what I must implement in dsc_extractor. 

This is only a tiny bit of imaon2's code, however. The bulk of its work consists of moving the __TEXT and the __DATA sections back together.

In a standalone library, the segments are all loaded into memory next to each other:

<table style="font-family: monospace">
<tr><td>0x000000000000</td><td style="background-color: #e57373">BusinessChat __TEXT</td></tr>
<tr><td>0x000000008000</td><td style="background-color: #ffd54f">BusinessChat __DATA</td></tr>
<tr><td>0x00000000B000</td><td style="background-color: #4dd0e1">BusinessChat __LINKEDIT</td></tr>
</table>

However, when the library is added to the dyld cache, the segments are split apart, and the same type of segments are placed together, to simplify the loading process:

<table style="font-family: monospace">
<tr><td>0x7FFF2002D000</td><td style="background-color: #e57373">ClientFlowService __TEXT</td></tr>
<tr><td>...</td><td style="background-color: #e57373">...</td></tr>
<tr><td>0x7FFF26A9C000</td><td style="background-color: #e57373">BusinessChat __TEXT</td></tr>
<tr><td>...</td><td style="background-color: #e57373">...</td></tr>
<tr><td>0x7FFF80000000</td><td style="background-color: #ffd54f">ClientFlowService __DATA</td></tr>
<tr><td>...</td><td style="background-color: #ffd54f">...</td></tr>
<tr><td>0x7FFF818EF000</td><td style="background-color: #ffd54f">BusinessChat __DATA</td></tr>
<tr><td>...</td><td style="background-color: #ffd54f">...</td></tr>
<tr><td>0x7FFFC0336000</td><td style="background-color: #4dd0e1">__LINKEDIT</td></tr>
</table>

Unfortunately, the dyld cache also removes the information required to move the segments, making it very difficult to undo this change. imaon2 tries its best to return the library to the original state, using advanced static analysis.

But do I really need that? The problem I wanted to solve isn't actually reproducing the original library: I just want to run the extracted code.

Apple's dsc_extractor can't move the segments back, so the extracted library has a large gap in memory:

<table style="font-family: monospace">
<tr><td>0x7FFF2002D000</td><td style="background-color: #e57373">BusinessChat __TEXT</td></tr>
<tr><td>0x7FFF20035000</td><td>1.5GB of empty space</td></tr>
<tr><td>0x7FFF818EF000</td><td style="background-color: #ffd54f">BusinessChat __DATA</td></tr>
<tr><td>0x7FFF818FA000</td><td style="background-color: #4dd0e1">BusinessChat __LINKEDIT</td></tr>
</table>

On a 32-bit system, that's 1.5GB of address space wasted out of only 2GB total, and the library would likely not load on a device. However, all current macOS and iOS devices are 64-bit. On 64-bit devices, 1.5GB of address space is tiny compared to the [64GB (iOS)](https://www.mikeash.com/pyblog/friday-qa-2013-09-27-arm64-and-you.html) or terabytes (macOS) of address space available.

(note: the above is actually a simplification: `mmap`, as used by dyld, seems to be [limited to 2GB on 64-bit iOS](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/mach/arm/vm_param.h#L153), as [reported here](https://github.com/pixelglow/zipzap/issues/72), but the Mach virtual memory APIs can be [mapped higher in memory](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/mach/arm/vm_param.h#L157). The calculation for amount of allowed memory [is pretty complicated](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/arm/pmap.c#L8983), taking into account the device's physical memory and whether the app can JIT. Suffice to say there's enough address space for us.)
{: style="background-color: #eee"}

So our program can be simpler than imaon2.

## Apple's own dyld cache extractor

I decided to base my extractor on Apple's own dyld cache extractor, available from [Apple's opensource portal](https://opensource.apple.com/tarballs/dyld/). As I mentioned before, it's designed to extract libraries for iOS debugging, not for producing usable libraries, so it only performs enough fixes to allow a debugger to load it. However, it's a good base, since it works on macOS 10.13 and iOS 11 caches just fine, and also comes with a nice Xcode project. (I only had to tweak the Xcode project to add the extractor library to the executable's dependency before it built.)

## Reading unrebased dyld cache

The first change I made was to read the uncached dyld cache. According to [iPhoneDevWiki](http://iphonedevwiki.net/index.php/Dyld_shared_cache#Cache_retrieval), just reading the cache from disk on a running system gives a modified version of the cache, with the required relocation information missing.

Even mmapping empty memory and then reading it with F_NOCACHE, as suggested by the wiki article, didn't seem to work. Thankfully, [an older version of dyld itself](https://opensource.apple.com/source/dyld/dyld-195.5/launch-cache/update_dyld_shared_cache.cpp.auto.html) showed the correct approach: allocate uncached Mach memory, then read uncached data from the file.

## Compare the original and new library

Next, I started comparing the original library against the extracted version from dsc_extract. I needed a small library that uses enough features for testing. The BusinessChat framework on macOS proved to be a good candidate.

To compare the two files, [MachOView](https://sourceforge.net/projects/machoview/files/?source=navbar) by Peter Saghelyi was essential. It describes each segment and section, interprets all the data structures, and has an amazing hex view. You absolutely need this if you're doing advanced macOS/iOS development.

I also used IDA Free - it was able to interpret the Objective-C data in the file, and provided better disassembly of the code.

## Undoing Objective-C selector uniquing

I knew from imaon2's source and [from Twitter](https://twitter.com/theninjaprawn/status/905932038372458496) that I need to fix Objective-C selectors in the extracted library. Before, the selectors point to nonexistant memory (represented in IDA with red text):

![disassembly from IDA, showing an invalid selector in Objective-C code]({{ "/assets/blog/dscextract/selector_unfixed1.png" | absolute_url }})

To understand why this dyld_shared_cache optimization must be undone, we need to look at how Objective-C works.

In Objective-C, calling a method involves [passing an object and a selector](https://developer.apple.com/documentation/objectivec/1456712-objc_msgsend) to invoke on the object.

The Objective-C runtime finds the right method matching the selector with [this code](https://github.com/opensource-apple/objc4/blob/cd5e62a5597ea7a31dccef089317abb3a661c154/runtime/objc-runtime-new.mm#L4498), which is so simple I don't need to pseudocode it:

```
//// zhuowei: mlist contains the object's methods, and sel is the selector of the method to call
static method_t *search_method_list(const method_list_t *mlist, SEL sel)
{
    int methodListIsFixedUp = mlist->isFixedUp();
    int methodListHasExpectedSize = mlist->entsize() == sizeof(method_t);
    
    if (__builtin_expect(methodListIsFixedUp && methodListHasExpectedSize, 1)) {
        return findMethodInSortedMethodList(sel, mlist);
    } else {
        // Linear search of unsorted method list
        for (auto& meth : *mlist) {
            //// zhuowei: note that selectors are compared by their address
            if (meth.name == sel) return &meth;
        }
    }

    return nil;
}
```

Note (by my comment) that the selectors are compared by their memory address instead of by string compare. This saves time, but means there can be only one unique instance of a selector in the program. This is accomplished with the help of both the compiler and the Objective-C runtime.

Objective-C code like `[NSObject new]` gets translated by the compiler to something like

```
// library 1
SEL mySelector = "new";
SEL* pointerToUniqueSelector = &mySelector;

objc_msgSend(NSObject, *myPointerToUniqueSelector);
```

If we have another library that also calls "new":

```
// library 2
SEL yourSelector = "new";
SEL* yourPointerToUniqueSelector = &yourSelector;

objc_msgSend(NSObject, *yourPointerToUniqueSelector);
```

Without the Objective-C runtime's intervention, `yourSelector != mySelector`, and the second library won't find the right method. Thus, when a library is loaded, the Objective-C runtime changes the selector references to match:

```
// library 2, after loading
SEL yourSelector = "new"; // unused
SEL* yourPointerToUniqueSelector = &mySelector; // modified to point to Library 1's copy

objc_msgSend(NSObject, *yourPointerToUniqueSelector);
```

Now both calls will use the same address for the selector.

To avoid doing this at startup, when building dyld cache, this selector uniquing is done in advance. According to [Greg Parker](http://sealiesoftware.com/blog/archive/2009/09/01/objc_explain_Selector_uniquing_in_the_dyld_shared_cache.html), this halved the time it takes to load apps on Mac OS X Snow Leopard.

However, this prevents extracting the library, as when extracting library from cache, we get:

```
// library 2, after extraction
SEL yourSelector = "new"; // unused
SEL* yourPointerToUniqueSelector = /* invalid address! since mySelector isn't in this file */

objc_msgSend(NSObject, *yourPointerToUniqueSelector);
```

The unique copy of the selector is in a different library, which we didn't extract, so the pointer points to an invalid address when it's loaded. 

we can undo this by going through all the pointers to the selectors, find out which selectors they point to in the cache, and then finding the equivalent selector in the file we want to extract: in pseudocode:

```
for each pointerToSelector in pointer to selectors:
  selectorString = readFromCache(pointerToSelector);
  pointerToSelector = findStringInLocalLibrary(selectorString)
```

This fixed disassmbly of the function:

![disassembly from IDA, showing a valid selector in Objective-C code]({{ "/assets/blog/dscextract/selector_fixed1.png" | absolute_url }})

## Fixing relocation

The next task is to regenerate the **rebase info**, which specifies the changes needed to move the library from its original linked address to the loaded memory address.

When the dyld cache is built, the original library's rebase information is replaced with a compressed version. The format is [documented by Apple in dyld](https://github.com/zhuowei/dsc_extractor_badly/blob/master/launch-cache/dyld_cache_format.h#L150), and it's very clever: it stores the list of pointers to change using a linked list in the unused top bits of those pointers, allowing the relocation info to be stored almost for free.

(It works so well that Apple also adopted it to [compress the kernel](https://bazad.github.io/2018/06/ios-12-kernelcache-tagged-pointers/) in iOS 12 beta.)

Unfortunately, normal libraries can't use this compressed format, so it must be converted back to the original format.

To do this, I borrowed dyld's code to interpret the compressed format, recorded each change it made, and wrote the changes back to the extracted library's rebase info table.

## Fixing the Objective-C information

After these two changes, and after using [dyld's debug variables](https://github.com/zhuowei/dsc_extractor_badly/blob/master/src/dyld.cpp#L199) to troubleshoot a few more issues, I can actually loads the library with a `dlopen` call:

```
// note: I had to rename the library to "DusinessChat", otherwise it loads the version of BusinessChat already in the cache
void* handle = dlopen("/private/tmp/System/Library/Frameworks/BusinessChat.framework/Versions/A/DusinessChat", RTLD_LOCAL | RTLD_LAZY);
Class clsBCChatButton = NSClassFromString(@"BCChatButton");
id anObj = [[clsBCChatButton alloc] initWithStyle:0];
```

However, the call to initWithStyle crashes with a method not found error. [Using a Stack Overflow snippet](https://stackoverflow.com/questions/2094702/get-all-methods-of-an-objective-c-class-or-instance) to list all the methods on the object also crashes with a segfault. Why?

Remember the code that looks up the right method for a selector? It compares the desired selector against `const method_list_t *mlist`, the list of methods defined by that class. Of course, the selectors in the method list must also be unique.

Like the selector reference llist, the dyld cache also preprocesses the method info to reference unique selectors. Again, after extracting the library, the method list contains invalid pointers to selectors, represented by red in the IDA disassembly:

<div style="font-size: 10px">
<span style="white-space: pre; font-family: Courier; color: blue; background: #ffffff">

<span style="color:gray">__objc_const:00007FFF818EFB40 </span>_OBJC_INSTANCE_METHODS_BCChatButton __objc2_meth_list &lt;<span style="color:#008040">1Bh</span><span style="color:navy">, </span><span style="color:#008040">2Eh&gt;
</span><span style="color:gray">__objc_const:00007FFF818EFB40                                         </span><span style="color:#8080ff">; DATA XREF: __objc_const:BCChatButton_$classData↓o
</span><span style="color:gray">__objc_const:00007FFF818EFB48                 </span>__objc2_meth &lt;<span style="background:red">7FFF250C68BCh</span><span style="color:navy">, offset aV2408q16, \ </span><span style="color:gray">; -[BCChatButton _setStyle:] ...
__objc_const:00007FFF818EFB48                               </span><span style="color:navy">offset </span>__BCChatButton__setStyle__&gt;
<span style="color:gray">__objc_const:00007FFF818EFB60                 </span>__objc2_meth &lt;<span style="background:red">7FFF25DC90B2h</span><span style="color:navy">, offset aV1608, \ </span><span style="color:gray">; -[BCChatButton .cxx_destruct] ...
__objc_const:00007FFF818EFB60                               </span><span style="color:navy">offset </span>__BCChatButton__cxx_destruct_&gt;
<span style="color:gray">__objc_const:00007FFF818EFB78                 </span>__objc2_meth &lt;<span style="background:red">7FFF25DC928Ah</span><span style="color:navy">, offset a240816, \ </span><span style="color:gray">; -[BCChatButton initWithCoder:] ...
__objc_const:00007FFF818EFB78                               </span><span style="color:navy">offset </span>__BCChatButton_initWithCoder__&gt;
</span>
</div>

So when extracting, that change must also be undone, using the exact same process as before: only, instead of going through the list of selectors, we go through the list of classes to find the list of methods, and fix each selector referenced within. The repaired method list is shown below, with all the selectors matching the desired methods:

<div style="font-size: 10px">
<span style="white-space: pre; font-family: Courier; color: blue; background: #ffffff">

<span style="color:gray">__objc_const:00007FFF818EFB40 </span>_OBJC_INSTANCE_METHODS_BCChatButton __objc2_meth_list &lt;<span style="color:#008040">18h</span><span style="color:navy">, </span><span style="color:#008040">2Eh&gt;
</span><span style="color:gray">__objc_const:00007FFF818EFB40                                         </span><span style="color:#8080ff">; DATA XREF: __objc_const:BCChatButton_$classData↓o
</span><span style="color:gray">__objc_const:00007FFF818EFB48                 </span>__objc2_meth &lt;<span style="color:navy">offset </span>sel__setStyle_<span style="color:navy">, offset aV2408q16, \ </span><span style="color:gray">; -[BCChatButton _setStyle:] ...
__objc_const:00007FFF818EFB48                               </span><span style="color:navy">offset </span>__BCChatButton__setStyle__&gt;
<span style="color:gray">__objc_const:00007FFF818EFB60                 </span>__objc2_meth &lt;<span style="color:navy">offset </span>sel__cxx_destruct<span style="color:navy">, offset aV1608, \ </span><span style="color:gray">; -[BCChatButton .cxx_destruct] ...
__objc_const:00007FFF818EFB60                               </span><span style="color:navy">offset </span>__BCChatButton__cxx_destruct_&gt;
<span style="color:gray">__objc_const:00007FFF818EFB78                 </span>__objc2_meth &lt;<span style="color:navy">offset </span>sel_initWithCoder_<span style="color:navy">, offset a240816, \ </span><span style="color:gray">; -[BCChatButton initWithCoder:] ...
__objc_const:00007FFF818EFB78                               </span><span style="color:navy">offset </span>__BCChatButton_initWithCoder__&gt;
</span>
</div>

## Fixing lazy pointers

So now the Objective-C method is found... and it promptly segfaults on the first call to objc_msgSendSuper, with a jump into an unmapped region of memory. To understand why, I had to learn how method calls work in Mach-O.

To speed up library loading, Mach-O uses **lazy binding**, which only looks up an external method when it is used for the first time. To do this, calls to external methods actually jumps to **stubs** - a short piece of code that loads a pointer from the Mach-O file's `__la_symbol_ptr` section, and jumps to it.

When the program starts, each of these pointers in `__la_symbol_ptr` points to a matching **resolver function**, whose job is to look up the real external method for that stub.

The first time an external method is called:

- the code calls stub
- stub loads address from its `la_symbol_ptr`, which initially points to its resolver, and jumps to it
- the resolver function:
  - actually finds the function to call
  - writes the address of the real function over the `la_symbol_ptr` variable
  - jumps to the real function
  
from this point on, future calls will:

- call stub
- stub loads address from `la_symbol_ptr`, which now contains the address of the real function stored by the resolver, and jumps to it

This means that the resolver is only invoked the first time, and the overhead is negligible for subsequent calls.

(ELF on Linux has the exact same system, by the way: it's called the [Procedure Linkage Table](https://www.iecc.com/linker/linker10.html).)

When building the dyld cache, the dyld cache tries to remove this lazy loading: by performing the resolution ahead of time, it avoids the initial lookup in the stub. So when we extract the library, the stub addresses, instead of pointing to the correct resolver functions, point to the nonexistant functions from the other libraries in the cache.

We fix this by restoring the resolver function for each entry in the `__la_symbol_ptr`. To do that:

for each resolver function:

- get the resolver data
- find where the resolver must write the final address (i.e. what the dyld cache must've changed)
- change the value at this address to point to this current resolver function

With this final problem fixed, I was able to run the test program just fine, proving that we've extracted one library from the dyld shared cache.

## What remains

All the changes I made to dsc_extractor is [available on GitHub](https://github.com/zhuowei/dsc_extractor_badly/compare/original...master).


So now I can extract from x86_64 a simple library: this is of course pointless since I can just grab the library from disk. I really want this to extract from arm64 iOS, where there no library. Unfortunately, arm64 is a bit more complicated.

arm64 has two more segments in each library, __DATA_CONST and __DATA_DIRTY, and, my dyld cache relocation code doesn't relocate these new segments properly. Since all the other fixes depend on that, I can't extract any arm64 libraries yet.

In addition, I need to fix Objective-C protocols' selectors, like how I fixed the method selectors.

I'm currently looking into fixing these to accomplish my goal of extract a library from one iOS firmware and port it to a different firmware. (Watch for Part 2 next week!)

## Epilogue: but do I really need that?

So I did all this complicated work, intending to port some code from one iOS firmware to another. But I need to ask myself again, "do I really need this"?

I know one similar iOS code porting project: [@stroughtonsmith](https://twitter.com/stroughtonsmith) and [@chpwn](https://twitter.com/chpwn) [ported Siri to the iPhone 4](https://www.theiphonewiki.com/wiki/Siri).

Instead of going through all this trouble to extract one individual library, Stroughtonsmith and Chpwn simply [replaced the entire shared cache](https://www.theiphonewiki.com/wiki/Siri#Shared_Cache_Injection) for certain processes. According to Stroughtonsmith, this took ["15 minutes over lunch"](https://twitter.com/stroughtonsmith/status/1010423049466851328), versus the one month - and counting - I've spent learning to extract a library. I'm guessing it probably also worked better than my attempt.

I guess the lesson is: always trying to find out what you really need. Do I need an identical library to the original, like what imaon2 tries to produce? Do I need an invidual library that loads, like what I tried to make? Or do I just need to get some feature from one device to another?

## What I learned

- programming is like entrepreneurship: find out what problem you're solving first, so you can ask, "do you really need that" and save yourself time
- How Mach-O works, how its concepts are similar to ELF
- how Objective-C runtime resolve methods by comparing selectors with unique addresses
- Open source code that don't work can still be an inspiration, like how imaon2's ObjC fixup module helped me realize what I need to do

## Notes

Sorry about the delay! I had to shelve my intended project for June 14 due to a lack of time (I'll eventually come back to it), so I decided to take as much time as I needed to research and write this week's post. The schedule will be back to normal next week.


