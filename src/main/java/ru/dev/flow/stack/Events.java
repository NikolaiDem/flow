package ru.dev.flow.stack;

import java.util.HashMap;
import java.util.Map;
import java.util.Queue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

public class Events {

    private static final Map<Long, Queue<CallNode>> eventsByThread = new ConcurrentHashMap<>();

    public static void add(CallNode node){
        long threadId = Thread.currentThread().threadId();
        eventsByThread.computeIfAbsent(threadId, k -> new ConcurrentLinkedQueue<>());
        Queue<CallNode> queue = eventsByThread.get(threadId);
        queue.add(node);
    }

    public static Map<Long, Queue<CallNode>> events() {
        return eventsByThread;
    }

    public static synchronized Map<Long, Queue<CallNode>> drainedEvents() {
        var snapshot = new HashMap<>(eventsByThread);
        eventsByThread.clear();
        return snapshot;
    }
}
