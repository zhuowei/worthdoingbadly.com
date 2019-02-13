#!/bin/bash
set -e

function stopgdm() {
	echo "Stopping GDM"
	systemctl stop gdm
	echo "Stopped."
	sleep 0.5
	echo "Stopping gdm-wayland-session"
	killall gdm-wayland-session
	echo "Stopped"
	sleep 0.5
}

function stopvt() {
	echo "Stopping virtual terminals"
	for i in /sys/class/vtconsole/*/bind
	do
		echo 0 >$i
	done
}

function stopsound() {
	echo "Stopping Intel HDA sound"
	for i in /sys/module/snd_hda_intel/drivers/pci\:snd_hda_intel/*/remove
	do
		echo 1 >$i
	done
}

function removemod() {
	echo "Waiting for everything to settle down"
	sleep 0.5
	echo "Removing modules"
	rmmod snd_hda_intel
	rmmod i915
}
function probepci() {
	devicestring="$(lspci -nn | grep "VGA compatible")"
	pciid="$(echo "$devicestring" | grep -o "8086:....")"
	pciaddr="$(echo "$devicestring" | cut -f 1 -d " ")"
	modprobe vfio-pci ids=$pciid
	echo "Probed: $devicestring"
	echo "run qemu with -device vfio-pci,host=$pciaddr"
}

stopgdm
stopvt
stopsound
removemod
probepci
