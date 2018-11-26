---
title: Learn how iOS devices sync over USB by enabling usbmuxd's debug logs
categories: ios, macos, usbmuxd
permalink: /usbmuxdebug/
---
To learn how iTunes and Xcode sync with iPhones, I enabled a hidden option in macOS's `usbmuxd` daemon that logs how applications communicate with iOS devices over USB.

# What the config option does

It causes `usbmuxd` to log which processes are accessing connected iOS devices.

[`usbmuxd`](https://www.theiphonewiki.com/wiki/Usbmux) is the system daemon on macOS that handles communications to iOS devices over USB (or Wi-Fi sync, if you have that enabled).

You can view the logs by opening the Console app and filtering for "usbmuxd":

![output of the log when opening Xcode with an iOS device attached](/assets/blog/usbmuxdebug/usbmuxd_log_cropped.png)

In the above log, I opened Xcode's Devices window, which triggered Xcode to connect to Lockdownd on my iPad at port 62078, likely to start some sort of developer service. Xcode then connected to the newly launched service through port 59426.

# How to enable it

You need a `/Library/Preferences/com.apple.usbmuxd.plist` config file.

Download [this configuration file for USBMuxd](/assets/usbmuxddebug/com.apple.usbmuxd.plist):

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>DebugLevel</key>
	<integer>7</integer>
</dict>
</plist>
```

and copy it to your `/Library/Preferences/` directory:

```
sudo cp ~/Downloads/com.apple.usbmuxd.plist /Library/Preferences
```

`usbmuxd` should pick up the configuration file and print a message to the console:

```
usbmuxd	notice    log filter changed from 5 to 7
```

# How I found it

After I loaded usbmuxd into IDA Free, I noticed that it was calling [`asl_set_filter`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/asl_set_filter.3.html) to filter out debug logs:

![function calling asl_set_filter](/assets/blog/usbmuxdebug/usbmuxd_set_filter.png)

This function is called by two functions.

![xrefs of asl_set_filter](/assets/blog/usbmuxdebug/usbmuxd_xrefs.png)

The `_start` function handles the command line parameter to enable verbose logging.

The other function, `sub_10000236E`, processes `usbmuxd`'s config file:

![usbmuxd's config path](/assets/blog/usbmuxdebug/usbmuxd_configpath.png)

There's quite a few configuration options that usbmuxd supports. The one that sounded promising was `DebugLevel`:

![usbmuxd settings' names](/assets/blog/usbmuxdebug/usbmuxd_settings_names.png)

I created the `/Library/Preferences/com.apple.usbmuxd.plist` file and increased the debug level until debug messages started appearing.

# Additional resources

Here's some sources I consulted during this research that you might find useful:

- [Libimobiledevice](https://github.com/libimobiledevice/libimobiledevice) - open source tools to communicate with iOS devices over USB
- [Usbmuxd protocol documentation](https://www.theiphonewiki.com/wiki/Usbmux) on iPhone Wiki - documents both the usbmuxd protocol and the Lockdownd protocol (which controls USB services on the device)
- [Discovering the iOS Instruments Server](https://github.com/troybowman/dtxmsg/blob/master/slides.pdf) - Troy Bowman's presentation on how Xcode communicates with iOS devices

# What I learned

- Where system daemons on macOS store their preferences
- Logging levels in the Apple System Logger framework
- I _can_ write a short article