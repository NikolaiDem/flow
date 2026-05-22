package ru.dev.flow.filters;

import ru.dev.flow.config.FlowYamlConfig;
import ru.dev.flow.stack.CallNode;

import java.util.List;

import static ru.dev.flow.config.FlowConfig.CONFIG;

public class CallNodeFilter {

    public static boolean matches(CallNode callNode) {
        FlowYamlConfig.Include include = CONFIG.getInclude();
        if (include == FlowYamlConfig.Include.EMPTY) {
            return false;
        }
        String className = callNode.className();
        List<String> contains = include.getContains();
        for (var containsAny : contains) {
            if (className.contains(containsAny)) {
                return true;
            }
        }
        List<String> startOn = include.getStartOn();
        for (var containsAny : startOn) {
            if (className.startsWith(containsAny)) {
                return true;
            }
        }
        return false;
    }
}
