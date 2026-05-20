
package com.bank.flow;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.UUID;

public class FlowContext {

    private static final ThreadLocal<Context> CTX =
            ThreadLocal.withInitial(Context::new);

    public static class Context {
        public String traceId;
        public Deque<CallNode> stack = new ArrayDeque<>();
    }

    public static void init() {
        CTX.get().traceId = UUID.randomUUID().toString();
    }

    public static Context get() {
        return CTX.get();
    }

    public static void clear() {
        CTX.remove();
    }
}
