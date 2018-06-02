---
title: iOS Simulator's secret trick to enable case sensitivity
categories: macos, ios
permalink: /casesensitive-iossim/
---

Macs are case insensitive, but the iOS Simulator uses a hidden option in macOS's kernel to enable case sensitivity, to match real iOS devices. This option can also be set with macOS's `taskpolicy` tool, so you can launch any macOS process with case sensitivity enabled.

## Introduction

Macs have a case insensitive filesystem by default: you can access a file named "bash" by opening "bash", "Bash", or "bAsh".

We can verify this: in an Xcode Playground targetting macOS, I ran this Swift code:

```
print("/bin/bash exists? \(FileManager.default.fileExists(atPath: "/bin/bash"))")
print("/bin/Bash exists? \(FileManager.default.fileExists(atPath: "/bin/Bash"))")
```

which prints

```
/bin/bash exists? true
/bin/Bash exists? true
```

However, iOS devices are all case sensitive. I was surprised that Xcode's iOS Simulator is able to emulate this: running the same code in the iOS Simulator prints

```
/bin/bash exists? true
/bin/Bash exists? false
```

confirming that the Simulator has a case sensitive filesystem. So how does it simulate case sensitivity on a case insensitive Mac?

## Into the Kernel

I found this iOS Simulator feature by accident. I was researching how programs exit on macOS, and while diving through macOS's kernel source code, came across this interesting function in [bsd/kern/kern_proc.c](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/bsd/kern/kern_proc.c#L1791):

```
int
proc_is_forcing_hfs_case_sensitivity(proc_t p)
{
	return (p->p_vfs_iopolicy & P_VFS_IOPOLICY_FORCE_HFS_CASE_SENSITIVITY) ? 1 : 0;
}
```

I was intrigued. A per-process case sensitivity flag? Where is it set? I [searched](https://github.com/apple/darwin-xnu/search?utf8=✓&q=P_VFS_IOPOLICY_FORCE_HFS_CASE_SENSITIVITY&type=) through the source code, and found that it's set in [bsd/kern/kern_resource.c](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/bsd/kern/kern_resource.c#L1633), in the syscall handler for the `setiopolicy_np` function:

```
		case IOPOL_CMD_SET:
			if (0 == kauth_cred_issuser(kauth_cred_get())) {
				/* If it's a non-root process, it needs to have the entitlement to set the policy */
				boolean_t entitled = FALSE;
				entitled = IOTaskHasEntitlement(current_task(), "com.apple.private.iopol.case_sensitivity");
				if (!entitled) {
					error = EPERM;
					goto out;
				}
			}

			switch (policy) {
				case IOPOL_VFS_HFS_CASE_SENSITIVITY_DEFAULT:
					OSBitAndAtomic16(~((uint32_t)P_VFS_IOPOLICY_FORCE_HFS_CASE_SENSITIVITY), &p->p_vfs_iopolicy);
					break;
				case IOPOL_VFS_HFS_CASE_SENSITIVITY_FORCE_CASE_SENSITIVE:
					OSBitOrAtomic16((uint32_t)P_VFS_IOPOLICY_FORCE_HFS_CASE_SENSITIVITY, &p->p_vfs_iopolicy);
					break;
				default:
					error = EINVAL;
					goto out;
			}
			
			break;
```

So if the process is running as `root` or if it has a special permission ("com.apple.private.iopol.case_sensitivity") granted by Apple, it can turn on case sensitivity for itself through a call to [`setiopolicy_np`](com.apple.private.iopol.case_sensitivity). All child processes also [inherit](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/bsd/kern/kern_fork.c#L1269) the case sensitivity.

The relevant IO policy constants are hidden behind an `#if private` preprocessor block in [`sys/resources.h`](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/bsd/sys/resource.h#L488), indicating that this is a private API.

So what does this flag actually do? Well, the HFS kernel module calls `proc_is_forcing_hfs_case_sensitivity` when looking up filenames:

```
hfs-407.30.1 $ grep -r proc_is_forcing_hfs_case_sensitivity .
./core/hfs_search.c:	int force_case_sensitivity = proc_is_forcing_hfs_case_sensitivity(vfs_context_proc(ctx));
./core/hfs_lookup.c:	int force_casesensitive_lookup = proc_is_forcing_hfs_case_sensitivity(p);
```

In both [hfs_lookup](https://opensource.apple.com/source/hfs/hfs-407.30.1/core/hfs_lookup.c.auto.html
) and [hfs_search](https://opensource.apple.com/source/hfs/hfs-407.30.1/core/hfs_search.c.auto.html
), the force case sensitivity flag is OR'ed with the filesystem's own case sensitivity flag, changing filename lookup behaviour to match a case sensitive HFS+ filesystem.

APFS seems to do the same: while I don't have source code, its kernel module definitely contains the same call to check if case sensitivity is enabled for the current process:

```
strings - /System/Library/Extensions/apfs.kext/Contents/MacOS/apfs|grep sensitivity
_proc_is_forcing_hfs_case_sensitivity
```

## The Simulator

As mentioned above, this ability is only given to root and any process with the "com.apple.private.iopol.case_sensitivity" entitlement. According to Jonathan Levin's site, [nothing in macOS itself has this entitlement](http://newosxbook.com/ent.jl?ent=&osVer=MacOS13).

So does the Simulator use this feature? Well, the Simulator doesn't run as root, so it would need this entitlement to enable it. 

In addition, since the flag is inherited by all child processes, it would make sense for the first process in the simulator to set this flag, so that all the processes started from this initial process would all be case sensitive. On iOS itself, this initial startup executable is `launchd`. On the Simulator, its role is taken by `launchd_sim`.

Looking at `/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/Library/CoreSimulator/Profiles/Runtimes/iOS.simruntime/Contents/Resources/RuntimeRoot/sbin`, I found two binaries: `launchd_sim` and `launchd_sim_trampoline`. It turns out the trampoline is the one with the entitlement:

```
$ grep -r case_sensitivity .
Binary file ./launchd_sim_trampoline matches
```

and `strings - launchd_sim_trampoline` lets us extract the entitlements to confirm:

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
<key>com.apple.private.iopol.case_sensitivity</key>
<true/>
</dict>
</plist>
```

It seems that `launchd_sim_trampoline` sets the case sensitivity flag, then starts the real `launchd_sim`, ensuring that every process in the simulator, even `launchd_sim` itself, gets a case sensitive filesystem. 

## Using this outside the simulator

It turns out that the simulator's not the only tool that can enable case sensitivity.

Searching for `"IOPOL_VFS_HFS_CASE_SENSITIVITY_FORCE_CASE_SENSITIVE"` on Google links to [the source](https://opensource.apple.com/source/system_cmds/system_cmds-597.90.1/taskpolicy.tproj/taskpolicy.c) for the `taskpolicy` tool built into macOS, with this relevant section:

```
	if (flagx) {
		ret = setiopolicy_np(IOPOL_TYPE_VFS_HFS_CASE_SENSITIVITY, IOPOL_SCOPE_PROCESS, IOPOL_VFS_HFS_CASE_SENSITIVITY_FORCE_CASE_SENSITIVE);
		if (ret == -1) {
			err(EX_SOFTWARE, "setiopolicy_np(IOPOL_TYPE_VFS_HFS_CASE_SENSITIVITY...)");
		}
	}
```


This code checks for a `-x` flag (not documented in the manpage), and if found enables case sensitive mode. After all options are applied, `taskpolicy` then launches the target program with the enabled options.

This looks like a good way to test the per-process case sensitive support: is it still available on macOS 10.13.4?

```
$ taskpolicy
Usage: taskpolicy [-x|-X] [-d <policy>] [-g policy] [-c clamp] [-b] [-t <tier>]
                  [-l <tier>] [-a] <program> [<pargs> [...]]
       taskpolicy [-b|-B] [-t <tier>] [-l <tier>] -p pid
```

Yep, still there.

Unfortunately, taskpolicy does not have the entitlement, so it can only set this flag if it's running as root. So let's use our test program again:

```
import Foundation
print("/bin/bash exists? \(FileManager.default.fileExists(atPath: "/bin/bash"))")
print("/bin/Bash exists? \(FileManager.default.fileExists(atPath: "/bin/Bash"))")
```

compile and run as root:

```
$ swiftc -o casetest casetest.swift
$ sudo bash
# ./casetest 
/bin/bash exists? true
/bin/Bash exists? true
# taskpolicy -x ./casetest
/bin/bash exists? true
/bin/Bash exists? false
```

And taskpolicy is able to enable case sensitive mode for our test program. One could probably make a wrapper around `taskpolicy` and `sudo` to launch desktop applications in case sensitive mode as well.

## Conclusion

- Apple worked hard to make sure apps would work on real devices without depending on simulator specific behaviours. As [explained by the developer of Higan, an SNES emulator](https://arstechnica.com/gaming/2011/08/accuracy-takes-power-one-mans-3ghz-quest-to-build-a-perfect-snes-emulator/), an inaccurate emulator will mislead developers who can't test on the real device into relying on emulator quirks that won't work on the real device; hence the drive for accuracy in both game console emulation and Xcode's iOS simulation.

- Apple believes in improving tooling to help developers avoid mistakes and bugs. Originally, the iOS Simulator did not have case sensitivity, and in 2010 [Apple noticed this was causing problems for developers](https://developer.apple.com/library/content/qa/qa1697/_index.html). Thus, Apple [added this case sensitivity simulation](https://github.com/apple/darwin-xnu/blame/0a798f6738bc1db01281fc08ae024145e84df927/bsd/kern/kern_proc.c#L1791) to OS X Mavericks (10.9/XNU 2422), released in 2013. This was just one tooling improvement among many others in the same period: Automatic Reference Counting was released in 2011, and Swift was released in 2014.

- When you own the entire platform, including the kernel, the filesystem, the simulated platform, and the simulator, you can pull off some cool tricks. This tight integration ensures that the iOS Simulator consistently provides a better experience for developers than the Android Emulator.

- in summary, this kernel change shows just how much effort Apple puts into Xcode to make iOS a developer friendly mobile OS.


## What I learned

- When encountering a simulation environment, I should immediately check for potential differences between real and emulated environment - the results may be surprising.
- You never know what you can find when reading source code, and it may provide answers to questions you didn't know to ask.
- Even the smallest feature can be interesting to examine. This will help me choose future blog topics that are interesting and can be covered in a short concise article.
