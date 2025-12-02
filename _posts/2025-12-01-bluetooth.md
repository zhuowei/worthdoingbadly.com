---
title: 'Proof-of-concept for CVE-2025-48593: No, this Android Bluetooth issue does NOT affect your phone or tablet'
categories: bluetooth, android
permalink: /bluetooth/
---

[CVE-2025-48593](https://www.cve.org/CVERecord?id=CVE-2025-48593), patched in [November's Android Security Bulletin](https://source.android.com/docs/security/bulletin/2025-11-01), only affects devices that support acting as Bluetooth headphones / speakers, such as some smartwatches, smart glasses, and cars.

To find out the impact of the issue, I examined the [patch](https://android.googlesource.com/platform/packages/modules/Bluetooth/+/b8153e05d0b9224feb0ace8c24eeeadc80e4dffc) from the Android bulletin and wrote a proof-of-concept that crashes the Bluetooth service in the Android Automotive emulator in Android Studio.

You can find my proof of concept at [https://github.com/zhuowei/blueshrimp](https://github.com/zhuowei/blueshrimp).

## Should I be worried?

No, you don't need to worry about this:

- As far as I can tell, phones and tablets are **NOT** vulnerable to CVE-2025-48593. The issue only affects Android 13-16 devices that support acting as Bluetooth headphones / speakers, such as some smartwatches, smart glasses, and cars.
- In addition, an attacker has to get a victim to [pair](https://cs.android.com/android/platform/superproject/main/+/main:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_rfc.cc;l=192;drc=86d90eee9dd37eccdd19449b9d72b883df060f9b) to the attacker before they can access the headset service. As long as you don't accept the pairing request on your smartwatch/glasses/car, you should be fine.
- My proof-of-concept isn't useful for a real attacker: I don't attempt to defeat ASLR, so this only crashes the Bluetooth service on a device. It can't do anything malicious.

## Demo

Here's a video showing the Bluetooth service crashing with "fault addr 0x4141414141414141" on the Android Automotive emulator in Android Studio:

<iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/tpJv3p89FHA" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
Build fingerprint: 'google/sdk_gcar_arm64/emulator_car64_arm64:14/UAA1.250512.001/13479943:userdebug/dev-keys'
Revision: '0'
ABI: 'arm64'
Timestamp: 2025-12-01 17:28:17.644347763-0500
Process uptime: 0s
Cmdline: com.google.android.bluetooth
pid: 6386, tid: 6424, name: bt_main_thread  >>> com.google.android.bluetooth <<<
uid: 1001002
tagged_addr_ctrl: 0000000000000001 (PR_TAGGED_ADDR_ENABLE)
pac_enabled_keys: 000000000000000f (PR_PAC_APIAKEY, PR_PAC_APIBKEY, PR_PAC_APDAKEY, PR_PAC_APDBKEY)
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x4141414141414141
    x0  4141414141414141  x1  b4000073106a14a0  x2  0000000000000103  x3  414141414141413e
    x4  b4000073106a15a3  x5  4141414141414241  x6  0000000000000100  x7  000000000000010f
    x8  0000000000000000  x9  4141414141414141  x10 0000000000000002  x11 00000070c20c8558
    x12 0000000000000018  x13 00000000ffffffbf  x14 0000000000000003  x15 0000000000000001
    x16 00000070c253f470  x17 00000073f6ee3a40  x18 00000070bb2c6060  x19 00000070c258c0c0
    x20 b4000073106a14a3  x21 0000000000000100  x22 00000070bc384000  x23 000000004141413e
    x24 00000070bc384000  x25 00000070bc384000  x26 00000070bc383ff8  x27 00000000000fc000
    x28 00000000000fe000  x29 00000070bc383470
    lr  00000070c20c3d58  sp  00000070bc383460  pc  00000073f6ee3b38  pst 00000000a0001000

15 total frames
backtrace:
      #00 pc 000000000005fb38  /apex/com.android.runtime/lib64/bionic/libc.so (__memcpy_aarch64_simd+248) (BuildId: 8bd98d931a32d13659267d7d53286e73)
      #01 pc 00000000006aad54  /apex/com.android.btservices/lib64/libbluetooth_jni.so (sdp_copy_raw_data(tCONN_CB*, bool)+344) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #02 pc 00000000006aa0c0  /apex/com.android.btservices/lib64/libbluetooth_jni.so (process_service_search_attr_rsp(tCONN_CB*, unsigned char*, unsigned char*)+624) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #03 pc 00000000006a9760  /apex/com.android.btservices/lib64/libbluetooth_jni.so (sdp_data_ind(unsigned short, BT_HDR*)+212) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #04 pc 00000000007387b4  /apex/com.android.btservices/lib64/libbluetooth_jni.so (l2c_csm_execute(t_l2c_ccb*, tL2CEVT, void*)+9412) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #05 pc 00000000009d6ce8  /apex/com.android.btservices/lib64/libbluetooth_jni.so (base::debug::TaskAnnotator::RunTask(char const*, base::PendingTask*)+196) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #06 pc 00000000009d6260  /apex/com.android.btservices/lib64/libbluetooth_jni.so (base::MessageLoop::RunTask(base::PendingTask*)+352) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #07 pc 00000000009d6574  /apex/com.android.btservices/lib64/libbluetooth_jni.so (base::MessageLoop::DoWork()+452) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #08 pc 00000000009d8964  /apex/com.android.btservices/lib64/libbluetooth_jni.so (base::MessagePumpDefault::Run(base::MessagePump::Delegate*)+100) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #09 pc 00000000009e4a34  /apex/com.android.btservices/lib64/libbluetooth_jni.so (base::RunLoop::Run()+64) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #10 pc 000000000069aaa4  /apex/com.android.btservices/lib64/libbluetooth_jni.so (bluetooth::common::MessageLoopThread::Run(std::__1::promise<void>)+336) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #11 pc 000000000069a584  /apex/com.android.btservices/lib64/libbluetooth_jni.so (bluetooth::common::MessageLoopThread::RunThread(bluetooth::common::MessageLoopThread*, std::__1::promise<void>)+48) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #12 pc 000000000069b090  /apex/com.android.btservices/lib64/libbluetooth_jni.so (void* std::__1::__thread_proxy<std::__1::tuple<std::__1::unique_ptr<std::__1::__thread_struct, std::__1::default_delete<std::__1::__thread_struct> >, void (*)(bluetooth::common::MessageLoopThread*, std::__1::promise<void>), bluetooth::common::MessageLoopThread*, std::__1::promise<void> > >(void*)+84) (BuildId: fe3c1bf88cf688f5197df2b2f326f723)
      #13 pc 00000000000cb6a8  /apex/com.android.runtime/lib64/bionic/libc.so (__pthread_start(void*)+208) (BuildId: 8bd98d931a32d13659267d7d53286e73)
      #14 pc 000000000006821c  /apex/com.android.runtime/lib64/bionic/libc.so (__start_thread+64) (BuildId: 8bd98d931a32d13659267d7d53286e73)
```

## Tested

I tested against 4 Android Emulators in Android Studio:

Affected:

- Android Automotive 14, API 34-ext9, "Android Automotive with Google APIs arm64-v8a System Image", version 5 - worked out of the box
- Android 15, API 35, "Google APIs ARM 64 v8a System Image", version 9 - worked once I [force-enabled](https://github.com/zhuowei/blueshrimp/blob/main/README.md#running) acting as a Bluetooth headset with root and `setprop bluetooth.profile.hfp.hf.enabled true`
- Android 13, API 33, "Google APIs ARM 64 v8a System Image", version 17 - worked once force-enabled

Not affected:

- Android 16 API 36.1 "Google APIs ARM 64 v8a System Image" revision 3 - patched against CVE-2025-48593: with force-enabled headset, running the proof-of-concept gives me:
  ```
  bumble.core.InvalidStateError: channel not open
  ```
- Android 12L, API 32, "Google APIs ARM 64 v8a System Image", version 8 - same as Android 16; "channel not open". It appears the Security Bulletin is correct, and only Android 13-16 is affected.

I also tested against real devices:

I don't have a physical Android device that acts as a Bluetooth headset, so I used root to [force-enable](https://gist.github.com/zhuowei/4fcaa4b0141d62f44af0cddd9b906588) it on two devices: my Pixel 3 XL (an Android 11 device), and an Android 14 device.
- the Android 11 device seems to be unaffected: it closes the SDP after the first response, like the patched emulator. It seems Android 11 is not vulnerable?
- the Android 14 device does seem to be affected the same way as the emulator.

I also tested against a pair of Meta Ray-Ban Display smart glasses (which runs a modified Android 14 with [Qualcomm's Bluetooth service](https://git.codelinaro.org/clo/la/platform/vendor/qcom-opensource/packages/apps/Bluetooth/-/tree/LA.QISI.14.0.r1-02800-qssi.0?ref_type=tags), which seems to be based on the [Android 12L](https://android.googlesource.com/platform/packages/apps/Bluetooth/+/refs/heads/android12L-gsi) code). It also seems to be unaffected: like the Pixel 3 XL on Android 11 and the patched Android 16 emulator, it outputs

```
bumble.core.InvalidStateError: channel not open
```

## My understanding of what's happening

Bluetooth headphones use the [Handsfree Profile](https://en.wikipedia.org/wiki/List_of_Bluetooth_profiles#Hands-Free_Profile_(HFP)).

Handsfree Profile is special: unlike some Bluetooth services, where one side acts as a server and the other side connects to it, both the headset and the connecting device (e.g. a phone) need to run Bluetooth servers.

After the phone connects to the headset's Handsfree service (UUID `0x111e`), the headset then connects back to the phone's Handsfree Audio Gateway service (UUID `0x111f`).

When a phone opens an RFCOMM connection to the headset's Handsfree service, in the headset's `hf_client` code:

- [bta_hf_client_allocate_handle](https://cs.android.com/android/platform/superproject/main/+/main:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_main.cc;l=556;drc=875c5971d0201d3c67cc166ad9ab8b2b4a7cab7f) allocates a `tBTA_HF_CLIENT_CB` handle from the pool
- [bta_hf_client_do_disc](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_sdp.cc;l=382;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) allocates a `tSDP_DISCOVERY_DB`, stores it in `client_cb->p_disc_db`, and starts SDP discovery
- [SDP_ServiceSearchAttributeRequest2](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/stack/sdp/sdp_api.cc;l=205;drc=138659ad3ff2961010b9cacd36fceb36ba73dcce) stores the `tSDP_DISCOVERY_DB` into a `tCONN_CB`'s `p_ccb->p_db`, then connects to the phone's SDP service
- now the `tSDP_DISCOVERY_DB` is stored both in the hf_client's `client_cb->p_disc_db` handle and in the SDP layer's `p_ccb->p_db`

```
hf_client:                  SDP:          
tBTA_HF_CLIENT_CB           tCONN_CB 1    
+-------------+             +------------+
|             |             |            |
| ACTIVE      |             | ACTIVE     |
|             |             |            |
|  p_disc_db  |             |   p_db     |
+------+------+             +------+-----+
       |                           |      
       |       tSDP_DISCOVERY_DB 1 |      
       |       +-----------+       |      
       |       |           |       |      
       |       |           |       |      
       +-------+           +-------+      
               |           |              
               +-----------+                        
```

When the phone's RFCOMM connection is closed:

- [bta_hf_client_mgmt_cback](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_rfc.cc;l=143;drc=86d90eee9dd37eccdd19449b9d72b883df060f9b) emits a `BTA_HF_CLIENT_RFC_CLOSE_EVT`
- [the bta_hf_client_st_opening state table](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_main.cc;l=157;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) calls the handler for [bta_hf_client_rfc_close](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_act.cc;l=278;drc=031a4c3b0a00602b7bbd08ffd8b4d02fdccb5989) and resets the state machine to `BTA_HF_CLIENT_INIT_ST`
- [bta_hf_client_sm_execute](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_main.cc;l=728;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) sees the state transition and deallocates the `tBTA_HF_CLIENT_CB` handle back to the pool
- However - before the patch for CVE-2025-48593 - the SDP connection is not cancelled, and is still waiting for a response
- At this time, there's a `tBTA_HF_CLIENT_CB` returned to the unallocated pool, with `client_cb->p_disc_db` still set and a still active SDP discovery

```
hf_client:                  SDP:          
tBTA_HF_CLIENT_CB           tCONN_CB 1    
+-------------+             +------------+
|             |             |            |
| INACTIVE    |             | ACTIVE     |
|             |             |            |
|  p_disc_db  |             |   p_db     |
+------+------+             +------+-----+
       |                           |      
       |       tSDP_DISCOVERY_DB 1 |      
       |       +-----------+       |      
       |       |           |       |      
       |       |           |       |      
       +-------+           +-------+      
               |           |              
               +-----------+              
```

When the phone answers the SDP discovery with an error:

- [bta_hf_client_sdp_cback](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_sdp.cc;l=85;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) emits a `BTA_HF_CLIENT_DISC_INT_RES_EVT`
- [the bta_hf_client_st_opening state table](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_main.cc;l=164;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) calls the handler for [bta_hf_client_disc_int_res](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_act.cc;l=319;drc=031a4c3b0a00602b7bbd08ffd8b4d02fdccb5989)
- [bta_hf_client_free_db](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_sdp.cc;l=413;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) frees `client_cb->p_disc_db`
- so now the `tSDP_DISCOVERY_DB` is freed, `client_cb->p_disc_db` is null, and the SDP layer no longer has a `p_ccb->p_db` to the discovery DB.

```
hf_client:                  SDP:          
tBTA_HF_CLIENT_CB           tCONN_CB 1    
+-------------+             +------------+
|             |             |            |
| INACTIVE    |             | INACTIVE   |
|             |             |            |
|  p_disc_db  |             |   p_db     |
+-------------+             +------------+
                                         
               (freed)
               +-----------+  
               |           |            
               |           | 
               |           |     
               |           |              
               +-----------+              
```

However, if the phone opens RFCOMM again before the first SDP discovery returns:

- we reallocate a handle (probably the same handle that was deallocated to the pool previously) and call discovery again.
- the `client_cb->p_disc_db` now points to a new `tSDP_DISCOVERY_DB`, and the SDP layer holds two `tSDP_DISCOVERY_DB`s: one `p_ccb->p_db` holds the old DB from the first connection and one `p_ccb->p_db` holds the new DB from the second connection

```
hf_client:                  SDP:                            
tBTA_HF_CLIENT_CB           tCONN_CB 1       tCONN_CB 2     
+-------------+             +------------+   +-------------+
|             |             |            |   |             |
| ACTIVE      |             | ACTIVE     |   | ACTIVE      |
|             |             |            |   |             |
|  p_disc_db  |             |   p_db     |   |   p_db      |
+-----+-------+             +------+-----+   +----+--------+
      |                            |              |         
      |        tSDP_DISCOVERY_DB 1 |              |         
      |        +-----------+       |              |         
      |        |           |       |              |         
      |        |           |       |              |         
      |        |           +-------+              |         
      |        |           |                      |         
      |        +-----------+                      |         
      |                                           |         
      |                                           |         
      |                                           |         
      |        tSDP_DISCOVERY_DB 2                |         
      |        +-----------+                      |         
      |        |           |                      |         
      |        |           |                      |         
      +--------+           +----------------------+         
               |           |                                
               |           |                                
               +-----------+                                
```

Now, the phone answers the first SDP discovery with an error:

- the SDP layer closes the `p_ccb` from the first connection
- [bta_hf_client_free_db](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/bta/hf_client/bta_hf_client_sdp.cc;l=413;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) frees `client_cb->p_disc_db`, which is the _second_ connection's DB
- now the hf_client's `client_cb->p_disc_db` is freed and set to null, and the SDP's `p_ccb` for the first connection is gone
- but the `p_ccb` for the second connection is still active, so `p_ccb->p_db` for the second SDP discovery request points to a freed `tSDP_DISCOVERY_DB`

```
hf_client:                  SDP:                            
tBTA_HF_CLIENT_CB           tCONN_CB 1       tCONN_CB 2     
+-------------+             +------------+   +-------------+
|             |             |            |   |             |
| ACTIVE      |             | INACTIVE   |   | ACTIVE      |
|             |             |            |   |             |
|  p_disc_db  |             |   p_db     |   |   p_db      |
+-------------+             +------------+   +----+--------+
                                                  |         
               tSDP_DISCOVERY_DB 1                |         
               +-----------+                      |         
               |           |                      |         
               |           |                      |         
               |           |                      |         
               |           |                      |         
               +-----------+                      |         
                                                  |         
                                                  |         
                                                  |         
               (freed!)                           |         
               +-----------+                      |         
               |           |                      |         
               |           |                      |         
               |           +----------------------+         
               |           |                                
               |           |                                
               +-----------+                                
```

Finally, the phone answers the second SDP discovery with an actual response:

- the SDP layer processes the incoming data in [sdp_data_ind](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/stack/sdp/sdp_main.cc;l=234;drc=0e45ce1dc53e611da84344e7c5a11108ad7dba46) and dispatches to sdp_disc_server_rsp
- [process_service_search_attr_rsp](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/stack/sdp/sdp_discovery.cc;l=683;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) starts reading from `p_ccb->p_db`
- since `p_db` was already freed by `bta_hf_client_free_db` from the first SDP discovery's error response, the second SDP response causes use-after-free.

## Exploiting the use-after-free

To exploit the use-after-free, I need to re-allocate the memory buffer with contents I control.

Both of Android's supported memory allocators ([Scudo](https://www.synacktiv.com/en/publications/behind-the-shield-unmasking-scudos-defenses#:~:text=For%20efficiency%2C%20the%20library%20first%20seeks%20a%20block%20within%20the%20thread's%20local%20cache) and [Jemalloc](https://www.synacktiv.com/publications/exploring-android-heap-allocations-in-jemalloc-new#:~:text=To%20speed%20up%20the%20allocation%20process)) have a first-in-first-out thread local cache. After triggering the issue, the next time Bluetooth calls `malloc` on the `bt_main_thread` for around 0x1010 bytes, it would re-use the most recently freed memory block of similar size - the freed `tSDP_DISCOVERY_DB`.

Unfortunately, just sending a Bluetooth packet isn't enough to trigger this allocation. Received packets are [allocated](https://cs.android.com/android/platform/superproject/main/+/main:packages/modules/Bluetooth/system/main/shim/helpers.h;l=120;drc=61197364367c9e404c7da6900658f1b16c42d0da) on a different thread, `bt_stack_manager_thread`. I have to find an allocation that happens on the main thread, inside the protocol implementations.

Synaktive's writeup of a [previous Android Bluetooth exploit](https://www.synacktiv.com/en/publications/paint-it-blue-attacking-the-bluetooth-stack) mentions that packet reassembly can be used to allocate memory on the Bluetooth main thread.

I wasn't able to use their approach of using [ERTM](https://en.wikipedia.org/wiki/List_of_Bluetooth_protocols#Logical_link_control_and_adaptation_protocol_(L2CAP)) with [AVCTP](https://en.wikipedia.org/wiki/List_of_Bluetooth_protocols#Audio/video_control_transport_protocol_(AVCTP)), as Bumble does not support ERTM; however, it turns out AVCTP's [own reassembly routine](https://cs.android.com/android/platform/superproject/main/+/main:packages/modules/Bluetooth/system/stack/avct/avct_lcb_act.cc;l=114;drc=61197364367c9e404c7da6900658f1b16c42d0da) also does a `osi_malloc` and fills it with the received packet's contents.

I control everything but the first 0x13 bytes of the AVCTP allocation. Conveniently, [`tSDP_DISCOVERY_DB`](https://cs.android.com/android/platform/superproject/main/+/main:packages/modules/Bluetooth/system/stack/sdp/sdp_discovery_db.h;l=65;drc=11911dbdae8407d6d8b87ad4f571725e3e2a1c2d) has a `raw_data` field:

```cpp
struct tSDP_DISCOVERY_DB {
  uint32_t mem_size;                                  /* Memory size of the DB        */
  uint32_t mem_free;                                  /* Memory still available       */
  tSDP_DISC_REC* p_first_rec;                         /* Addr of first record in DB   */
  uint16_t num_uuid_filters;                          /* Number of UUIds to filter    */
  bluetooth::Uuid uuid_filters[SDP_MAX_UUID_FILTERS]; /* UUIDs to filter */
  uint16_t num_attr_filters;                          /* Number of attribute filters  */
  uint16_t attr_filters[SDP_MAX_ATTR_FILTERS];        /* Attributes to filter */
  uint8_t* p_free_mem;                                /* Pointer to free memory       */
  uint8_t* raw_data; /* Received record from server. allocated/released by client  */
  uint32_t raw_size; /* size of raw_data */
  uint32_t raw_used; /* length of raw_data used */
};
```

and the [`sdp_copy_raw_data`](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/stack/sdp/sdp_discovery.cc;l=238;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) method `memcpy`s the SDP response directly into `raw_data`.

So, to get an arbitrary write, my proof-of-concept:

- responds to the first SDP request with an error, which `free`s the `tSDP_DISCOVERY_DB`
- (at this point, the Android Automotive emulator tries to connect to A2DP and sends another SDP request: my proof-of-concept answers this request with an error too.)
- waits for the second SDP request
- sends an AVRCP packet to reallocate the dangling `tSDP_DISCOVERY_DB`, with a fake object that sets `raw_data` to my target address
- responds to the second SDP request
- `sdp_copy_raw_data` runs and does a `memcpy` into my target address with my SDP response

I wrote the proof-of-concept using [Bumble](https://github.com/google/bumble):
- it's a full Bluetooth stack, which gives me full control over the SDP connection
- it can connect both to Android Emulator and to real USB Bluetooth dongles

## What about ASLR?

ASLR is left as an exercise for the reader... because I'm not experienced enough to figure this out.

I think it's possible to get an information disclosure from this.

I currently re-allocate after the SDP request is already sent, but [I found](https://github.com/zhuowei/blueshrimp/blob/attempt-read-failed/dumpbt.js) it's possible to re-allocate just before the SDP request is sent by delaying the L2CAP configuration response. This lets me overwrite `num_uuid_filters` and `num_attr_filters`. Since there's no bounds check when accessing [uuid_filters](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/stack/sdp/sdp_discovery.cc;l=684;drc=769caf391c6055c6f9db945b71d96b2f01c8799c) and [attr_filters](https://cs.android.com/android/platform/superproject/+/android-latest-release:packages/modules/Bluetooth/system/stack/sdp/sdp_discovery.cc;l=692;drc=769caf391c6055c6f9db945b71d96b2f01c8799c), I can get it to copy memory after those fields into the SDP request. (A good target might be `p_free_mem`, just past the `attr_filters` - it gives the address of the `tSDP_DISCOVERY_DB` itself.)

(In fact, if `num_attr_filters` is set high enough, `sdpu_build_attrib_seq` also overflows the request buffer, giving a relative out-of-bounds write when constructing the SDP request).

Unfortunately, `num_uuid_filters` falls into the 0x13 bytes that I can't control with AVCTP, and it's set to "0x06 0x06". So `sdpu_build_uuid_seq` fills up the entire 0x1010 byte buffer, then I get "cannot send message bigger than peer's mtu size: len=4096 mtu=1691".

(Maybe ERTM, which only has 0x8 bytes of overhead, would work?)

Anyways, shaping the heap so interesting memory falls behind the `tSDP_DISCOVERY_DB` is probably going to be difficult. Let me know if you figure it out!

## Thanks

Credits to:
- "Dikun Zhang (stardesty) of Li Auto security team", according to the [Android Security Bulletin](https://source.android.com/docs/security/overview/acknowledgements), for originally discovering this issue.
- the members of [FreeXR](https://github.com/FreeXR) and XRBreak for their support.


## What I learned

- Far too much about the Android Bluetooth stack
- How to write Bluetooth services in Bumble
- How Bluetooth protocols, such as L2CAP, SDP, RFCOMM, Headset Client, and AVRCP/AVCTP work
- How to (kinda...) [forward](https://notnow.dev/notice/AzvNJ51CKQ6XJv63qS) Android Emulator's Bluetooth into another Linux VM
- How to use Frida to instrument Android apps. This was crucial for [logging](https://github.com/zhuowei/blueshrimp/blob/main/dumpbt.js) when the database is freed and what malloc re-allocated it.
- How to capture Bluetooth traffic on physical Android devices, thanks to [wejn's guide](https://wejn.org/2021/04/streaming-bluetooth-capture-to-wireshark-without-btsnoop-net/)
