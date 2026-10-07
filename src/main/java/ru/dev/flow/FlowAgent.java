
package ru.dev.flow;


import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import net.bytebuddy.matcher.ElementMatchers;
import ru.dev.flow.advice.SpringApplicationConstructorAdvice;
import ru.dev.flow.config.AgentOptions;

import java.lang.instrument.Instrumentation;

public class FlowAgent {

    static volatile AgentOptions options = AgentOptions.parse(null);

    public static void premain(String args, Instrumentation inst) {
        options = AgentOptions.parse(args);
//        var flowMethodMatchers = new FlowGenericMatchers.FlowMethodMatchers();
//        var flowTypeMatchers = new FlowGenericMatchers.FlowTypeMatchers();
        AgentBuilder agentBuilder = new AgentBuilder.Default()
                .with(AgentBuilder.RedefinitionStrategy.REDEFINITION);
//                .type(flowTypeMatchers.filter(CONFIG))
//                .transform((builder, type, loader, module, pd) ->
//                        builder.method(flowMethodMatchers.filter(CONFIG))
//                                .intercept(Advice.to(FlowAdvice.class))
//                )
//                .type(nameEndsWith("IT").or(nameEndsWith("Test")))
//                .transform((builder, type, loader, module, pd) ->
//                        builder.method(isAnnotatedWith(Test.class))
//                                .intercept(Advice.to(TestBoundaryAdvice.class))
//                )
//                .type(named("ru.alfabank.pc.api.logback.assertion.InMemoryAppender"))
//                .transform((builder, type, loader, module, pd) ->
//                        builder.method(named("recording"))
//                                .intercept(Advice.to(LogRecordingStartAdvice.class))
//                )
//                .type(named("ru.alfabank.pc.api.logback.assertion.LogRecording"))
//                .transform((builder, type, loader, module, pd) ->
//                        builder.method(named("logs"))
//                                .intercept(Advice.to(LogRecordingFinishAdvice.class))
//                );
        if (options.isSpringJfr()) {
            System.err.println("spring-jfr=true, registering SpringApplication transformer");
            agentBuilder = agentBuilder.type(ElementMatchers.named("org.springframework.boot.SpringApplication"))
                    .transform((builder, type, classLoader, module, protectionDomain) ->
                            builder
                                    .constructor(ElementMatchers.any())
                                    .intercept(Advice.to(SpringApplicationConstructorAdvice.class))
                    );
        }
        agentBuilder
                .installOn(inst);
    }
}
