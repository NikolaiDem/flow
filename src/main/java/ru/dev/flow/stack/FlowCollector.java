package ru.dev.flow.stack;

import ru.dev.flow.filters.CallNodeFilter;

public class FlowCollector {

    public static void add(CallNode node) {
        if (!CallNodeFilter.matches(node)) {
            return;
        }
        Events.add(node);
    }
}