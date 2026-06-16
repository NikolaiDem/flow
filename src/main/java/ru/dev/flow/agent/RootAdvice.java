package ru.dev.flow.agent;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;
import net.bytebuddy.asm.Advice;

public class RootAdvice {

    @Advice.OnMethodEnter
    public static Scope enter(
            @Advice.Origin("#t") String className,
            @Advice.Origin("#m") String methodName) {
        Span span = GlobalOpenTelemetry.getTracer("business-agent").spanBuilder(className + "." + methodName)
                // ВАЖНО: родитель берётся автоматически из Context.current()
                .startSpan();
        System.out.println(span);
        return span.makeCurrent();
    }

    @Advice.OnMethodExit(onThrowable = Throwable.class)
    public static void exit(
            @Advice.Enter Scope scope) {
        scope.close();
    }
}