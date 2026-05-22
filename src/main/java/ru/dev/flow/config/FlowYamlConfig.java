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

    private Include include = Include.EMPTY;
    private Exclude exclude = Exclude.EMPTY;

    @Setter
    @Getter
    public static class Include {

        public static final Include EMPTY = new Include();

        @JsonProperty("start-on")
        private List<String> startOn = List.of();

        private List<String> contains = List.of();

    }

    @Setter
    @Getter
    public static class Exclude {

        public static final Exclude EMPTY = new Exclude();

        @JsonProperty("start-on")
        private List<String> startOn = List.of();

        private List<String> contains = List.of();

    }
}