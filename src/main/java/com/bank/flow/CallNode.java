package com.bank.flow;

import lombok.ToString;

import java.util.ArrayList;
import java.util.List;

@ToString
public class CallNode {

    public final String className;
    public final String methodName;

    public CallNode parent;
    public final List<CallNode> children = new ArrayList<>();

    public long start;
    public long end;

    public CallNode(String className, String methodName) {
        this.className = className;
        this.methodName = methodName;
        this.start = System.currentTimeMillis();
    }

    public long duration() {
        return end - start;
    }

    public String label() {
        return className + "#" + methodName;
    }
}