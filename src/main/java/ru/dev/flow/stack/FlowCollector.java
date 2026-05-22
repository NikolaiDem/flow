package ru.dev.flow.stack;

import ru.dev.flow.filters.CallNodeFilter;

import java.util.Map;
import java.util.Queue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

public class FlowCollector {

    private static final Map<Long, Queue<CallNode>> eventsByThread = new ConcurrentHashMap<>();

    public static void add(CallNode node) {
        if (!CallNodeFilter.matches(node)) {
            return;
        }
        long threadId = Thread.currentThread().threadId();
        eventsByThread.computeIfAbsent(threadId, k -> new ConcurrentLinkedQueue<>());
        Queue<CallNode> queue = eventsByThread.get(threadId);
        queue.add(node);
    }

    public static Map<Long, Queue<CallNode>> events() {
        return eventsByThread;
    }
}