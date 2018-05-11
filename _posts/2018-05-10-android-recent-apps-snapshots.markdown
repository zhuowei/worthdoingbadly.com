---
title: Accessing screenshots from Android's Recent Apps screen
categories: android
permalink: /androidrecents/
---

I learned to call Android's hidden ActivityManager APIs from the ADB command line to access the screenshots of Recent Apps, so I can build [a custom app switcher](https://github.com/zhuowei/PillAppSwitcher).

## Introduction

Google presented Android P's [new navigation bar](https://www.androidpolice.com/2018/05/08/gesture-navigation-officially-announced-android-p/) at Google I/O, and I was impressed by the animations and the integration with the homescreen. I wanted to try replicating the navigation UI to see how it's made. I started by making a basic horizontal carousel showing my recent apps:

![my task switcher prototype, after one day's work]({{ "/assets/blog/androidrecents/screenshot_myapp.jpg" | absolute_url }})

Figure 1: my task switcher prototype, after one day's work

![Android's current task switcher, for reference]({{ "/assets/blog/androidrecents/screenshot_stock.jpg" | absolute_url }})

Figure 2: Android's current task switcher, for reference

To make this interface, I needed the phone's list of tasks and screenshots of each task. This is much more challenging than it sounds: I had to learn how Android apps talk to the system at the lowest levels.

## Why this is hard

Getting the list of current apps used to be a simple [ActivityManager.getRecentTasks](https://developer.android.com/reference/android/app/ActivityManager.html#getRecentTasks(int,%20int)) call. However, apps started abusing it, so in Android 5.0, this API was hidden behind a new permission, `android.permission.GET_DETAILED_TASKS`. This permission is only granted to system applications, so my application can't get it. However, the ADB shell [can access it](https://doridori.github.io/Android-Security-welcome-to-shell/).

For a prototype, I can simply tether my phone to a computer, and ask the ADB shell to send the tasks to my app. Thus, I need to make an ADB command line app that can:

- access the current list of running apps
- get the screenshot of each app
- export this data to a normal Android app

## Running from adb

Normally, Android applications are started from Android's graphical user interface. However, in the adb shell, there's only a command line, and the entry point is good old `public static void main`. No `Context`, no `Activity` - how do I run any code that talks to Android?

I know a command line tool on Android is possible, since the [Substratum](https://www.androidpolice.com/2017/09/11/andromeda-brings-substratum-theming-unrooted-android-8-0-oreo-devices/) theme manager also uses a command line tool started from ADB. How did they do it?

I looked at the existing utilities on Android: one commonly used command is `am`, used to start activities from the command line when debugging. The executable, `/system/bin/am`, is actually a [simple shell script](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/cmds/am/am):
```
base=/system
export CLASSPATH=$base/framework/am.jar
exec app_process $base/bin com.android.commands.am.Am "$@"
```

which sets a CLASSPATH pointing to the Java code of the tool, then runs `app_process` with the working directory and the main class of the tool. I can do the same by setting the CLASSPATH to my APK and running my main class.

To autodetect the APK path, I used the `pm path` command:

```
$ pm path net.zhuoweizhang.pill
package:/data/app/net.zhuoweizhang.pill-1/base.apk
```

Using a `sed` command, I removed the leading `package:` from the path before storing it in `CLASSPATH`, giving a final command line of

```
CLASSPATH="$(pm path net.zhuoweizhang.pill|sed -e s/^package//)" app_process /sdcard net.zhuoweizhang.pill.PillServer
```

Oddly, Instant Run causes `pm path` to show multiple packages: I had to disable Instant Run to make this work.

## Talking to the Android system

Now that I'm running Java code from the ADB command line, how do I talk to the Android system? There's no `Context`, so I can't just run `Context.getSystemService(ACTIVITY_MANAGER)` to get an ActivityManager to get the list of tasks. 

I once again turn to the `am` utility. The [Java code](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/cmds/am/src/com/android/commands/am/Am.java) for `am` shows how it accesses the ActivityManager:

{% highlight java %}
private IActivityManager mAm;
mAm = ActivityManager.getService();
{% endhighlight %}

Note that it accesses an IActivityManager, not the regular ActivityManager - which needs a Context<sup>[note 1](#note-1-context)</sup>. As it turns out, ActivityManager is just a wrapper around IActivityManager: all ActivityManager methods eventually call the equivalent IActivityManager method. 

Therefore, if I use IActivityManager, I can talk to Android from a command line app, without a `Context`!

The list of IActivityManager's exported methods is, of course, defined in [its AIDL file](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/core/java/android/app/IActivityManager.aidl), just like a regular Android Service.

## Getting the recent apps images

Let's see how Android's existing Recent Apps screen gets its images. I know - from looking at the Android log - that the Recent Apps screen is implemented in SystemUI:

```
$ logcat|grep Recent
I ActivityManager: START u0 {flg=0x10804000 cmp=com.android.systemui/.recents.RecentsActivity} from uid 10027
```

Let's take a look at [RecentsActivity's source](https://github.com/aosp-mirror/platform_frameworks_base/tree/android-cts-8.1_r4/packages/SystemUI/src/com/android/systemui/recents): `TaskViewThumbnail` [sounds relevant](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/packages/SystemUI/src/com/android/systemui/recents/views/TaskViewThumbnail.java). It sets the app screenshot when it receives a `TaskSnapshotChangedEvent`. Looking for this class brings us to `RecentsImpl`, which sends the `TaskSnapshotChangedEvent` from [the `onTaskSnapshotChanged` method](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/packages/SystemUI/src/com/android/systemui/recents/RecentsImpl.java#L203) of a `TaskStackListener`. This listener is registered on the `SystemServicesProxy` class. Looking through [this class](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/packages/SystemUI/src/com/android/systemui/recents/misc/SystemServicesProxy.java), I found many relevant  methods.

[For getting tasks](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/packages/SystemUI/src/com/android/systemui/recents/misc/SystemServicesProxy.java#L393):

{% highlight java %}
    public List<ActivityManager.RecentTaskInfo> getRecentTasks(int numLatestTasks, int userId,
            boolean includeFrontMostExcludedTask, ArraySet<Integer> quietProfileIds) {
        if (mAm == null) return null;
        // snip
        List<ActivityManager.RecentTaskInfo> tasks = null;
        try {
            tasks = mAm.getRecentTasksForUser(numTasksToQuery, flags, userId);
        } catch (Exception e) {
            Log.e(TAG, "Failed to get recent tasks", e);
        }
{% endhighlight %}

Sounds like getRecentTasksForUser lets us find the recent apps. This is called on the `ActivityManager`, not the `IActivityManager`, so let's [find the method](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/core/java/android/app/ActivityManager.java#L1846) in ActivityManager:

{% highlight java %}

    public List<RecentTaskInfo> getRecentTasksForUser(int maxNum, int flags, int userId)
            throws SecurityException {
        try {
            return getService().getRecentTasks(maxNum,
                    flags, userId).getList();
        } catch (RemoteException e) {
            throw e.rethrowFromSystemServer();
        }
    }
{% endhighlight %}

The IActivityManager equivalent is just `getRecentTasks`. I can call it like this:

{% highlight java %}
List<ActivityManager.RecentTaskInfo> tasks = iam.getRecentTasks(25, 0, 0)
{% endhighlight %}


to get the last 25 tasks for user 0 (the main user).

[What about thumbnails](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/packages/SystemUI/src/com/android/systemui/recents/misc/SystemServicesProxy.java#L741)?

{% highlight java %}
    /**
     * Returns a task thumbnail from the activity manager
     */
    public @NonNull ThumbnailData getThumbnail(int taskId, boolean reducedResolution) {
        if (mAm == null) {
            return new ThumbnailData();
        }

        final ThumbnailData thumbnailData;
        if (ActivityManager.ENABLE_TASK_SNAPSHOTS) {
            ActivityManager.TaskSnapshot snapshot = null;
            try {
                snapshot = ActivityManager.getService().getTaskSnapshot(taskId, reducedResolution);
            } catch (RemoteException e) {
                Log.w(TAG, "Failed to retrieve snapshot", e);
            }
            if (snapshot != null) {
                thumbnailData = ThumbnailData.createFromTaskSnapshot(snapshot);
            } else {
                return new ThumbnailData();
            }
{% endhighlight %}

Looks like thumbnails are accessed through the `getTaskSnapshot` method on IActivityManager. Let's look at how [ThumbnailData](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-cts-8.1_r4/packages/SystemUI/src/com/android/systemui/recents/model/ThumbnailData.java#L35) processes the returned snapshot:

{% highlight java %}
    public static ThumbnailData createFromTaskSnapshot(TaskSnapshot snapshot) {
        ThumbnailData out = new ThumbnailData();
        out.thumbnail = Bitmap.createHardwareBitmap(snapshot.getSnapshot());
{% endhighlight %}

Following this method's example, I can turn the TaskSnapshot into a Bitmap easily. To get a JPEG of an app's screenshot, all I have to do is take the `persistentId` from the task information, and run:
{% highlight java %}
    ActivityManager.TaskSnapshot thumbnail = iam.getTaskSnapshot(id, false);
    GraphicsBuffer graphicBuffer = thumbnail.getSnapshot();
    Bitmap bmp = Bitmap.createHardwareBitmap(graphicBuffer);
    bmp.compress(Bitmap.CompressFormat.JPEG, 80, os);
{% endhighlight %}

Just what is a GraphicsBuffer? [Android Developer explains](https://source.android.com/devices/tech/perf/task-snapshots) that it's a graphic that can be shared across processes without copying.

Now I have all the data I need, but how do I send it to the main application, running as a different UID?

## Sending the information across

The usual methods of inter-process communication on Android is, of course, through Intents (Activity launch, Broadcast Intent) or through a Service. Unfortunately, I can't use a Service since a Context is needed to register one. I did try using a Broadcast Intent, since I wanted to try passing the GraphicsBuffer directly to my app without converting it to a JPEG: it didn't work. It turns out Intents can't serialize file descriptors, which is used by GraphicsBuffers to share memory between processes.

Instead, I decided to design for prototyping, not security. I wanted to load these images into an ImageView, and there are many libraries that help load images into ImageView from HTTP.

Therefore, I decided to simply create a local HTTP server. Sure, it's insecure (allows any app to access the screen), but for a prototype, this is fine. (<b>Do not use this in a real app</b>).

I used the well-known [NanoHTTPD library](https://github.com/NanoHttpd/nanohttpd), which is a single file HTTP server that can be easily integrated into any app. I made two endpoints:

- The root page, `GET /`, calls the `getRecentTasksForUser` method and returns the tasks in JSON format.
- The thumbnail endpoint, `GET /thumbs/(id)`, calls the `getTaskSnapshot` method and returns a JPEG of the desired task.

Originally, I only had one endpoint, which sent the images along with the tasks; however, it turns out converting a GraphicsBuffer to a Bitmap takes almost half a second each, and it takes several seconds to get the list of apps. They were broken out into a separate endpoint to allow the main app to load the thumbnails on demand.

## The app itself: learning RecyclerView and Glide

Now that the list of tasks is available, I just need to show them in an app. I chose to use a RecyclerView to display the list of apps.

To download data from the local server, I used Square's [okhttp3](https://square.github.io/okhttp/) to simplify getting the JSON. To load the images into the ImageViews, I used Bumptech/Google's [Glide](https://github.com/bumptech/glide) library, which made loading images absolutely pain-free. I try to minimize the number of libraries I use in apps, but these libraries are well worth their size.

After a tiny bit of styling, we're seeing the list of apps!

The code so far can be found at <https://github.com/zhuowei/PillAppSwitcher>.

## What I learned

- How Android's Recent Apps screen actually works
- Accessing Activity Manager methods on Android from the command line
- What you can't do on Android (registering a Service from a command line app, sending an Intent with file descriptors passed in)
- Using Glide to load images in a RecyclerView

## Future steps

Next, I'll work on making an actual task switcher - that'll be the subject of an upcoming post.

## Note 1: Context

Why can't I just make a Context, then? A Context needs an ApplicationThread, which I can't make from a command line app. I can go more in-depth on this: let me know if how an Android app starts up interests you.