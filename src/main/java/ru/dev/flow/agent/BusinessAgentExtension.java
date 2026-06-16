package ru.dev.flow.agent;

import io.opentelemetry.javaagent.extension.instrumentation.InstrumentationModule;
import io.opentelemetry.javaagent.extension.instrumentation.TypeInstrumentation;
import net.bytebuddy.matcher.ElementMatcher;

import java.util.List;

import static io.opentelemetry.javaagent.extension.matcher.AgentElementMatchers.hasClassesNamed;

public class BusinessAgentExtension extends InstrumentationModule {

    protected BusinessAgentExtension(String mainInstrumentationName, String... additionalInstrumentationNames) {
        super(mainInstrumentationName, additionalInstrumentationNames);
    }

    @Override
    public ElementMatcher.Junction<ClassLoader> classLoaderMatcher() {
        return hasClassesNamed("javax.servlet.http.HttpServlet");
    }

    @Override
    public List<TypeInstrumentation> typeInstrumentations() {
        return List.of();
    }
}