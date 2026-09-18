package ru.dev.flow.advice;

import net.bytebuddy.asm.Advice;

public class LogRecordingFinishAdvice {

    @Advice.OnMethodEnter
    public static LogRecordingEvent enter(@Advice.This Object self) {
        var logRecordingEvent = new LogRecordingEvent();
        logRecordingEvent.className = self.getClass().getName();
        logRecordingEvent.methodName = "logs";
        logRecordingEvent.threadName = Thread.currentThread().getName();
        logRecordingEvent.begin();
        logRecordingEvent.commit();
        return logRecordingEvent;
    }
}