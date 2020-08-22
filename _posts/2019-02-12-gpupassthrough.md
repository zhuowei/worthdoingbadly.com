---
title: Use GPU passthrough with Intel integrated graphics to accelerate QEMU on Fedora
categories: qemu, linux, fedora
permalink: /gpupassthrough/
---

Here's how I setup GPU passthrough with an Intel Broadwell GPU on Fedora 29. I wrote a script to unload the Intel driver while avoiding the "Module i915 is in use" error, and explored what QEMU GPU passthrough options actually do.

# Introduction

GPU passthrough allows a virtual machine to use the full power of the host's GPU to speed up graphical performance.

I tried GPU passthrough with the integrated graphics of my Intel Broadwell CPU. With passthrough enabled, I was able to boot a Linux VM in QEMU with full GPU acceleration.

I tested this on Fedora Workstation 29's Live image, booted from a USB drive.

# Boot argument to turn on the IOMMU

To [enable PCI passthrough](https://www.linux-kvm.org/page/How_to_assign_devices_with_VT-d_in_KVM
), I had to turn on the IOMMU at boot.

- Hit `E` when the boot screen appears to edit boot arguments
- Add `intel_iommu=on` to the end of the `linuxefi` line
- Press Ctrl-X to boot with the new argument.

# Disabling the GPU on the host

Usually, the GPU is disabled at boot up, either with the `nomodeset` boot argument or with a modprobe blacklist.

However, I'm using a Live USB, and I needed the screen to configure Wi-Fi and enable SSH. So I keep the GPU on during boot, and only disable it just before starting QEMU.

This was harder than I thought: just running `rmmod i915` gives the error:

```
$ sudo rmmod i915
rmmod: ERROR: Module i915 is in use
```

That's because the GPU is still active.

I had to:

1. [Login through SSH](#appendix-1-setting-up-ssh-on-fedora-workstation-live), since these commands will turn off the screen.
2. Disable the graphical environment by stopping GDM
3. [Disable the kernel's text console](https://bugs.freedesktop.org/show_bug.cgi?id=29828)
4. [Disable the Intel HDA sound card](https://bugs.freedesktop.org/show_bug.cgi?id=70336), as it communicates with the GPU to support sound over HDMI

After disabling everything that uses the GPU, `rmmod i915` works, and the screen turns dark.

To make the graphic card available for passthrough, I probed [vfio-pci](https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF#With_vfio-pci_loaded_as_a_module). Now the GPU is ready for passthrough.

I [made a script](/assets/blog/gpupassthrough/prepareIntelGPUPassthrough.sh) that automates these steps: you can just run, in an SSH session,

```
wget https://worthdoingbadly.com/assets/blog/gpupassthrough/prepareIntelGPUPassthrough.sh
sudo bash prepareIntelGPUPassthrough.sh
```

to unload the i915 driver and enable vfio-pci.

# Enabling passthrough in QEMU

To test if the Intel GPU works in passthrough, I needed to run an operating system that supported this GPU. Fedora Workstation 29 obviously supports it, since I'm using it as my host OS, so I decided to use it as the guest as well.

I started QEMU with the following arguments. Some are familiar arguments, some are new.

```
sudo qemu-system-x86_64 -machine q35 -m 2G -accel kvm -cpu host \
-device vfio-pci,host=00:02.0 -nographic -vga none \
-object input-linux,id=kbd,evdev=/dev/input/by-path/platform-i8042-serio-0-event-kbd \
-cdrom Fedora-Workstation-Live-x86_64-29-1.2.iso
```

Here's what each of the new unfamiliar commands do:

- `-machine q35`

  Tells QEMU to emulate a Intel Q35 chipset, which supports GPU passthrough.

  _Edit_: [Thomas A on Twitter](https://twitter.com/CT_the_man_doll/status/1095562088687124486) mentioned that QEMU's default 440FX chipset should also support GPU passthrough. However, that failed on my machine; it might only work for discrete GPUs?

- `-device vfio-pci,host=00:02.0`

  [Adds the GPU](https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF#Plain_QEMU_without_libvirt) to the virtual machine.

  The address is the first part of the output of `lspci | grep "VGA Compatible"`:

  ```
  00:02.0 VGA compatible controller [0300]: Intel Corporation HD Graphics 5500 [8086:1616] (rev 09)
  ```

- `-nographic`

  Allows QEMU to start in an SSH terminal. This disables the usual QEMU window, and also enables the virtual machine's serial port for viewing boot progress.

  To exit QEMU in this mode:

  - Press Ctrl-A
  - Then C to switch to the QEMU console
  - Type "q"
  - Then press Enter.

- `-object input-linux,id=kbd,evdev=/dev/input/by-path/platform-i8042-serio-0-event-kbd`

  Tells QEMU to [read virtual keyboard input directly](https://www.kraxel.org/blog/2016/04/linux-evdev-input-support-in-qemu-2-6/) from my real keyboard. This is needed because QEMU is running in a terminal, and can't capture keyboard input normally.

- `-vga none`

  Turns off QEMU's built-in graphics emulation so Linux would use the passed through GPU.

# Conclusion

GPU passthrough with Intel integrated graphics is useful for speeding up virtual machines, and it's easy to setup.

If you're interested in learning more, the Arch Linux Wiki has [a good tutorial](https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF#Plain_QEMU_without_libvirt) on configuring GPU passthrough, which I consulted a lot while writing this post.

# What I learned

- GPU passthrough in QEMU
- Removing the i915 module at runtime
- `input-linux` support in QEMU
- It's strange to see a virtual machine taking over my entire screen

# Appendix 1: setting up SSH on Fedora Workstation Live

To enable SSH access on Fedora Workstation 29 Live:

- Go to Settings->Details->Users
- Change the password of the live user
- Open a terminal
- Run `sudo systemctl start sshd` to start the SSH server
- Now you can access the machine with `ssh liveuser@(machine ip)`
