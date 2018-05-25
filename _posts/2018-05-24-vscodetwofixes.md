---
title: Fixing two small bugs in Visual Studio Code
categories: macos
permalink: /vscodetwofixes/
---

VSCode is my favorite editor, and I wanted to contribute back to this open source project that helped me so much. Thus, I learned to build and debug VSCode to triage and fix two bugs from their bug tracker.

## Introduction

Every year, I contribute to one Electron application to keep up with [fellow kids](http://i0.kym-cdn.com/photos/images/original/000/683/526/4b2.gif) and to learn trendy web technologies. Last year, I made [two](https://github.com/desktop/desktop/pull/1677) [patches](https://github.com/desktop/desktop/pull/1678) to the new GitHub Desktop, to learn about TypeScript and the organization of an Electron app. This year, I decided to look at to Visual Studio Code: it's rapidly becoming my favorite editor, as it's feature rich, yet never obtrusive like a full IDE, and I wanted a chance to make it even better. Once again, I fixed two interesting bugs, both in the Git extension component. Here are my pull requests:

- [#50252: Fix Git merge conflict resolution for "both added" files](https://github.com/Microsoft/vscode/pull/50252)
- [#50376: Fix `includeIf` support for Git on Windows](https://github.com/Microsoft/vscode/pull/50376)

## Finding good bugs

I started by looking through the [VSCode Bug tracker](https://github.com/Microsoft/vscode/issues?q=is%3Aopen+is%3Aissue+label%3Abug+milestone%3ABacklog) for simple bugs I could fix. 

The tracker tags all bugs with its type (bug or feature request) and milestone (the release where the bug is being worked on, or "backlog" if the bug isn't assigned.)

I began browsing the issue tracker for bugs suited to a first-time contributor. First, I filtered for bugs only: feature requests requires discussing the new feature's design and implementation with other VSCode developers, but bugfixes can often be worked on alone, reducing turnaround time. In addition, I filtered for bugs in the backlog only, avoiding issues that others are already working on. Furthermore, I looked for bugs I can easily reproduce. Finally, I ignored bugs caused by third party components, such as the many, many bugs about Unicode support in the third party terminal library, since that would also require coordinating with the upstream developers of the library.

I was able to find two bugs that looked simple for a beginner to triage. Both are in the Git extension, a fairly isolated component. While I wanted to chase a bug through multiple components to get a better sense of VSCode's structure, I did not have the time. Oh well, maybe later.

The bugs are:

- [#44106: Merge conflict warning when there are none](https://github.com/Microsoft/vscode/issues/44106)
- [#40354: Git integration does not correctly support `includeIf` directive](https://github.com/Microsoft/vscode/issues/40354)

Now that I identified where I could help, I need to know how I could help.

## Getting started

VSCode makes it very easy for new developers to contribute. Build instructions are fully [documented](https://github.com/Microsoft/vscode/wiki/How-to-Contribute) and automated, and debugging configurations are already setup (as a Visual Studio Code project, of course). This is why I chose this project for my annual Electron pilgrimage. (Other open source maintainers, take note.)

To build VSCode, I simply followed their guide. Like every JavaScript project, downloading dependencies took forever, but I encountered absolutely zero problems with the process.

To debug VSCode, I couldn't use VSCode's built-in Developer Console. It only inspects the main user interface, but I'm working on the Git extension, which runs in a separate Node process. Instead, the guide says to debug using the Attach to Extension Host command.

I looked for the Attach to Extension Host command in VSCode's command palette, expecting it to show up like the Debugging Console command. I couldn't find it. I only figured it out when I opened the VSCode source in VSCode itself: this isn't a command, but a build task in the source. I need to run it from another copy of VSCode, which would attach to the VSCode I want to debug.

After figuring out the extension host debugging, I was able to set breakpoints in the Git extension. Now, I just need to figure out where to put those breakpoints.

## The merge conflicts bug

I chose [the merge conflicts bug](https://github.com/Microsoft/vscode/issues/44106) because the reporter gave a nice reproduction script that creates a Git repo with the problematic merge conflict. After following the reporter's steps, I confirmed that the bug occurs: when I try to add the file after resolving all the merge conflicts, a message still pops up with the message "Are you sure you want to stage file.txt with merge conflicts?".

To find the code responsible for this incorrect message, I simply looked for this text in the codebase using `grep`.

```
grep -r "with merge conflicts" extensions
extensions/git/src/commands.ts:				? localize('confirm stage files with merge conflicts', "Are you sure you want to stage {0} files with merge conflicts?", unresolvedConflicts.length)
```

Ah. the message comes from the Git extension, in commands.ts. The [relevant code](https://github.com/Microsoft/vscode/blob/49ab54ef08be371f5f5005d159870cbd27de1302/extensions/git/src/commands.ts#L625) is shown below.

```
		const selection = resourceStates.filter(s => s instanceof Resource) as Resource[];
		const merge = selection.filter(s => s.resourceGroupType === ResourceGroupType.Merge);
		const bothModified = merge.filter(s => s.type === Status.BOTH_MODIFIED);
		const promises = bothModified.map(s => grep(s.resourceUri.fsPath, /^<{7}|^={7}|^>{7}/));
		const unresolvedBothModified = await Promise.all<boolean>(promises);
		const resolvedConflicts = bothModified.filter((s, i) => !unresolvedBothModified[i]);
		const unresolvedConflicts = [
			...merge.filter(s => s.type !== Status.BOTH_MODIFIED),
			...bothModified.filter((s, i) => unresolvedBothModified[i])
		];

		if (unresolvedConflicts.length > 0) {
			const message = unresolvedConflicts.length > 1
				? localize('confirm stage files with merge conflicts', "Are you sure you want to stage {0} files with merge conflicts?", unresolvedConflicts.length)
				: localize('confirm stage file with merge conflicts', "Are you sure you want to stage {0} with merge conflicts?", path.basename(unresolvedConflicts[0].resourceUri.fsPath));
```

To my surprise, the code that displays the dialog is right next to the logic. Nice breath of fresh air - I expected multiple layers of abstraction. In addition, the code is simple to understand: it collects the files with unresolved conflicts, and pops the dialog if there are any.

Conflicts are handled differently for files with status `BOTH_MODIFIED` and for everything else. For `BOTH_MODIFIED` files (i.e. modified by both sides), grep is used to detect all the files with conflict markers still remaining. These files are stored in unresolvedBothModified. For other types of files, VSCode always marks them as containing unresolved conflicts.

So what is my file's status? I put a breakpoint to read the contents of unresolvedConflicts. Turns out that the status is `Status.BOTH_ADDED`, since the file was added in both branches.

It seems that the author didn't account for this case: files added by both sides are also resolved using conflict markers, so the `BOTH_MODIFIED` logic should be run to detect fixed conflicts instead of always reporting these files as unresolved.

To fix this, I added a check for `Status.BOTH_ADDED`. The existing check for `BOTH_MODIFIED` was repeated twice, so I first refactored the check into an anonymous lambda to avoid future inconsistency if any more types needs to be added.

After building, closing, and reopening VSCode, the original reproduction case no longer triggers the bug.

I made [a pull request](https://github.com/Microsoft/vscode/pull/50252) with my fix, but I marked it as [WIP]: I did not have a chance to test this fix to make sure it's not breaking anything else.

To my surprise, VSCode has only rudimentary tests for the Git component - no extensive regression tests. In addition, there's no Continuous Integration server that builds and tests pull requests to catch regressions. Therefore, I have to patiently wait for instructions from VSCode developers on how I should test this change. Now I understand how automated regression tests saves time over the long run.

## The includeIf bug

I turned next to the [includeIf bug](https://github.com/Microsoft/vscode/issues/40354), which is also easy to reproduce (in theory).

[Git 2.13](https://blog.github.com/2017-05-10-git-2-13-has-been-released/) added an `includeIf` directive for the `.gitconfig`, which allows including a config file if the current repository is located below the specified directory. With this, one could, for example, automatically use a work email when committing in `~/Documents/work/`, and a personal email for `~/Documents/oss/`.

Unfortunately, this feature isn't well documented yet: in fact, the [highest ranking tutorial](https://www.motowilliams.com/conditional-includes-for-git-config) on Google is written by the person who reported this bug! After wrestling with my gitconfig, adding the trailing slash to make it recognize the path, I finally got includeIf to work on the command line Git: running `git config user.name` outside the repository shows that the user.name isn't set, but running the same command inside the specified directory shows the correct specified name.

So I tried committing a file in VS Code in the specified repo... and it worked fine! I can't reproduce it on macOS at all.

The original reporter used Windows. Is this Windows specific?

I spent hours setting up a Windows computer to match the reporter's setup. Again, I got Git for Windows to only set a username in a specific repo. I tried committing to that repo and... yep, VSCode didn't pick up the username, as the bug stated.

Now that I reproduced the issue, I need to figure out exactly what differed between the Git command I'm manually running, which works, and the Git commands that VSCode is running, which doesn't.

My usual tactic is to wrap the executable to dump out inputs. I created a batch file that logs the current working directory and any arguments passed to `git`:

```
@echo off
echo %* in %cd% >>"C:\Users\zhuowei\mygitlog%1.txt"
git config --list --show-origin >>"C:\Users\zhuowei\mygitlog%1.txt"
"C:\Program Files\Git\cmd\git.exe" %*
```

And set `git.path` in VSCode to use this batch file. I tried to commit from VSCode, which failed to pick up the includeIf config. Then I ran the wrapper from the command line, and it did pick up the includeIf. I then checked the log:

In VSCode:

```
config --get-all user.name in c:\Users\zhuowei\Documents\repos\includeIf 
```

Outside:

```
config --get-all user.name in C:\Users\zhuowei\Documents\repos\includeIf
```

The arguments were identical, but the current working directories differ by one single character: VSCode uses a lowercase, not an uppercase drive letter. Could something this simple cause this bug?

I tested my hypothesis by switching to `includeIf`'s case insensitive compare mode: now VSCode can pick up the includeIf just fine. From this, I can conclude that the case of the drive letter is causing the bug.

It turns out that Node.js always lowercases the drive letter in any returned paths, so my fix must explicitly uppercase the drive letter when launching Git. First, I had to find where Git is launched: I searched for `child_process`, Node's built-in module for launching external programs. This revealed that VSCode launches Git through two methods, [Git.exec](https://github.com/Microsoft/vscode/blob/49ab54ef08be371f5f5005d159870cbd27de1302/extensions/git/src/git.ts#L422) and [Git.stream](https://github.com/Microsoft/vscode/blob/49ab54ef08be371f5f5005d159870cbd27de1302/extensions/git/src/git.ts#L427), both of which takes the desired current working directory. All I have to do was to uppercase the drive letter in these methods.

Searching VSCode's codebase for "drive letter uppercase" brought me to an [existing piece of code](https://github.com/Microsoft/vscode/blob/49ab54ef08be371f5f5005d159870cbd27de1302/src/vs/workbench/parts/terminal/node/terminalEnvironment.ts#L152) uppercasing the drive letter to fix issue [#9448](https://github.com/Microsoft/vscode/issues/9448):

```
function _sanitizeCwd(cwd: string): string {
	// Make the drive letter uppercase on Windows (see #9448)
	if (platform.platform === platform.Platform.Windows && cwd && cwd[1] === ':') {
		return cwd[0].toUpperCase() + cwd.substr(1);
	}
	return cwd;
}
```

I borrowed this code and passed Git's working directory through this function in Git.exec and Git.stream.

After applying this change, VSCode loads the Git config from the includeIf directive, and commits just fine. Thus, I submitted the fix as my [second pull request](https://github.com/Microsoft/vscode/pull/50376) on the VSCode project.

## What I learned

- Building and running VS Code from source
- that automated and well documented build processes attracts new contributors to an open source project
- finding the origin of a bug in an unfamiliar codebase by grepping for user visible messages
- that regression tests are important for giving contributors confidence that their fix hasn't broken anything else
- debugging mysterious problems by narrowing down the differences between execution environments.
- using Visual Studio Code's Node debugger (to debug itself)