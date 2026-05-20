
package com.bank.flow;

import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;

import java.lang.instrument.Instrumentation;

import static net.bytebuddy.matcher.ElementMatchers.*;

public class FlowAgent {

    public static void premain(String args, Instrumentation inst) {

        new AgentBuilder.Default()
                .ignore(nameStartsWith("net.bytebuddy"))
                .type(nameStartsWith("com.bank"))
                .transform((builder, type, loader, module, pd) ->
                        builder.visit(Advice.to(FlowAdvice.class)
                                .on(any()))
                )
                .installOn(inst);
    }
}
