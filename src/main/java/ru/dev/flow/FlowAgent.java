
package ru.dev.flow;


import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import net.bytebuddy.matcher.ElementMatchers;
import ru.dev.flow.advice.FlowAdvice;
import ru.dev.flow.advice.SpringApplicationConstructorAdvice;
import ru.dev.flow.config.AgentOptions;
import ru.dev.flow.filters.FlowGenericMatchers;
import ru.dev.flow.output.Json;
import ru.dev.flow.stack.Events;

import java.lang.instrument.Instrumentation;

import static net.bytebuddy.matcher.ElementMatchers.isSynthetic;
import static net.bytebuddy.matcher.ElementMatchers.nameStartsWith;
import static ru.dev.flow.config.FlowConfig.CONFIG;

public class FlowAgent {

    static volatile AgentOptions options = AgentOptions.parse(null);

    public static void premain(String args, Instrumentation inst) {
        options = AgentOptions.parse(args);
        AgentBuilder agentBuilder = new AgentBuilder.Default()
                .with(AgentBuilder.RedefinitionStrategy.RETRANSFORMATION)
                .with(AgentBuilder.InitializationStrategy.NoOp.INSTANCE)
                .with(AgentBuilder.TypeStrategy.Default.REDEFINE)
                .ignore(
                        nameStartsWith("net.bytebuddy.")          // Игнорировать сам Byte Buddy
                                .or(nameStartsWith("org.slf4j."))          // Игнорировать логирование
                                .or(nameStartsWith("ru.dev.flow.")) // Игнорировать классы вашего агента
                                .or(isSynthetic())                         // Игнорировать синтетические классы (важно!)
                );
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
        if (options.isFlowRecording()) {
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                System.err.println("\n=== CALL GRAPH WRITE TO FILE ===");
                Json json = new Json(Events.events(), CONFIG.getStackOutput());
                json.write();
            }));
            var flowMethodMatchers = new FlowGenericMatchers.FlowMethodMatchers();
            var flowTypeMatchers = new FlowGenericMatchers.FlowTypeMatchers();
            agentBuilder = agentBuilder.type(flowTypeMatchers.filter(CONFIG))
                    .transform((builder, type, loader, module, pd) ->
                            builder.visit(Advice.to(FlowAdvice.class)
                                            .on(flowMethodMatchers.filter(CONFIG))));
        }
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
