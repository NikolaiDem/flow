package ru.dev.flow.filters;

import net.bytebuddy.description.NamedElement;
import net.bytebuddy.description.method.MethodDescription;
import net.bytebuddy.description.type.TypeDescription;
import net.bytebuddy.matcher.ElementMatcher;
import ru.dev.flow.config.FlowYamlConfig;

import static net.bytebuddy.matcher.ElementMatchers.*;
import static org.apache.commons.collections4.CollectionUtils.isEmpty;

public interface FlowGenericMatchers<T extends NamedElement> {

    default ElementMatcher.Junction<T> filter(FlowYamlConfig.Type type) {
        var includeMatcher = buildMatcher(type.getInclude());
        var excludeMatcher = buildMatcherExclude(type.getExclude());
        // include AND NOT exclude
        return includeMatcher.and(not(excludeMatcher));
    }

    ElementMatcher.Junction<T> filter(FlowYamlConfig cfg);

    private ElementMatcher.Junction<T> buildMatcher(FlowYamlConfig.Match cfg) {
        // если секция пустая → any()
        if (cfg == null ||
                (isEmpty(cfg.getStartOn()) && isEmpty(cfg.getContains()))) {
            return any();
        }

        ElementMatcher.Junction<T> matcher = none();

        // start-on → nameStartsWith
        if (!isEmpty(cfg.getStartOn())) {
            for (String prefix : cfg.getStartOn()) {
                matcher = matcher.or(nameStartsWith(prefix));
            }
        }

        // contains → nameContains
        if (!isEmpty(cfg.getContains())) {
            for (String part : cfg.getContains()) {
                matcher = matcher.or(nameContains(part));
            }
        }

        return matcher;
    }

    private ElementMatcher.Junction<T> buildMatcherExclude(FlowYamlConfig.Match cfg) {
        // exclude пустой → none()
        if (cfg == null ||
                (isEmpty(cfg.getStartOn()) && isEmpty(cfg.getContains()))) {
            return none();
        }
        ElementMatcher.Junction<T> matcher = none();
        if (!isEmpty(cfg.getStartOn())) {
            for (String prefix : cfg.getStartOn()) {
                matcher = matcher.or(nameStartsWith(prefix));
            }
        }

        if (!isEmpty(cfg.getContains())) {
            for (String part : cfg.getContains()) {
                matcher = matcher.or(nameContains(part));
            }
        }

        if (!isEmpty(cfg.getEquals())) {
            for (String part : cfg.getEquals()) {
                matcher = matcher.or(named(part));
            }
        }

        return matcher;
    }

    class FlowMethodMatchers implements FlowGenericMatchers<MethodDescription> {
        @Override
        public ElementMatcher.Junction<MethodDescription> filter(FlowYamlConfig cfg) {
            return filter(cfg.getMethod());
        }
    }

    class FlowTypeMatchers implements FlowGenericMatchers<TypeDescription> {
        @Override
        public ElementMatcher.Junction<TypeDescription> filter(FlowYamlConfig cfg) {
            return filter(cfg.getType());
        }
    }
}