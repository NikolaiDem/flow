package ru.dev.flow;

import lombok.SneakyThrows;
import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import net.bytebuddy.description.type.TypeDescription;
import net.bytebuddy.dynamic.DynamicType;
import net.bytebuddy.matcher.ElementMatchers;
import net.bytebuddy.utility.JavaModule;
import ru.dev.flow.advice.FlowAdvice;
import ru.dev.flow.advice.SpringApplicationConstructorAdvice;
import ru.dev.flow.config.FlowConfig;
import ru.dev.flow.config.FlowLogger;
import ru.dev.flow.filters.FlowGenericMatchers;
import ru.dev.flow.output.Json;
import ru.dev.flow.stack.Events;

import java.lang.instrument.Instrumentation;
import java.nio.file.Path;
import java.util.Arrays;

import static net.bytebuddy.matcher.ElementMatchers.isMethod;
import static net.bytebuddy.matcher.ElementMatchers.nameStartsWith;

public class FlowAgent {

    private static final FlowLogger log = FlowLogger.get();

    static {
        Runtime.getRuntime().addShutdownHook(new Thread(log::close));
    }

    @SneakyThrows
    public static void premain(String args, Instrumentation inst) {
        var config = FlowConfig.get();
        var allLoadedClasses = inst.getAllLoadedClasses();
        log.debug("All Loaded classes");
        Arrays.stream(allLoadedClasses)
                .map(Class::getName)
                .forEach(log::debug);
        var listener = getListener();
        AgentBuilder agentBuilder = new AgentBuilder.Default()
                .with(AgentBuilder.TypeStrategy.Default.REDEFINE)
                .ignore(
                        nameStartsWith("net.bytebuddy.")          // Игнорировать сам Byte Buddy
                                .or(nameStartsWith("org.slf4j."))          // Игнорировать логирование
                                .or(nameStartsWith("ru.dev.flow.")) // Игнорировать классы вашего агента
                )
                .with(listener);

        if (config.getAgent().getFlowRecording()) {
            String stackOutDir = config.getFlow().getStackOutput();
            if (stackOutDir == null) {
                throw new IllegalArgumentException("FLOW_AGENT_STACK_OUTPUT is not defined");
            }
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                Json json = new Json(Events.events(), Path.of(stackOutDir));
                json.write();
            }));
            var flowMethodMatchers = new FlowGenericMatchers.FlowMethodMatchers();
            var flowTypeMatchers = new FlowGenericMatchers.FlowTypeMatchers();
            var typeFilter = flowTypeMatchers.filter(config);
            log.debug("Type filter " + typeFilter);
            var methodFilter = flowMethodMatchers.filter(config);
            log.debug("Method filter " + methodFilter);
            agentBuilder = agentBuilder.type(typeFilter)
                    .transform((builder, type, loader, module, pd) ->
                            builder.visit(Advice.to(FlowAdvice.class)
                                    .on(isMethod().and(methodFilter))));
        }

        if (config.getAgent().getSpringJfr()) {
            log.debug("spring-jfr=true, registering SpringApplication transformer");
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

    private static AgentBuilder.Listener.Adapter getListener() {
        return new AgentBuilder.Listener.Adapter() {
            @Override
            public void onTransformation(TypeDescription typeDescription, ClassLoader classLoader, JavaModule module, boolean loaded, DynamicType dynamicType) {
                log.debug("Transformed " + typeDescription);
            }

            @Override
            public void onIgnored(TypeDescription typeDescription, ClassLoader classLoader, JavaModule module, boolean loaded) {
                log.debug("Ignored " + typeDescription);
            }

            @Override
            public void onDiscovery(String typeName, ClassLoader classLoader, JavaModule module, boolean loaded) {
                log.debug("Discovered " + typeName);
            }
        };
    }
}
