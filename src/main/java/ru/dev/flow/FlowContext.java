package ru.dev.flow;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

public class FlowContext {

    private static final ThreadLocal<FlowContext> TL =
            ThreadLocal.withInitial(FlowContext::new);

    public final Deque<CallNode> stack = new ArrayDeque<>();
    public final List<CallNode> roots = new ArrayList<>();

    public static FlowContext get() {
        return TL.get();
    }

    public static void clear() {
        TL.remove();
    }
}