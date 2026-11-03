package ru.dev.flow.output;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import lombok.RequiredArgsConstructor;
import ru.dev.flow.config.FlowLogger;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@RequiredArgsConstructor
public class Json {

    private static final FlowLogger log = FlowLogger.get();
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    private static final DateTimeFormatter FILE_TS =
            DateTimeFormatter.ofPattern("yyyy-MM-dd_HH-mm-ss");

    private final Object object;

    /** Директория для записи. Имя файла формируется по текущему времени. */
    private final Path directory;

    public void write() {
        String fileName = "flow-stack-" + FILE_TS.format(LocalDateTime.now()) + ".json";
        Path file = directory.resolve(fileName);

        try {
            Files.createDirectories(directory);
            MAPPER.writeValue(file.toFile(), object);
            log.debug("[flow-agent] Stack written: " + file.toAbsolutePath());
        } catch (IOException e) {
            log.error("[flow-agent] Failed to write stack: " + file
                    + " (" + e.getMessage() + ")");
        }
    }
}