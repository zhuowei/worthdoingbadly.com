---
title: Rendering SwiftUI views to HTML
categories: swift, swiftui, ios
permalink: /swiftui-html/
---

I built a [proof-of-concept tool](https://github.com/zhuowei/marina) to render SwiftUI to HTML. While I'm not intending to turn it into a full UI framework, I still learned plenty along the way: I learned how to use Swift's generics, why declarative UI frmeworks use a shadow graph, and how Swift's design is an evolution of C++'s philosophy.

![screenshot of the Landmarks sample from Apple's SwiftUI, rendered to HTML](/assets/blog/swiftui-html/swiftui_renderingLandmarksSample.png)

# What's SwiftUI?

[SwiftUI](https://developer.apple.com/tutorials/swiftui/tutorials) is Apple's new UI framework, announced at WWDC 2019.

It's a declarative framework - you just create some structs telling the framework what to render, and the framework handles layout and events. When the underlying state changes, the platform intelligently re-renders your views.

It's similar in concept to React:

- Both SwiftUI and React allows developers to create UIs using functional programming techniques, without worrying about managing state
- Both SwiftUI and React extends their host language to make creating UIs easier:
   - React adds JSX to JavaScript
   - SwiftUI adds two new syntax features to Swift: [function builders](https://github.com/apple/swift-evolution/pull/1046) and [property decorators](https://github.com/apple/swift-evolution/blob/master/proposals/0258-property-delegates.md).

# What did I build?

I wanted to learn how SwiftUI uses the new Swift syntax, so I decided to create a [SwiftUI to HTML converter](https://github.com/zhuowei/marina).

My goals were:

- Understand how SwiftUI uses its new syntax features
- Understand how SwiftUI leverages the Swift type system
- Render the [SwiftUI tutorial sample app](https://developer.apple.com/tutorials/swiftui/handling-user-input)'s first page to HTML
- before WWDC ends ;)

I intentionally avoided many features to make that deadline: my library is: 

- **Not intended to be a full SwiftUI compatible framework** - for that, look at [@MaxDesiatov's Tokamak](https://twitter.com/maxdesiatov/status/1135627087790911489).
- Not intended as an HTML template library - for that, use [@dokun1's Vaux](https://github.com/dokun1/Vaux).
- Not implementing the styling features in SwiftUI
- Not supporting data binding or interactivity - SwiftUI uses a complex render graph to keep track of state for each UI element; there's no way I could reimplement that in a week.

# Reimplementing SwiftUI's public API

The first task was reimplementing SwiftUI's structs so programs using SwiftUI would compile.

This was mostly straightforward: I just looked at the [documentation](https://developer.apple.com/documentation/swiftui/view) and the API details in Xcode, then recreated each struct in my own file.

For example, the Text struct is just:

```
struct Text : View, MarinaTextAccess {
    var content:String
    var body:Never {
        fatalError("Text has no body")
    }
    init<S>(_ content: S) where S : StringProtocol {
        self.content = String(content)
    }
    init(verbatim content: String) {
        self.content = String(content)
    }
    func getContent() -> Any {
        return content
    }
    func color(_ color: Color?) -> Text {
        return self
    }
    func font(_ font: MarinaFont) -> Text {
        return self
    }
}
```

That's enough to get Apple's Landmarks demo to compile.

# Compile errors

The harder part was diagnosing compile errors.

Function builders are new to Swift, and they don't handle compiler errors well: I ran into many nonsense errors: for example, `'inout Bool' is not convertible to 'Bool'`.

To work around this, I would comment out parts of the code until the error becomes sensible again.

In fact, I still can't get `buildIf` to work in my implementation: I had to [patch Landmarks](https://github.com/zhuowei/marina-sample-landmarks/commit/2c493a166cc36c0f1ff575ca8b9df499408e80cc#diff-19174e087c34a01189d0450674a76d7fR19) to use an if/else pair instead.

The Swift developers are working on improving compiler messages when function builders are used, so I'm sure building DSLs in the future would be much easier.

# Emitting HTML: wrapping my head around generics

Once the view hierarchy is described by the structs, I then need to emit HTML from those structs.

This was the most difficult part, since SwiftUI depends heavily on generics. I've been writing Swift for one and a half years, but this is the first time I've ever written a pair of angled brackets.

In Java, I could access each node's value by checking its type with `instanceof`, then casting.

```
if (view instanceof Text) {
    emit(((Text)view).getText());
}
```

In Swift, this doesn't work, since Swift's generics have different semantics than Java's:

```
test.swift:7:18: error: protocol 'View' can only be used as a generic constraint because it has Self or associated type requirements
if let a = b as? View {
```

I tried many approaches:

- generic functions with type constraints: doesn't work because no dynamic dispatching
- adding a function to the View protocol and overriding it in each inheriting struct: again, structs, unlike classes, doesn't have dynamic dispatching, so overrides won't work
- using Mirror to access values via reflection: doesn't work on computed properties, like `body`.

Finally, after reading many articles about type erasure, I figured out the secret sauce:

- Have each of my structs inherit from a unique access protocol.
  - for example, the `Text` struct above implements `MarinaTextAccess`.
- the protocol would include a `getContent() -> Any` method
- In my render method, I simply:
  - [check if the input implements the access protocol](https://github.com/zhuowei/marina/blob/master/marina_html.swift#L46). This is possible because the access protocol has no associated types.
  - if it matches, cast it to the access protocol, and call getContent.
  - getContent then returns the content of the view as a type-erased `Any` value.

This avoids problems with associated types. However, it does mean that all my views are passed in as Any: I would love to learn what's the proper typesafe way to handle this.

Using this method, I [traverse](https://github.com/zhuowei/marina/blob/master/marina_html.swift#L35) down the SwiftUI view hierarchy, emitting HTML for each node.

# What I learned: design constraints

I've always wondered why every declarative UI framework creates a shadow representation of the input elements:

- for React, the shadow DOM
- for Flutter, the Render Tree
- for SwiftUI, the Attribute Graph.

After implementing the SwiftUI to HTML translator, I finally understood: the shadow graph is where the UI stores the state and dispatches events - so that the user code doesn't need to worry about these non-functional details.

I realized that my library, without a shadow graph, would never be able to handle events such as taps.

It's interesting that three frameworks, implemented by different developers in different languages, came to the same solution because the problem constrains the solution space.

# What I learned: Application vs Library code

One unexpected result of this exercise: I now better appreciate how Swift and Go compare to each other. Sure, I've read the Swift vs Go posts [that](https://www.quora.com/How-does-Apples-new-programming-language-Swift-compare-against-Google-Go) [are](https://www.quora.com/How-does-Apples-new-programming-language-Swift-compare-against-Google-Go/answer/John-Forde-8
) [a dime](https://opencredo.com/blogs/java-go-back/
) a dozen: however, it took me until this to really understand: Swift and Go are evolutions of two different approaches to programming language design.

Before writing this SwiftUI to HTML converter, I wrote exactly 0 pairs of generic brackets in Swift.

As an iOS app developer, I just used Swift as "Objective-C without semicolons" - I didn't have to interact with the type system at all. Thus, I was absolutely in over my head when I tried implementing a library, with its heavy dependence on generics.

In Swift, the type system improves the experience of the library user, at the cost of complexity for the library implementer. This creates a gap, with some app developers unable to understand libraries, because they simply never encountered the advanced features, such as generics, in day-to-day application code.

This reminds me of C++ templates. The C++ Standard Template Library uses templates to make C++ easy to use for developers, with containers and smart pointers. However, I can't understand a single line of STL code. (I tried.)

From this, I realized that most programming language designs takes one of two approaches:

- Give library developers massive power to build abstractions that make app code very simple
    - but app developers don't gain the skill required to peek behind the curtain and understand/write libraries

or:

- Design a simple language for both libraries and applications
    - making application code more verbose, but allowing anyone to understand libraries

C++, of course, belongs to the first camp, while Java takes the second approach:

Java code is sometimes ridiculed for its verbosity, but I can open any file in - say - [Android's source](https://github.com/aosp-mirror/platform_frameworks_base/blob/master/core/java/android/widget/TextView.java) and immediately understand it, without learning new programming techniques specific to library development.

What I find most interesting is that Swift and Go represents a refinement of each approach:

- Swift, in the first camp, uses its type system so libraries can provide better compile-type diagnostics, making applications even easier to write.
- Go, in the second camp, added thoughtful language features such as built-in concurrency, reducing verbosity while keeping the language understandable

I really like that both Swift and Go took advantage of the upsides of their predecessor's approach, while mitigating the downsides. It makes me better appreciate the thoughtfulness in their design.

# What I learned: summary

- Swift function builders and property decorators
- Swift generics
- Swift's design philosophy

# How you can help

- Are there any suggestions on how I can improve the rendering code to be more type safe? Let me know [@zhuowei](https://twitter.com/zhuowei).

# Other links you might enjoy

- [Swift Evolution pull request for function builders](https://github.com/apple/swift-evolution/pull/1046)
- [Swift pull request with function builder samples](https://github.com/apple/swift/pull/25221)
- [Swift Evolution pull request for property delegates](https://github.com/apple/swift-evolution/blob/master/proposals/0258-property-delegates.md)
- [SwiftRocks's article on SwiftUI's tricks](https://swiftrocks.com/inside-swiftui-compiler-magic.html)
- [kateinoigakukun's article on how SwiftUI uses ABI stability for its magic](https://kateinoigakukun.hatenablog.com/entry/2019/06/09/081831)