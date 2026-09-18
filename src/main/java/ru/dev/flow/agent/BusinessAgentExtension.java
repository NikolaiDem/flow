package ru.dev.flow.agent;

import io.opentelemetry.javaagent.extension.instrumentation.InstrumentationModule;
import io.opentelemetry.javaagent.extension.instrumentation.TypeInstrumentation;
import net.bytebuddy.matcher.ElementMatcher;

import java.util.List;

import static net.bytebuddy.matcher.ElementMatchers.any;

public class BusinessAgentExtension extends InstrumentationModule {

    public BusinessAgentExtension() {
        super("business-agent");
        System.out.println(BusinessAgentExtension.class);
    }

    @Override
    public ElementMatcher.Junction<ClassLoader> classLoaderMatcher() {
        return any();
    }

    @Override
    public List<TypeInstrumentation> typeInstrumentations() {
        return List.of(new RootInstrumentation());
    }
}