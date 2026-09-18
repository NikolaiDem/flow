package ru.dev.flow.advice;

import jdk.jfr.Category;
import jdk.jfr.Event;
import jdk.jfr.Label;
import jdk.jfr.Name;

@Name("LogRecording")
@Label("recording")
@Category("Application")
public class LogRecordingEvent extends Event {

    @Label("Class")
    String className;

    @Label("Method")
    String methodName;

    @Label("Thread")
    String threadName;
}
