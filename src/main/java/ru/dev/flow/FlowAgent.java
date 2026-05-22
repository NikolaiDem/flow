
package ru.dev.flow;


import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import ru.dev.flow.advice.FlowAdvice;
import ru.dev.flow.filters.FlowMatchers;
import ru.dev.flow.output.Json;
import ru.dev.flow.stack.FlowCollector;

import java.lang.instrument.Instrumentation;

import static net.bytebuddy.matcher.ElementMatchers.*;
import static ru.dev.flow.config.FlowConfig.CONFIG;

public class FlowAgent {

    public static void premain(String args, Instrumentation inst) {
        // 1. ставим shutdown hook ОДИН РАЗ
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("\n=== CALL GRAPH ===");
            Json json = new Json(FlowCollector.events(), CONFIG.getStackOutput());
            json.write();
        }));

        new AgentBuilder.Default()
                .with(AgentBuilder.RedefinitionStrategy.REDEFINITION)
                .type(FlowMatchers.typeFilter(CONFIG))
                .transform((builder, type, loader, module, pd) ->
                        builder.method(any())
                                .intercept(Advice.to(FlowAdvice.class))
                )
                .installOn(inst);
    }
}
