package ru.dev.flow.filters;

import net.bytebuddy.matcher.ElementMatcher;
import ru.dev.flow.config.FlowYamlConfig;

import java.util.List;

import static net.bytebuddy.matcher.ElementMatchers.*;

public class FlowMatchers {

    public static ElementMatcher.Junction<? super net.bytebuddy.description.type.TypeDescription>
    typeFilter(FlowYamlConfig cfg) {

        ElementMatcher.Junction<? super net.bytebuddy.description.type.TypeDescription>
                includeMatcher = buildMatcher(cfg.getInclude());

        ElementMatcher.Junction<? super net.bytebuddy.description.type.TypeDescription>
                excludeMatcher = buildMatcherExclude(cfg.getExclude());

        // include AND NOT exclude
        return includeMatcher.and(not(excludeMatcher));
    }

    private static ElementMatcher.Junction<? super net.bytebuddy.description.type.TypeDescription>
    buildMatcher(FlowYamlConfig.Match cfg) {

        // если секция пустая → any()
        if (cfg == null ||
                (isEmpty(cfg.getStartOn()) && isEmpty(cfg.getContains()))) {
            return any();
        }

        ElementMatcher.Junction<? super net.bytebuddy.description.type.TypeDescription>
                matcher = none();

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

    private static ElementMatcher.Junction<? super net.bytebuddy.description.type.TypeDescription>
    buildMatcherExclude(FlowYamlConfig.Match cfg) {

        // exclude пустой → none()
        if (cfg == null ||
                (isEmpty(cfg.getStartOn()) && isEmpty(cfg.getContains()))) {
            return none();
        }

        ElementMatcher.Junction<? super net.bytebuddy.description.type.TypeDescription>
                matcher = none();

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

        if (cfg.isSynthetic()) {
            matcher = matcher.or(isSynthetic());
        }

        return matcher;
    }

    private static boolean isEmpty(List<String> list) {
        return list == null || list.isEmpty();
    }
}