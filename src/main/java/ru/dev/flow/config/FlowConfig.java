package ru.dev.flow.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;

import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;

import static com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES;

public class FlowConfig {

    public static final FlowYamlConfig CONFIG = load();

    public static FlowYamlConfig load() {
        try {
            String path = System.getProperty("flow.config");

            InputStream in;

            if (path != null) {
                in = Files.newInputStream(Path.of(path));
            } else {
                in = FlowConfig.class.getClassLoader()
                        .getResourceAsStream("config.yaml");
            }

            ObjectMapper mapper = new ObjectMapper(new YAMLFactory());
            mapper.configure(FAIL_ON_UNKNOWN_PROPERTIES, false);

            return mapper.readValue(in, FlowYamlConfig.class);

        } catch (Exception e) {
            throw new RuntimeException("Failed to load YAML config", e);
        }
    }
}