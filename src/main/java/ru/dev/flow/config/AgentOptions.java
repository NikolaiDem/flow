package ru.dev.flow.config;

public final class AgentOptions {

    private final boolean springJfr;
    private final boolean verbose;
    private final String recordingName;
    private final boolean failOnError;

    private AgentOptions(Builder b) {
        this.springJfr = b.springJfr;
        this.verbose = b.verbose;
        this.recordingName = b.recordingName;
        this.failOnError = b.failOnError;
    }

    public boolean isSpringJfr() { return springJfr; }
    public boolean isVerbose() { return verbose; }
    public String getRecordingName() { return recordingName; }
    public boolean isFailOnError() { return failOnError; }

    public static AgentOptions parse(String args) {
        Builder b = new Builder();
        if (args == null || args.isBlank()) {
            return b.build();
        }

        for (String token : args.split(",")) {
            String trimmed = token.trim();
            if (trimmed.isEmpty()) {
                continue;
            }

            // Краткая форма: "true" без ключа
            if (!trimmed.contains("=")) {
                b.springJfr = Boolean.parseBoolean(trimmed);
                continue;
            }

            String[] kv = trimmed.split("=", 2);
            String key = kv[0].trim().toLowerCase();
            String value = kv[1].trim();

            switch (key) {
                case "spring-jfr"        -> b.springJfr = Boolean.parseBoolean(value);
                case "verbose"        -> b.verbose = Boolean.parseBoolean(value);
                case "recording-name" -> b.recordingName = value;
                case "fail-on-error"  -> b.failOnError = Boolean.parseBoolean(value);
                default -> {
                    // Неизвестные ключи игнорируем, но сообщаем при verbose
                    b.unknownKeys.add(key);
                }
            }
        }
        return b.build();
    }

    public static final class Builder {
        private boolean springJfr = false;
        private boolean verbose = false;
        private String recordingName = "spring-context-startup";
        private boolean failOnError = false;
        private final java.util.List<String> unknownKeys = new java.util.ArrayList<>();

        public AgentOptions build() { return new AgentOptions(this); }
    }

    @Override
    public String toString() {
        return "AgentOptions{enabled=" + springJfr + ", verbose=" + verbose +
               ", recordingName='" + recordingName + "', failOnError=" + failOnError + '}';
    }
}