package com.bank.flow;

import java.util.List;

public class FlowRegistry {

    private static final List<CallNode> ROOTS = new java.util.concurrent.CopyOnWriteArrayList<>();

    public static void addRoot(CallNode node) {
        ROOTS.add(node);
    }

    public static List<CallNode> roots() {
        return ROOTS;
    }
}