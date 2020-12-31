---
title: Disable Same Origin Policy in iOS WKWebView with private API
categories: ios, webkit, safari
permalink: /disablesameorigin/
---

Safari's Web Inspector has an option (Develop -> Disable Cross Origin Restrictions) to disable the same-origin policy for debugging. This allows, for example, the `fetch` API to load any page, not limited to the same domain or CORS-enabled domains.

[Recently](https://twitter.com/zhuowei/status/1300657149635432450), I had to enable this mode on an iOS WKWebView from code, without attaching the Web Inspector. My solution is probably not very useful for you, since it uses private API, but might be helpful for enterprise-signed apps or debugging.

Here's how.

## The code

The code can be found in this [GitHub Gist](https://gist.github.com/zhuowei/0b7074b3803d72609c028ab5723d9c28):

```objective_cpp
// Allows disabling Same-Origin Policy on iOS WKWebView.
// Tested on iOS 12.4.
// Uses private API; obviously can't be used on app store.

@import WebKit;
@import ObjectiveC;

void WKPreferencesSetWebSecurityEnabled(id, bool);

@interface WDBFakeWebKitPointer: NSObject
@property (nonatomic) void* _apiObject;
@end
@implementation WDBFakeWebKitPointer
@end

void WDBSetWebSecurityEnabled(WKPreferences* prefs, bool enabled) {
    Ivar ivar = class_getInstanceVariable([WKPreferences class], "_preferences");
    void* realPreferences = (void*)(((uintptr_t)prefs) + ivar_getOffset(ivar));
    WDBFakeWebKitPointer* fake = [WDBFakeWebKitPointer new];
    fake._apiObject = realPreferences;
    WKPreferencesSetWebSecurityEnabled(fake, enabled);
}
```

To use, just call:

`WDBSetWebSecurityEnabled(prefs, true);`

when constructing the WKWebView.

## How it works

`WKPreferences` has a `_setWebSecurityEnabled` method... on [macOS only](https://github.com/WebKit/WebKit/blob/b7e84a4224b3934868bc08f5c89b583355a6c87a/Source/WebKit/UIProcess/API/Cocoa/WKPreferences.mm#L1034).

The C++ method that it calls, `WebKit::WebPreferences::setWebSecurityEnabled`, does not seem to be exported by WebKit, so we can't just extract the C++ [WebKit::WebPreferences](https://github.com/WebKit/WebKit/blob/b7e84a4224b3934868bc08f5c89b583355a6c87a/Source/WebKit/UIProcess/API/Cocoa/WKPreferencesInternal.h#L41) object and call it directly.

However, iOS does include the `WKPreferencesSetWebSecurityEnabled` [C API](https://github.com/WebKit/WebKit/blob/b7e84a4224b3934868bc08f5c89b583355a6c87a/Source/WebKit/UIProcess/API/C/WKPreferences.cpp#L689) which can set the variable, but it takes a `WKPreferencesRef` and not a `WKPreferences*`.

So, to set the variable, we need to:
- Extract the C++ `WebPreferences` from the Objective-C `WKPreferences`
- Wrap the `WebPreferences` in a `WKPreferencesRef` for the C API

## Extracting the C++ `WebPreferences`

It turns out [ObjectStorage](https://github.com/WebKit/WebKit/blob/b7e84a4224b3934868bc08f5c89b583355a6c87a/Source/WebKit/Shared/Cocoa/WKObject.h#L35) is basically just

```cpp
struct ObjectStorage<TypeName> {
    TypeName data;
};
```

i.e. a wrapper around the containing type with the object as its only member.

so basically our class becomes equivalent to:

```objective_cpp
@interface WKPreferences {
    WebKit::WebPreferences _preferences;
};
```

Usually, when we want to access a private instance variable, we can use KVO's [`valueForKey:`](https://developer.apple.com/documentation/objectivec/nsobject/1412591-valueforkey?language=objc) method.

However, that method assumes that the instance variable contains a pointer to an Objective-C object; our ivar is not a pointer but an inline-allocated C++ object.

Instead, we use `class_getInstanceVariable` to get the instance variable, and perform pointer arithmetic with the offset from `ivar_getOffset` to get a pointer to `_preferences`.

## Wrapping the `WebPreferences` into `WKPreferencesRef`

To find out what a `WKPreferencesRef` is, I just passed in a random object into the method and was greeted with "unrecognized selector _apiObject".

I made an Objective-C class with a property named `_apiObject`, stored the pointer to `WebPreferences` into the property, and it just worked.

## What I learned

- Yet another way to access instance variables
- WebKit's C API
- Most options in the Safari Develop menu can actually be set from code