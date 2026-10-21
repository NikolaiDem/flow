package ru.dev.flow.stack;

import java.util.HashMap;
import java.util.Map;
import java.util.Queue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

public class Events {

    private static final Map<String, Queue<CallNode>> eventsByThread = new ConcurrentHashMap<>();

    public static void add(CallNode node){
        var threadId = Thread.currentThread().getName();
        eventsByThread.computeIfAbsent(threadId, k -> new ConcurrentLinkedQueue<>());
        Queue<CallNode> queue = eventsByThread.get(threadId);
        queue.add(node);
    }

    public static Map<String, Queue<CallNode>> events() {
        return eventsByThread;
    }

    public static synchronized Map<String, Queue<CallNode>> drainedEvents() {
        var snapshot = new HashMap<>(eventsByThread);
        eventsByThread.clear();
        return snapshot;
    }
}
