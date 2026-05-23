package ru.dev.flow.filters;

import ru.dev.flow.config.FlowYamlConfig;
import ru.dev.flow.stack.CallNode;

import java.util.List;

import static ru.dev.flow.config.FlowConfig.CONFIG;

public class CallNodeFilter {

    public static boolean matches(CallNode callNode) {
        FlowYamlConfig.Match match = CONFIG.getInclude();
        if (match == FlowYamlConfig.Match.EMPTY) {
            return false;
        }
        String className = callNode.className();
        List<String> contains = match.getContains();
        for (var containsAny : contains) {
            if (className.contains(containsAny)) {
                return true;
            }
        }
        List<String> startOn = match.getStartOn();
        for (var containsAny : startOn) {
            if (className.startsWith(containsAny)) {
                return true;
            }
        }
        return false;
    }
}
