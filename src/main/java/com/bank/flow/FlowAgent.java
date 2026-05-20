
package com.bank.flow;


import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;

import java.lang.instrument.Instrumentation;

import static net.bytebuddy.matcher.ElementMatchers.*;

public class FlowAgent {

    public static void premain(String args, Instrumentation inst) {
        // 1. ставим shutdown hook ОДИН РАЗ
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("\n=== CALL GRAPH ===");

            var roots = FlowCollector.roots();
            System.out.println(roots);
        }));

        new AgentBuilder.Default()
                .with(AgentBuilder.RedefinitionStrategy.RETRANSFORMATION)
                .type(nameContains("com.example"))
                .transform((builder, type, loader, module, pd) -> {

                   // System.out.println("TRANSFORM: " + type.getName());

                    return builder
                            .method(any())
                            .intercept(Advice.to(FlowAdvice.class));
                })
                .installOn(inst);
    }
}
