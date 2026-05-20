
package com.bank.flow;

import java.util.ArrayList;
import java.util.List;

public class CallNode {

    public String className;
    public String method;

    public long start;
    public long end;

    public CallNode parent;
    public List<CallNode> children = new ArrayList<>();

    public CallNode(String className, String method) {
        this.className = className;
        this.method = method;
        this.start = System.currentTimeMillis();
    }
}
