package ru.dev.flow;

import net.bytebuddy.asm.Advice;

import java.lang.reflect.Method;

public class FlowAdvice {

    @Advice.OnMethodEnter
    public static void enter(@Advice.Origin Method method) {
        CallNode node = new CallNode(
                method.getDeclaringClass().getName(),
                method.getName()
        );

        FlowCollector.enter(node);
    }

    @Advice.OnMethodExit(onThrowable = Throwable.class)
    public static void exit() {
        FlowCollector.exit();
    }
}