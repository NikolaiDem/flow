package ru.dev.flow;

public class FlowCollector {

    public static void enter(CallNode node) {
        var ctx = FlowContext.get();
        System.out.println("Enter to " + node);
        if (ctx.stack.isEmpty()) {
            FlowRegistry.addRoot(node); // 👈 ВАЖНО
        } else {
            CallNode parent = ctx.stack.peek();
            parent.children.add(node);
            node.parent = parent;
        }

        ctx.stack.push(node);
    }

    public static void exit() {
        var ctx = FlowContext.get();

        if (!ctx.stack.isEmpty()) {
            CallNode node = ctx.stack.pop();
            node.end = System.currentTimeMillis();
        }

        if (ctx.stack.isEmpty()) {
            // поток завершил execution tree — можно очистить ThreadLocal при желании
            // FlowContext.clear();
        }
    }

    public static java.util.List<CallNode> roots() {
        return FlowContext.get().roots;
    }
}