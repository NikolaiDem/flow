
package com.bank.flow;

public class FlowCollector {

    public static void enter(CallNode node) {
        var ctx = FlowContext.get();

        if (!ctx.stack.isEmpty()) {
            CallNode parent = ctx.stack.peek();
            parent.children.add(node);
            node.parent = parent;
        }

        ctx.stack.push(node);
    }

    public static void exit() {
        var ctx = FlowContext.get();
        if (!ctx.stack.isEmpty()) {
            CallNode n = ctx.stack.pop();
            n.end = System.currentTimeMillis();
        }
    }

    public static CallNode root() {
        var ctx = FlowContext.get();
        return ctx.stack.isEmpty() ? null : ctx.stack.getLast();
    }
}
