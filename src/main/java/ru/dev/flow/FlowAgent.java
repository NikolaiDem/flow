
package ru.dev.flow;


import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import org.junit.jupiter.api.Test;
import ru.dev.flow.advice.FlowAdvice;
import ru.dev.flow.advice.TestBoundaryAdvice;
import ru.dev.flow.filters.FlowMatchers;
import ru.dev.flow.output.Json;
import ru.dev.flow.stack.Events;

import java.lang.instrument.Instrumentation;

import static net.bytebuddy.matcher.ElementMatchers.*;
import static ru.dev.flow.config.FlowConfig.CONFIG;

public class FlowAgent {

    public static void premain(String args, Instrumentation inst) {
        // 1. ставим shutdown hook ОДИН РАЗ
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("\n=== CALL GRAPH ===");
            Json json = new Json(Events.events(), CONFIG.getStackOutput());
            json.write();
        }));

        new AgentBuilder.Default()
                .with(AgentBuilder.RedefinitionStrategy.REDEFINITION)
                .type(FlowMatchers.typeFilter(CONFIG))
                .transform((builder, type, loader, module, pd) ->
                        builder.method(any())
                                .intercept(Advice.to(FlowAdvice.class))
                )
                .type(nameEndsWith("IT").or(nameEndsWith("Test")))
                .transform((builder, type, loader, module, pd) ->
                        builder.method(isAnnotatedWith(Test.class))
                                .intercept(Advice.to(TestBoundaryAdvice.class))
                )
                .installOn(inst);
    }
}
