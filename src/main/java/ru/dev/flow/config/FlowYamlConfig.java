package ru.dev.flow.config;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;

import java.util.List;

@Setter
@Getter
@ToString
public class FlowYamlConfig {

    private Bootstrap bootstrap = new Bootstrap();
    private Agent agent = new Agent();
    private Flow flow = new Flow();

    // ---------- bootstrap: пути ----------

    @Setter
    @Getter
    @ToString
    public static class Bootstrap {

        @JsonProperty("log-file")
        private String logFile;

        @JsonProperty("jfr-file")
        private String jfrFile;
    }

    // ---------- agent: флаги поведения ----------

    @Setter
    @Getter
    @ToString
    public static class Agent {

        @JsonProperty("spring-jfr")
        private Boolean springJfr;

        @JsonProperty("flow-recording")
        private Boolean flowRecording;

        private Boolean verbose;
    }

    // ---------- flow: stack-output + правила ----------

    @Setter
    @Getter
    @ToString
    public static class Flow {

        @JsonProperty("stack-output")
        private String stackOutput;

        private Type type = new Type();
        private Type method = new Type();
    }

    // ---------- type / method ----------

    @Setter
    @Getter
    @ToString
    public static class Type {

        private Match include = new Match();
        private Match exclude = new Match();
    }

    @Setter
    @Getter
    @ToString
    public static class Match {

        public static final Match EMPTY = new Match();

        @JsonProperty("start-on")
        private List<String> startOn = List.of();

        private List<String> contains = List.of();

        private List<String> equals = List.of();

        private boolean synthetic = false;
    }
}