package ru.dev.flow.output;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import lombok.RequiredArgsConstructor;
import lombok.SneakyThrows;

import java.nio.file.Path;

@RequiredArgsConstructor
public class Json {

    private static final ObjectMapper mapper = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);
    private final Object object;
    private final String path;

    @SneakyThrows
    public void write() {
        mapper.writeValue(Path.of(path).toFile(), object);
    }
}
