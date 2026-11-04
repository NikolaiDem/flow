package ru.dev.flow.config;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public final class FlowLogger {

    public enum Level {ERROR, WARN, INFO, DEBUG}

    private static final DateTimeFormatter TS =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS");

    private static final DateTimeFormatter FILE_TS =
            DateTimeFormatter.ofPattern("yyyy-MM-dd_HH-mm-ss");

    private static final FlowLogger INSTANCE = bootstrap();

    private final BufferedWriter writer;   // null → консоль
    private final Level threshold;
    private final Object lock = new Object();
    private final String source;           // "console" | путь к файлу
    private volatile boolean closed;

    private FlowLogger(BufferedWriter writer, Level threshold, String source) {
        this.writer = writer;
        this.threshold = threshold;
        this.source = source;
    }

    private static FlowLogger bootstrap() {
        Path file = resolveLogPath();
        if (file == null) {
            return new FlowLogger(null, Level.INFO, "console");
        }
        try {
            Path parent = file.toAbsolutePath().getParent();
            if (parent != null) Files.createDirectories(parent);
            BufferedWriter w = Files.newBufferedWriter(file, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            return new FlowLogger(w, Level.INFO, file.toAbsolutePath().toString());
        } catch (Exception e) {
            System.err.println("[flow-agent] Cannot open log file: " + file
                    + " (" + e.getMessage() + "). Logging to console");
            return new FlowLogger(null, Level.INFO, "console");
        }
    }

    public static FlowLogger get() {
        return INSTANCE;
    }

    public void error(String msg) { log(Level.ERROR, msg, null); }
    public void warn(String msg)  { log(Level.WARN,  msg, null); }
    public void info(String msg)  { log(Level.INFO,  msg, null); }
    public void debug(String msg) { log(Level.DEBUG, msg, null); }
    public void error(String msg, Throwable t) { log(Level.ERROR, msg, t); }

    private void log(Level level, String msg, Throwable t) {
        if (level.ordinal() > threshold.ordinal()) return;
        if (closed) return;

        String line = TS.format(LocalDateTime.now()) + " [" + level + "] " + msg;

        // ERROR/WARN всегда в stderr, независимо от writer'а
        if (level == Level.ERROR || level == Level.WARN) {
            System.err.println(line);
            if (t != null) t.printStackTrace(System.err);
        }

        if (writer == null) {
            // консольный режим: INFO/DEBUG → stdout
            if (level == Level.INFO || level == Level.DEBUG) {
                System.out.println(line);
            }
            return;
        }

        synchronized (lock) {
            try {
                writer.write(line);
                writer.newLine();
                if (t != null) writer.write(stackTraceToString(t));
                writer.flush();
            } catch (IOException e) {
                System.err.println("[flow-agent] Log write failed: " + e.getMessage());
                closed = true;
            }
        }
    }

    public void close() {
        if (writer == null) return;
        synchronized (lock) {
            if (closed) return;
            closed = true;
            try {
                writer.flush();
                writer.close();
            } catch (IOException ignored) { }
        }
    }

    public String source() {
        return source;
    }

    private static String stackTraceToString(Throwable t) {
        java.io.StringWriter sw = new java.io.StringWriter();
        t.printStackTrace(new java.io.PrintWriter(sw));
        return sw.toString();
    }

    // ---------- resolve ----------

    /**
     * Возвращает полный путь к лог-файлу или null (тогда пишем в консоль).
     * Приоритет: bootstrap.log-dir (YAML) → -Dflow.log → консоль.
     */
    private static Path resolveLogPath() {
        // 1. YAML: bootstrap.log-dir (директория) — имя генерируется
        String dirFromYaml = null;
        try {
            dirFromYaml = FlowConfig.get().getBootstrap().getLogDir();
        } catch (Throwable t) {
            System.err.println("[flow-agent] Cannot read config for log dir: " + t.getMessage());
        }
        if (dirFromYaml != null && !dirFromYaml.isBlank()) {
            return buildLogFile("yaml", dirFromYaml);
        }

        // 2. -Dflow.log (полный путь к файлу — override)
        String fromSys = System.getProperty("flow.log");
        if (fromSys != null && !fromSys.isBlank()) {
            return logResolvedPath("system property", fromSys);
        }

        // 3. ничего не задано — консоль
        System.err.println("[flow-agent] Log dir not set, logging to console");
        return null;
    }

    /** Строит путь: директория + flow-agent-<timestamp>.log */
    private static Path buildLogFile(String source, String dirValue) {
        try {
            Path dir = Path.of(dirValue.trim());
            String fileName = "flow-agent-" + FILE_TS.format(LocalDateTime.now()) + ".log";
            Path file = dir.resolve(fileName);
            System.err.println("[flow-agent] Log file (" + source + "): " + file.toAbsolutePath());
            return file;
        } catch (InvalidPathException e) {
            System.err.println("[flow-agent] Invalid log dir: \"" + dirValue
                    + "\" (" + e.getMessage() + "). Logging to console");
            return null;
        }
    }

    /** Для -Dflow.log: трактуем как полный путь к файлу. */
    private static Path logResolvedPath(String source, String value) {
        try {
            Path p = Path.of(value.trim());
            System.err.println("[flow-agent] Log file (" + source + "): " + p);
            return p;
        } catch (InvalidPathException e) {
            System.err.println("[flow-agent] Invalid log path: \"" + value
                    + "\" (" + e.getMessage() + "). Logging to console");
            return null;
        }
    }
}