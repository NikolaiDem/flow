import ru.dev.flow.filters.FlowGenericMatchers;
import ru.dev.flow.output.Json;
import ru.dev.flow.stack.Events;

import java.io.*;
import java.lang.instrument.Instrumentation;
import java.util.Arrays;

import static net.bytebuddy.matcher.ElementMatchers.*;
import static ru.dev.flow.config.FlowConfig.CONFIG;

public class FlowAgent {

    static volatile AgentOptions options = AgentOptions.parse(null);
    public static BufferedWriter FILE_WRITER;
    static {
        try {
            FILE_WRITER = new BufferedWriter(new FileWriter("D://work/logs/flow.log", true));
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @SneakyThrows
    public static void premain(String args, Instrumentation inst) {
        var allLoadedClasses = inst.getAllLoadedClasses();
        FILE_WRITER.write("All Loaded classes");
        Arrays.stream(allLoadedClasses)
                .map(Class::getName)
                .forEach(s -> {
                    try {
                        FILE_WRITER.write(s);
                        FILE_WRITER.newLine();
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });
        options = AgentOptions.parse(args);
        PrintStream printStream = new PrintStream(
                new FileOutputStream("D://work/logs/flow.log", true)
        );
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            printStream.flush();
            printStream.close();
            try {
                FILE_WRITER.flush();
                FILE_WRITER.close();
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        }));
        AgentBuilder agentBuilder = new AgentBuilder.Default()
                //.with(new AgentBuilder.Listener.StreamWriting(printStream))
                .with(AgentBuilder.TypeStrategy.Default.REDEFINE)
                .ignore(
                        nameStartsWith("net.bytebuddy.")          // Игнорировать сам Byte Buddy
                                .or(nameStartsWith("org.slf4j."))          // Игнорировать логирование
                                .or(nameStartsWith("ru.dev.flow.")) // Игнорировать классы вашего агента
                )
                    .with(
                        new AgentBuilder.Listener.Adapter() {
                            @Override
                            public void onTransformation(TypeDescription typeDescription, ClassLoader classLoader, JavaModule module, boolean loaded, DynamicType dynamicType) {
                                try {
                                    FILE_WRITER.write("Transformed " + typeDescription);
                                    FILE_WRITER.newLine();
                                } catch (IOException e) {
                                    throw new RuntimeException(e);
                                }
                            }

                            @Override
                            public void onIgnored(TypeDescription typeDescription, ClassLoader classLoader, JavaModule module, boolean loaded) {
                                try {
                                    FILE_WRITER.write("Ignored " + typeDescription);
                                    FILE_WRITER.newLine();
                                } catch (IOException e) {
                                    throw new RuntimeException(e);
                                }
                            }

                            @Override
                            public void onDiscovery(String typeName, ClassLoader classLoader, JavaModule module, boolean loaded) {
                                try {
                                    FILE_WRITER.write("Discovered " + typeName);
                                    FILE_WRITER.newLine();
                                } catch (IOException e) {
                                    throw new RuntimeException(e);
                                }
                            }
                        }
                );
//                .type(nameContains("ru.alfabank"))
//                .transform((builder, type, classLoader, module, protectionDomain) ->
//                        builder.visit(Advice.to(FlowAdvice.class).on(isMethod()))
//                );
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
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.err.println("\n=== CALL GRAPH WRITE TO FILE ===");
            Json json = new Json(Events.events(), CONFIG.getStackOutput());
            json.write();
        }));
        if (options.isFlowRecording()) {
            var flowMethodMatchers = new FlowGenericMatchers.FlowMethodMatchers();
            var flowTypeMatchers = new FlowGenericMatchers.FlowTypeMatchers();
            var typeFilter = flowTypeMatchers.filter(CONFIG);
            System.err.println("Type filter " + typeFilter);
            var methodFilter = flowMethodMatchers.filter(CONFIG);
            System.err.println("Method filter " + methodFilter);
            agentBuilder = agentBuilder.type(typeFilter)
                    .transform((builder, type, loader, module, pd) ->
                            builder.visit(Advice.to(FlowAdvice.class)
                                            .on(isMethod().and(methodFilter))));
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
