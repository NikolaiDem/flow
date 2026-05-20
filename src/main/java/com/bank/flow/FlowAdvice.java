
package com.bank.flow;

import net.bytebuddy.asm.Advice;

public class FlowAdvice {

    @Advice.OnMethodEnter
    public static void enter(@Advice.Origin Class<?> clazz,
                             @Advice.Origin String method) {

        CallNode node = new CallNode(clazz.getName(), method);
        FlowCollector.enter(node);
    }

    @Advice.OnMethodExit
    public static void exit() {
        FlowCollector.exit();
    }
}
