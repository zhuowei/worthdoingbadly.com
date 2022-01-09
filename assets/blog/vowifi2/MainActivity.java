package com.worthdoingbadly.cdmasmstester;

import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;
import android.telephony.SmsMessage;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        try {
            doSms();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static final byte[] pdu = new byte[]{
            (byte) 0x1, (byte) 0x2d, (byte) 0x0, (byte) 0x0, (byte) 0x10, (byte) 0x10, (byte) 0x2, (byte) 0x2, (byte) 0xe, (byte) 0x88, (byte) 0x85, (byte) 0x98, (byte) 0x9a, (byte) 0x9a, (byte) 0x9a, (byte) 0x9b, (byte) 0x1b, (byte) 0x1b, (byte) 0x1b, (byte) 0x9b, (byte) 0x9b, (byte) 0x9b, (byte) 0x80, (byte) 0x8, (byte) 0x16, (byte) 0x0, (byte) 0x3, (byte) 0x10, (byte) 0x0, (byte) 0x0, (byte) 0x1, (byte) 0x7, (byte) 0x48, (byte) 0x2f, (byte) 0x41, (byte) 0x94, (byte) 0xdf, (byte) 0xe8, (byte) 0x30, (byte) 0x3, (byte) 0x6, (byte) 0x22, (byte) 0x1, (byte) 0x8, (byte) 0x4, (byte) 0x58, (byte) 0x40
    };

    private static void doSms() throws Exception {
        // disable graylist

        Class smsMessageClass = Class.forName("com.android.internal.telephony.cdma.SmsMessage");
        Method createFromEfRecordMethod = smsMessageClass.getMethod("createFromEfRecord", Integer.TYPE, byte[].class);
        Object smsObj = createFromEfRecordMethod.invoke(null, 0, pdu);
        System.out.println("sms obj: " + smsObj);
        if (smsObj == null) return;
        Constructor<SmsMessage> frameworkSmsMessageConstructor = SmsMessage.class.getConstructor(Class.forName("com.android.internal.telephony.SmsMessageBase"));
        SmsMessage smsMessage = frameworkSmsMessageConstructor.newInstance(smsObj);
        System.out.println("smsMessage " + smsMessage);
        System.out.println(smsMessage.getDisplayMessageBody());
        System.out.println(smsMessage.getDisplayOriginatingAddress());
    }
}