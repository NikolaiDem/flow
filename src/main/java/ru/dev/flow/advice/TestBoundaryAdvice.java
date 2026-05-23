package ru.dev.flow.advice;

import net.bytebuddy.asm.Advice;
import ru.dev.flow.stack.CallNode;
import ru.dev.flow.stack.CallNodeType;
import ru.dev.flow.stack.Events;

import java.lang.reflect.Method;

public class TestBoundaryAdvice {

    @Advice.OnMethodEnter
    public static void enter(@Advice.Origin Method method) {
        CallNode node = new CallNode(
                method.getDeclaringClass().getName(),
                method.getName(),
                CallNodeType.START_TEST
        );
        Events.add(node);
    }

    @Advice.OnMethodExit(onThrowable = Throwable.class)
    public static void exit(@Advice.Origin Method method) {
        CallNode node = new CallNode(
                method.getDeclaringClass().getName(),
                method.getName(),
                CallNodeType.END_TEST
        );
        Events.add(node);
    }
}