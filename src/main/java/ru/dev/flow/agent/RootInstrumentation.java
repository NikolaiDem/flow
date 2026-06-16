package ru.dev.flow.agent;

import io.opentelemetry.javaagent.extension.instrumentation.TypeInstrumentation;
import io.opentelemetry.javaagent.extension.instrumentation.TypeTransformer;
import net.bytebuddy.description.method.MethodDescription;
import net.bytebuddy.description.type.TypeDescription;
import net.bytebuddy.matcher.ElementMatcher;
import ru.dev.flow.filters.FlowGenericMatchers;

import static net.bytebuddy.matcher.ElementMatchers.*;
import static ru.dev.flow.config.FlowConfig.CONFIG;

public class RootInstrumentation implements TypeInstrumentation {

    private final FlowGenericMatchers<MethodDescription> flowMethodMatchers = new FlowGenericMatchers.FlowMethodMatchers();
    private final FlowGenericMatchers<TypeDescription> flowTypeMatchers = new FlowGenericMatchers.FlowTypeMatchers();

    @Override
    public ElementMatcher<TypeDescription> typeMatcher() {
        return flowTypeMatchers.filter(CONFIG);
    }

    @Override
    public void transform(TypeTransformer transformer) {
        transformer.applyAdviceToMethod(
                flowMethodMatchers.filter(CONFIG)
                        .and(not(isNative()))
                        .and(not(isConstructor())),
                RootAdvice.class.getName()
        );
    }
}