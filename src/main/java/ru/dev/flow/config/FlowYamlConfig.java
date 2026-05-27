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

    @JsonProperty("stack-output")
    private String stackOutput;

    private Type type;
    private Type method;

    @Setter
    @Getter
    public static class Type {

        private Match include = Match.EMPTY;
        private Match exclude = Match.EMPTY;
    }

    @Setter
    @Getter
    public static class Match {

        public static final Match EMPTY = new Match();

        @JsonProperty("start-on")
        private List<String> startOn = List.of();

        private List<String> contains = List.of();

        private List<String> equals = List.of();

        private boolean synthetic = false;
    }
}