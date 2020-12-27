---
title: Examining CVE-2020-27932 on macOS 10.15.7
categories: macos, qemu
permalink: /specialreply/
---

macOS 11.0/iOS 14.2/iOS 12.4.9 [fixed](https://support.apple.com/en-us/HT211946) an issue where `host_request_notification` doesn't check `port->ip_specialreply`, causing it to overwrite `ip_sync_inheritor_port`. This can be used to reboot the system with a zone check error, but I can't figure out what else this can do.

## The change

As detailed by [Synacktiv](https://www.synacktiv.com/en/publications/ios-1-day-hunting-uncovering-and-exploiting-cve-2020-27950-kernel-memory-leak.html), the fix for CVE-2020-27932 can also be found with BinDiff.

Running the same procedure as their blog post shows that the remaining patched function was fffffff0076bb370: `host_request_notification`.

The fixed function just adds one additional check.

![BinDiff graph view, showing two blocks of code side by side, with one extra highlighted line on the right](/assets/blog/specialreply/bindiff_graph.png)

[Original](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/osfmk/kern/host_notify.c#L104):

```
if (!ip_active(port) || port->ip_tempowner || ip_kotype(port) != IKOT_NONE) {
```

New:

```
if (!ip_active(port) || port->ip_tempowner || port->ip_specialreply || ip_kotype(port) != IKOT_NONE) {
```

Indeed, this code runs without error on old macOS/iOS, but fails with `KERN_FAILURE` after macOS 11.0/10.5.7 November update/iOS 14.2/iOS 12.4.9:

```
mach_port_t port = thread_get_special_reply_port();
kern_return_t err = host_request_notification(mach_host_self(), HOST_NOTIFY_CALENDAR_CHANGE, port);
```

## host_request_notification

This function is used to get a notification whenever the date or the time changes on a macOS/iOS system.

Calling [`host_request_notification`](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/kern/host_notify.c#L81) adds the port to a doubly linked list of ports that will receive date/time change notifications.

To allow easily removing the port from the linked list, the list entry is also stored in the port's `ip_kobject` field.

```
ipc_kobject_set_atomically(port, (ipc_kobject_t)entry, IKOT_HOST_NOTIFY);
```

It sets `ip_kotype(port)` to `IKOT_HOST_NOTIFY`, and `port->ip_kobject` to the entry.

This is how the kernel associates a Mach port with a kernel object. Other Mach ports representing a kernel object, such as task ports or timer ports, also use `ip_kotype` and `ip_kobject` to store their associated kernel objects.

When the port is destroyed, it calls [`host_notify_port_destroy`](https://github.com/apple/darwin-xnu/blob/0a798f6738bc1db01281fc08ae024145e84df927/osfmk/kern/host_notify.c#L123), which reads the list entry back out and unlinks it from the list.

```
if (ip_kotype(port) == IKOT_HOST_NOTIFY) {
	entry = (host_notify_t)port->ip_kobject;
```

So what's so special about special reply ports? What can they do that no other port can?

## Special reply ports

Searching for `ip_specialreply` in the kernel source brings up only 29 references: most to do with QoS and turnstiles.

In [Mach RPC](https://developer.apple.com/library/archive/documentation/Darwin/Conceptual/KernelProgramming/Mach/Mach.html), ports are one-way, so when you send a message to another process, you also include a reply port. The remote process sends its response back to your reply port.


See this note in [osfmk/mach/message.h](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/osfmk/mach/message.h#L204):

```
 *  The msgh_remote_port field specifies the destination of the message.
 *  It must specify a valid send or send-once right for a port.
 *
 *  The msgh_local_port field specifies a "reply port".  Normally,
 *  This field carries a send-once right that the receiver will use
 *  to reply to the message.  It may carry the values MACH_PORT_NULL,
 *  MACH_PORT_DEAD, a send-once right, or a send right.
```

Here's my high quality diagram of how Mach messages work:

```
Me          -----------------------------------> [destination port] other process
            {message, reference to reply port}
[reply port] <----------------------------------
            {response message}
```

Since almost every IPC request has a response, Mach lets you create a special reply port, which is optimized by the kernel for better QoS during replies - for example, avoiding priority inversions. For this QoS to work, reply ports are linked to the destination port when messages are sent and received.

The special reply ports changed in iOS 11 and 12:

In iOS 11, instead of a single reply port per task ([mach_reply_port](http://web.mit.edu/darwin/src/modules/xnu/osfmk/man/mach_reply_port.html)), reply ports are now created per-thread, via the `thread_get_special_reply_port` function.

Since a process can now have multiple special reply ports, iOS added the `ip_specialreply` boolean to indicate that the port is a special reply port.

Comparing xnu-3789.1.32's `osfmk/ipc/ipc_port.h` with xnu-4570.1.46:

```
-                 ip_reserved:2,
+                 ip_specialreply:1,    /* port is a special reply port */
+                 ip_link_sync_qos:1,   /* link the special reply port to destination port */
```

In iOS 12, the QoS system for reply ports was rewritten to allow linking not just to ports, but to other QoS objects such as knotes and turnstiles. Comparing xnu-4570.1.46 with xnu-4903.221.2:
```
                   ip_specialreply:1,    /* port is a special reply port */
-                  ip_link_sync_qos:1,   /* link the special reply port to destination port */
+                  ip_sync_link_state:3, /* link the special reply port to destination port/ Workloop */
```

So on iOS 12, we get [these fields](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/osfmk/ipc/ipc_port.h#L154) to represent the special reply and its linkages:

```
ip_specialreply:1,          /* port is a special reply port */
ip_sync_link_state:3,       /* link the port to destination port/ Workloop */
```

The `ip_sync_link_state` field can take on [these values](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/osfmk/ipc/ipc_port.h#L215):

```
/*
 * SYNC IPC state flags for special reply port/ rcv right.
 *
 * PORT_SYNC_LINK_ANY
 *    Special reply port is not linked to any other port
 *    or WL and linkage should be allowed.
 *
 * PORT_SYNC_LINK_PORT
 *    Special reply port is linked to the port and
 *    ip_sync_inheritor_port contains the inheritor
 *    port.
 *
 * PORT_SYNC_LINK_WORKLOOP_KNOTE
 *    Special reply port is linked to a WL (via a knote).
 *    ip_sync_inheritor_knote contains a pointer to the knote
 *    the port is stashed on.
 *
 * PORT_SYNC_LINK_WORKLOOP_STASH
 *    Special reply port is linked to a WL (via a knote stash).
 *    ip_sync_inheritor_ts contains a pointer to the turnstile with a +1
 *    the port is stashed on.
 *
 * PORT_SYNC_LINK_NO_LINKAGE
 *    Message sent to special reply port, do
 *    not allow any linkages till receive is
 *    complete.
 *
 * PORT_SYNC_LINK_RCV_THREAD
 *    Receive right copied out as a part of bootstrap check in,
 *    push on the thread which copied out the port.
 */
```

So how are these linkages created?

## Linkage

A linkage is created when a process sends a message to a destination port with an attached reply port, through this call chain:

- `mach_msg_overwrite_trap`
- `ipc_kmsg_copyin_header`
- `ipc_kmsg_set_qos`
- `ipc_port_link_special_reply_port`.

Alternatively, it can also be created when the destination receives the message, through this call chain:
- `mach_msg_overwrite_trap`
- `mach_msg_rcv_link_special_reply_port`
- `ipc_port_link_special_reply_port`

In both cases, the linkage is created as [follows](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/osfmk/ipc/ipc_port.c#L1411):

```
	/* Check if we need to drop the acquired turnstile ref on dest port */
	if (!special_reply_port->ip_specialreply ||
	    special_reply_port->ip_sync_link_state != PORT_SYNC_LINK_ANY ||
	    special_reply_port->ip_sync_inheritor_port != IPC_PORT_NULL) {
		drop_turnstile_ref = TRUE;
	} else {
		/* take a reference on dest_port */
		ip_reference(dest_port);
		special_reply_port->ip_sync_inheritor_port = dest_port;
		special_reply_port->ip_sync_link_state = PORT_SYNC_LINK_PORT;
	}
```

So: if the special port can be linked and there's no inheritor port yet, link the reply port to the destination port.

When the special reply port needs to be updated (for example, after the destination receives the message, or when an old thread special port is replaced by a new one), the kernel calls `ipc_port_adjust_special_reply_port_locked`, which updates the special reply port's linked object depending on its current state.

If the port is not linked, [nothing happens](https://github.com/knightsc/darwin-xnu/blob/bde2581420e9d87b7335984d3408e4ddabf3cb87/osfmk/ipc/ipc_port.c#L1736):

```
	/* Check if the special reply port is marked non-special */
	if (special_reply_port->ip_sync_link_state == PORT_SYNC_LINK_ANY) {
not_special:
		if (get_turnstile) {
			turnstile_complete((uintptr_t)special_reply_port,
			    port_rcv_turnstile_address(special_reply_port), NULL, TURNSTILE_SYNC_IPC);
		}
		imq_unlock(&special_reply_port->ip_messages);
		ip_unlock(special_reply_port);
		if (get_turnstile) {
			turnstile_cleanup();
		}
		return;
	}
```

Otherwise, depending on the state and the new desired linkage, the linkage is swapped between a port/knote/turnstile.

These two functions are, as far as I can find, the only functions that write to `ip_sync_inheritor_port`.
In addition, `ipc_port_adjust_special_reply_port_locked` is the only function to write to the other two fields, `ip_sync_inheritor_knote` and `ip_sync_inheritor_ts`.

Why is writing to these fields important?

## The issue

`ip_kobject`, `ip_sync_inheritor_port`, `ip_sync_inheritor_knote`, and `ip_sync_inheritor_ts` are [declared](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/osfmk/ipc/ipc_port.h#L130) **in a union!!**

```
union {
	ipc_kobject_t kobject;
	ipc_importance_task_t imp_task;
	ipc_port_t sync_inheritor_port;
	struct knote *sync_inheritor_knote;
	struct turnstile *sync_inheritor_ts;
} kdata;
```

However, the fields keeping track of what's in these fields are **separate**: `ip_kotype` and `ip_sync_link_state` are not stored together.

This means that it's possible to **overwrite** a `ip_sync_inheritor_port` with a linked list entry using `host_request_notification`!

There are multiple ways to do this, but here's the simplest way to crash the kernel with this issue:

First, we call `thread_get_special_reply_port`.

This creates a new special reply port for this thread:

```
Reply port
 - ip_sync_link_state: PORT_SYNC_LINK_ANY
 - {ip_kobject, ip_sync_inheritor_*}: null
 - ip_kotype: IKOT_NONE
```

To change ip_sync_link_state we need to invoke `ipc_port_link_special_reply_port`.

The easiest way to invoke this is to try to receive a message on the special reply port, using the destination port as the notify port. (as shown in the [kernel's unit test](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/tests/kevent_qos.c#L1039), `tests/kevent_qos.c`)

`mach_msg_rcv_link_special_reply_port` calls `ipc_port_link_special_reply_port`, which links the special reply port to the destination port:

```
Reply port
 - ip_sync_link_state: PORT_SYNC_LINK_PORT
 - {ip_kobject, ip_sync_inheritor_*}: destination port
 - ip_kotype: IKOT_NONE
```

While that waits to receive a message, in another thread we call `host_request_notification`, which writes to `ip_kobject` and `ip_kotype` without changing `ip_sync_link_state`:

```
Reply port
 - ip_sync_link_state: PORT_SYNC_LINK_PORT
 - {ip_kobject, ip_sync_inheritor_*}: host notify link entry (overwritten!!)
 - ip_kotype: IKOT_HOST_NOTIFY
```

When the receive times out, the kernel calls `ipc_port_adjust_special_reply_port_locked` to unlink the port. 

This should cause a panic when the function gets a linked list entry instead of the port it expects.

.... that's the theory anyways.

## Let's try it

Thankfully, the special reply port is one of the few parts of the kernel with [unit tests](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/tests/kevent_qos.c#L1039) in `tests/kevent_qos.c`. I just added a `host_request_notification` call to it.

What I [currently have](https://gist.github.com/zhuowei/861fd8878397d9696303259f40cb01b3) triggers a kernel panic on a self-compiled macOS 10.15.6 kernel.
```
Receiving message! object=0xffffff80237e8d48 
mach_msg_rcv_link_special_reply_port port=0xffffff80237e8d48 dest=f0b
mach_msg_rcv_link_special_reply_port got dest port=0xffffff8023e48618
ipc_port_link_special_reply_port: port=0xffffff80237e8d48 dest=0xffffff8023e48618 sync=no state=0 ip_sync_inheritor_port=0
Take a reference: 0xffffff80237e8d48 -> 0xffffff8023e48618
ipc_port_recv_update_inheritor special port=0xffffff80237e8d48 state=1

<snip>

host_request_notification port 0xffffff80237e8d48 old 0xffffff8023e48618 entry 0xffffff801f206390
```

```
panic(cpu 0 caller 0xffffff800630fc8a): "Address not in expected zone for zone_require check (addr: 0xffffff801f206390, zone: ipc ports)"@/
Users/zhuowei/Documents/winprogress/macos11/crashtest/xnubuild/build-xnu/xnu-6153.141.1/osfmk/kern/zalloc.c:662
Backtrace (CPU 0), Frame : Return Address
0xffffff95997758a0 : 0xffffff8006273cee 
0xffffff9599775900 : 0xffffff800627349f 
0xffffff9599775940 : 0xffffff80064df248 
0xffffff9599775990 : 0xffffff80064c7fbe 
0xffffff9599775ad0 : 0xffffff80064e7540 
0xffffff9599775af0 : 0xffffff8006272d78 
0xffffff9599775c40 : 0xffffff8006273916 
0xffffff9599775cc0 : 0xffffff8006e7266f 
0xffffff9599775d30 : 0xffffff800630fc8a 
0xffffff9599775d60 : 0xffffff800623d73d 
0xffffff9599775d80 : 0xffffff80062393e3 
0xffffff9599775db0 : 0xffffff800624224e 
0xffffff9599775df0 : 0xffffff8006242acb 
0xffffff9599775e50 : 0xffffff800625b403 
0xffffff9599775ea0 : 0xffffff800625ae7b 
0xffffff9599775f60 : 0xffffff800625b819 
0xffffff9599775f80 : 0xffffff800623abfc 
0xffffff9599775fa0 : 0xffffff80064bb72e 
```

which is, in my kernel,

```
debugger_collect_diagnostics (in kernel.debug.unstripped) (debug.c:1008)
handle_debugger_trap (in kernel.debug.unstripped) (debug.c:0)
kdp_i386_trap (in kernel.debug.unstripped) (kdp_machdep.c:436)
kernel_trap (in kernel.debug.unstripped) (trap.c:785)
trap_from_kernel (in kernel.debug.unstripped) + 38
DebuggerTrapWithState (in kernel.debug.unstripped) (debug.c:555)
panic_trap_to_debugger (in kernel.debug.unstripped) (debug.c:877)
0xffffff8000e7266f (in kernel.debug.unstripped)
zone_require (in kernel.debug.unstripped) (zalloc.c:664)
ipc_object_validate (in kernel.debug.unstripped) (ipc_object.c:500)
imq_lock (in kernel.debug.unstripped) (ipc_mqueue.c:1872)
ipc_port_send_turnstile_complete (in kernel.debug.unstripped) (ipc_port.c:1571)
ipc_port_adjust_special_reply_port_locked (in kernel.debug.unstripped) (ipc_port.c:1867)
mach_msg_receive_results_complete (in kernel.debug.unstripped) (mach_msg.c:719)
mach_msg_receive_results (in kernel.debug.unstripped) (mach_msg.c:334)
mach_msg_receive_continue (in kernel.debug.unstripped) (mach_msg.c:492)
ipc_mqueue_receive_continue (in kernel.debug.unstripped) (ipc_mqueue.c:993)
```

Running the same code on iOS 14.1 gives me

```
panic(cpu 1 caller 0xfffffff02667d3f0): Kernel data abort. at pc 0xfffffff025f59d2c, lr 0xddf82e7025f5d4d0 (saved state: 0xffffffe8157d3a40)
```

## Other options

It's also possible to trigger this when sending a message: I'm not sure if that would be more convenient.

The opposite - overwriting host_notify's linked list entry with a port/knote/turnstile - seems more difficult:

As mentioned, for a new port with `PORT_SYNC_LINK_ANY`, only `ipc_port_link_special_reply_port` can create the link, and it checks that there's no existing object. So once `host_request_notification` attaches an object, `ipc_port_link_special_reply_port` will no longer work.

I guess you could link a port first, then use `host_request_notification` to overwrite that port with a list entry, then use `ipc_port_adjust_special_reply_port_locked` to overwrite the list entry with a knote or turnstile. But I'm not sure how.

## Now what?

... I have absolutely no idea how this can cause any issues.

There are only a few reachable methods that actually use the value stored in `ip_kobject` or `ip_sync_inheritor_*`.

1. `host_notify_all`:

   We obviously can't use it because apps can't change the system time on iOS.

2. `host_notify_port_destroy`:

   Since the `ip_kotype` is set to a notification, `host_notify_port_destroy` will be called when the port's destroyed.

   As previously mentioned, We can't use `ipc_port_link_special_reply_port` to overwrite the linked list entry as it checks that the port is null before overwriting. If we want to break the `host_notify_port_destroy` function, we would need to figure out how to get `ipc_port_adjust_special_reply_port_locked`, the only other function that sets `ip_sync_inheritor_*` fields, to overwrite the object with a knote or turnstile.

   Even then, the linked list has multiple [safe unlinking checks](https://github.com/apple/darwin-xnu/blob/a449c6a3b8014d9406c2ddbdc81795da24aa7443/osfmk/kern/queue.h#L229) that makes this infeasible.

3. `ipc_port_adjust_special_reply_port_locked` or the variously turnstile/QoS methods

   How would you even do this? How would a linked list node be made even close enough to a task port/knote/turnstile such that these methods won't just crash immediately?

## What I learned

- Encapsulation is important.

  Laugh all you want, but your CS101 textbook is right: object-oriented programming would've prevented this.

  A `setSyncInheritorPort` method can check that there's no kobject already set, and a `setKObject` method can do the same for the linked port.

  By keeping the checks in one place, the users of the object wouldn't need to verify the object's state themselves, and wouldn't miss a check like we saw here.

- How Mach reply ports are used
- How to [compile](https://gist.github.com/zhuowei/69c886423642cd77fd2c010f4d54b1c4) the macOS kernel to [add debug statements](https://github.com/zhuowei/darwin-xnu/tree/logging-specialreply) following [Scott Knight's](https://knight.sc/debugging/2020/02/18/building-xnu.html) and [kernelshaman's](https://kernelshaman.blogspot.com/2020/09/building-xnu-for-macos-catalina-1015x.html) guides
- CVE-2020-27932 UNallocates the THREAD special reply port. OMG, UnthreadedJB was [#not](https://www.theiphonewiki.com/wiki/Unthredera1n) [#fakr](https://twitter.com/zhuowei/status/1337095121716830210)!