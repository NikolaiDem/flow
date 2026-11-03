package ru.dev.flow.config;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;

import java.io.InputStream;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;

public final class FlowConfig {

    private static final ObjectMapper MAPPER = new ObjectMapper(new YAMLFactory())
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    /** Eager: читается при загрузке класса, до первого get(). */
    private static final FlowYamlConfig INSTANCE = load();

    private FlowConfig() {}

    /** Всегда возвращает не-null конфиг: реальный или дефолтный. */
    public static FlowYamlConfig get() {
        return INSTANCE;
    }

    private static FlowYamlConfig load() {
        Path path = resolvePath();
        if (path == null) {
            System.err.println("[flow-agent] Config not found. Using defaults");
            return new FlowYamlConfig();
        }

        try (InputStream in = open(path)) {
            FlowYamlConfig cfg = MAPPER.readValue(in, FlowYamlConfig.class);
            System.err.println("[flow-agent] Config loaded from " + path);
            return cfg;

        } catch (NoSuchFileException e) {
            System.err.println("[flow-agent] File not found: " + path + ". Check FLOW_AGENT_CONFIG");
        } catch (AccessDeniedException e) {
            System.err.println("[flow-agent] Not readable: " + path + ". Check file permissions");
        } catch (Exception e) {
            System.err.println("[flow-agent] Failed to read config: " + e.getMessage() + ". Using defaults");
        }
        return new FlowYamlConfig();
    }

    /**
     * Возвращает путь из -Dflow.config или FLOW_AGENT_CONFIG, либо null.
     * null означает «использовать дефолты» (не бросаем исключение).
     */
    private static Path resolvePath() {
        String raw = System.getProperty("flow.config");
        if (raw == null || raw.isBlank()) {
            raw = System.getenv("FLOW_AGENT_CONFIG");
        }
        if (raw == null || raw.isBlank()) {
            return null;
        }
        try {
            return Path.of(raw.trim());
        } catch (InvalidPathException e) {
            System.err.println("[flow-agent] Invalid path: \"" + raw + "\". Check FLOW_AGENT_CONFIG");
            return null;
        }
    }

    private static InputStream open(Path path) throws Exception {
        return Files.newInputStream(path);
    }
}