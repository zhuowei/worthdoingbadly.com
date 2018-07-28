---
title: Changing macOS's uptime with a kernel extension
categories: macos
permalink: /uptimekext/
---

`up 74007 days, 22:31`? Yeah, seems legit: I booted my computer 200 years ago on [December 10th, 1815](http://www.wolframalpha.com/input/?i=74007+days+22+hours+before+july+26,+2018). Actually, I wrote a kernel extension to change the output of the `uptime` command on macOS, to learn the basics of kernel module programming.

## Introduction

On Unix systems such as macOS, the `uptime` command tells you how long the computer has been running:

```
$ uptime
23:28  up 1 day, 13:34, 3 users, load averages: 1.56 1.47 1.49
```

Having a high uptime is a (pointless) badge of honour among computer nerds. My computers are too unstable to keep running for years at a time, so I decided to look into artificially inflating the uptime to get this meaningless symbol.

There are plenty of tools to modify the uptime on Linux: one [manually increments](http://web.archive.org/web/20161025152929/http://etheus.net/UptimeFaker) the kernel's uptime counter, which unfortunately destabilizes the kernel. Another [modifies the /proc entry](https://github.com/dkorunic/uptime_hack) to return a different value. Yet another [patchs the kernel's code](https://www.anfractuosity.com/projects/uptime/) that calculates the uptime. However, there's no tools for macOS. So I made one.

## How to run

This makes your computer unstable. **Do NOT run on a computer you care about.** (I used a virtual machine.)

I tested this on macOS Mojave 10.14 beta 1.

Since this is a kernel module, System Integrity Protection must be disabled.

[Grab the source](https://github.com/zhuowei/MacUptimeChanger), build it in Xcode 10 beta, copy the UptimeChanger.kext, and run in a terminal:

```
sudo kextunload -b com.worthdoingbadly.UptimeChanger
sudo chown -R root:wheel UptimeChanger.kext
sudo kextutil UptimeChanger.kext
```

then run

```
sudo sysctl kern.changeboottime=<unix timestamp of system boot>
```

to change the boot time of the system. The uptime is then (current time - boot time), of course.

For example, to produce the example from the start of the post, I ran:

```
$ uname -a
Darwin local 18.0.0 Darwin Kernel Version 18.0.0: Fri May 25 16:54:22 PDT 2018; root:xnu-4903.200.199.11.1~1/RELEASE_X86_64 x86_64
$ date
Wed Jul 25 23:48:52 EDT 2018
$ sudo sysctl kern.changeboottime=-4861708948
kern.changeboottime: 1532575384 -> -4861708948
$ uptime
23:48  up 74007 days, 22:31, 4 users, load averages: 0.89 0.97 1.27
```

The result is surprisingly stable: apps all ran as normal, with the exception of `ssh`, which prints an error:

```
select: invalid argument
```

when the boot time is set before the Unix epoch.

So how does this tool work?

## How uptime works

To develop a tool to change uptime, I first need to know how uptime is calculated.

The [source for `uptime`](https://opensource.apple.com/source/shell_cmds/shell_cmds-34/w/w.c) shows that it reads the `kern.boottime` sysctl, and subtracts the result from the current time to get the uptime.

```
	/*
	 * Print how long system has been up.
	 * (Found by looking getting "boottime" from the kernel)
	 */
	mib[0] = CTL_KERN;
	mib[1] = KERN_BOOTTIME;
	size = sizeof(boottime);
	if (sysctl(mib, 2, &boottime, &size, NULL, 0) != -1 &&
	    boottime.tv_sec != 0) {
		uptime = now - boottime.tv_sec;
```

The kernel [handles this sysctl](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/bsd/kern/kern_sysctl.c#L2007) by [grabbing the value](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/kern/clock.c#L1068) from two variables storing the time when the system was booted.

These values seems to be writable: the clock code [already updates](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/kern/clock.c#L743) the booted time when a user sets the clock, so writing to it probably won't cause any ill effects to the system, unlike the Linux tool.

## Creating a kext

Until Leopard, regular programs can write to the kernel using `task_for_pid(0)`. Now, the only way to modify values in the kernel is to use a kernel extension, which is loaded into the kernel itself, and thus has access to anything the kernel can access.

Thankfully, there are many tutorials for creating a kext (such as [apriorit's](https://www.apriorit.com/dev-blog/430-macos-kext-development)): so the process was quite easy to follow.

To develop an unsigned kext, I first had to disable [System Integrity Protection](https://developer.apple.com/library/archive/documentation/Security/Conceptual/System_Integrity_Protection_Guide/KernelExtensions/KernelExtensions.html#//apple_ref/doc/uid/TP40016462-CH4-SW1).

Next, I created a kernel extension in Xcode. Xcode has two templates for kernel extensions: the IOKit extension is used for device drivers, while the Generic Kernel Extension is used for all other extensions. I used the Generic Kernel Extension template.

This gives me a basic kernel extension, with two methods - one called when the extension is added, and one called when it's removed.

## Accessing the variable

The variable we want to access is unfortunately a static variable, and thus cannot be found in the kernel's symbol table.

```
/* Boottime variables*/
static uint64_t clock_boottime;
```

That's OK: I can calculate the variable's address by examing the code that uses the variable.

Unfortunately, the methods that directly access it [aren't exported](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/kern/clock.h#L170) in the public kernel extension API either:

```
#ifdef	XNU_KERNEL_PRIVATE
extern void			clock_get_boottime_microtime(
						clock_sec_t			*secs,
						clock_nsec_t		*microsecs);
#endif
```

However, they are in the kernel's private symbols. [Nemo, Snare, and Jonathan Zdziarski](https://www.zdziarski.com/blog/?p=6901) developed a library to look up functions in a kernel's private symbols. Once I [added their library](https://github.com/jzdziarski/kernelresolver), I was able to [find and call](https://github.com/zhuowei/MacUptimeChanger/blob/master/UptimeChanger/UptimeChanger.c#L61) `clock_get_boottime_microtime` to read the uptime.

To find the location of `clock_boottime` so I can write to it, I looked for the line in `clock_get_boottime_microtime` that read from the variable:

<pre><code>
void
clock_get_boottime_microtime(
	clock_sec_t			*secs,
	clock_usec_t		*microsecs)
{
	spl_t	s;

	s = splclock();
	clock_lock();

<span style="color: red">	*secs = (clock_sec_t)clock_boottime;</span>
	*microsecs = (clock_nsec_t)clock_boottime_usec;

	clock_unlock();
	splx(s);
}
</code></pre>


Then I used `lldb` to disassemble the `clock_get_boottime_microtime`'s machine code for the matching instruction.

<pre><code>$ lldb /System/Library/Kernels/kernel
(lldb) target create "/System/Library/Kernels/kernel"
Current executable set to '/System/Library/Kernels/kernel' (x86_64).
(lldb) b clock_get_boottime_microtime
Breakpoint 1: where = kernel`clock_get_boottime_microtime, address = 0xffffff80003ddf60
(lldb) x/32i 0xffffff80003ddf60
0xffffff80003ddf60: 55                    pushq  %rbp
0xffffff80003ddf61: 48 89 e5              movq   %rsp, %rbp
0xffffff80003ddf64: 41 57                 pushq  %r15
0xffffff80003ddf66: 41 56                 pushq  %r14
0xffffff80003ddf68: 41 54                 pushq  %r12
0xffffff80003ddf6a: 53                    pushq  %rbx
0xffffff80003ddf6b: 49 89 f6              movq   %rsi, %r14
0xffffff80003ddf6e: 49 89 fc              movq   %rdi, %r12
0xffffff80003ddf71: 9c                    pushfq
0xffffff80003ddf72: 5b                    popq   %rbx
0xffffff80003ddf73: f6 c7 02              testb  $0x2, %bh
0xffffff80003ddf76: 74 01                 je     0xffffff80003ddf79
0xffffff80003ddf78: fa                    cli
0xffffff80003ddf79: 4c 8d 3d f8 86 8b 00  leaq   0x8b86f8(%rip), %r15
0xffffff80003ddf80: 4c 89 ff              movq   %r15, %rdi
0xffffff80003ddf83: e8 08 42 12 00        callq  0xffffff8000502190
<span style="color: red">0xffffff80003ddf88: 48 8b 05 09 73 a4 00  movq   0xa47309(%rip), %rax</span>
0xffffff80003ddf8f: 49 89 04 24           movq   %rax, (%r12)
0xffffff80003ddf93: 8b 05 f7 72 a4 00     movl   0xa472f7(%rip), %eax
0xffffff80003ddf99: 41 89 06              movl   %eax, (%r14)
0xffffff80003ddf9c: 4c 89 ff              movq   %r15, %rdi
0xffffff80003ddf9f: e8 ac 43 01 00        callq  0xffffff80003f2350
0xffffff80003ddfa4: 9c                    pushfq
0xffffff80003ddfa5: 58                    popq   %rax
0xffffff80003ddfa6: f6 c7 02              testb  $0x2, %bh
0xffffff80003ddfa9: 75 08                 jne    0xffffff80003ddfb3
0xffffff80003ddfab: f6 c4 02              testb  $0x2, %ah
0xffffff80003ddfae: 74 21                 je     0xffffff80003ddfd1
0xffffff80003ddfb0: fa                    cli
0xffffff80003ddfb1: eb 1e                 jmp    0xffffff80003ddfd1
0xffffff80003ddfb3: fb                    sti
0xffffff80003ddfb4: 90                    nop
</code></pre>

The instruction that reads the variable is

```
0xffffff80003ddf88: 48 8b 05 09 73 a4 00  movq   0xa47309(%rip), %rax
```

It uses PC-relative addressing, so to calculate the pointer to the variable, I took the address of the next instruction (0xffffff80003ddf8f), added the offset from the last 4 bytes of the current instruction (0xa47309), and [I got a pointer](https://github.com/zhuowei/MacUptimeChanger/blob/master/UptimeChanger/UptimeChanger.c#L74) to `clock_boottime`.

To verify, I called `clock_get_boottime_microtime` and checked that its returned value matches the value I read directly from `clock_boottime`.

## Creating the sysctl

There are multiple ways for a kernel extension to communicate with a program. I chose to export a `sysctl` variable, since these values can be easily set from the command line.

There are many guides on creating a new sysctl: I followed [this one by Apple](https://developer.apple.com/library/archive/documentation/Darwin/Conceptual/KernelProgramming/boundaries/boundaries.html#//apple_ref/doc/uid/TP30000905-CH217-BABJJBHG).

First, I declared the sysctl using:

```
SYSCTL_PROC(_kern, OID_AUTO, changeboottime, CTLTYPE_INT | CTLFLAG_WR,
	NULL, 0, UptimeChanger_sysctl_kern_changeboottime, "L",
	"change uptime by setting boot time, in seconds since Unix epoch");
```

This macro specifies that it's a write only sysctl, with long integer type (to match the boot type variable), and managed by the `UptimeChanger_sysctl_kern_changeboottime` function.

Next, I [added calls](https://github.com/zhuowei/MacUptimeChanger/blob/master/UptimeChanger/UptimeChanger.c#L116) to register and unregister this sysctl in the kext's start and stop functions.

Finally, I implemented the function that handles setting this sysctl: [all I had to do](https://github.com/zhuowei/MacUptimeChanger/blob/master/UptimeChanger/UptimeChanger.c#L89) was verify that the pointer to the value is valid, then just call the existing sysctl code for setting long integer variables. After the value is set, I also update the commpage's value, just like the set system clock code.

## building and running the kext

There's one last step before the kext can be loaded: [I needed](http://www.robertopasini.com/index.php/2-uncategorised/627-osx-command-line-tools-for-analyzing-kernel-extensions) to run

```
kextlibs -xml UptimeChanger.kext
```

and copy the resulting list of libraries into the Info.plist.

It took a few system crashes to debug the address calculation, but once I fixed that, the sysctl worked flawlessly.

## What I learned

- It's easy to get started with kext programming on macOS
- ssh doesn't work when boot time is set before the Unix epoch. Odd. I wonder why.
- How to write a short(er) article - I'm learning to make and write up simpler projects so I can dedicate more time for occational larger projects such as the [iOS QEMU](/xnuqemu2/) post.
