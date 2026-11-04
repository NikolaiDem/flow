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
            DateTimeFormatter.ofPattern("yyyy-MM-dd_HH-mm-ss-SSS");

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

    // ---------- bootstrap ----------

    private static FlowLogger bootstrap() {
        Level level = resolveLevel();
        Path file = resolveLogPath();

        if (file == null) {
            System.err.println("[flow-agent] Logging to console, level=" + level);
            return new FlowLogger(null, level, "console");
        }

        try {
            Path parent = file.toAbsolutePath().getParent();
            if (parent != null) Files.createDirectories(parent);
            BufferedWriter w = Files.newBufferedWriter(file, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            System.err.println("[flow-agent] Log file: " + file.toAbsolutePath()
                    + ", level=" + level);
            return new FlowLogger(w, level, file.toAbsolutePath().toString());
        } catch (Exception e) {
            System.err.println("[flow-agent] Cannot open log file: " + file
                    + " (" + e.getMessage() + "). Logging to console, level=" + level);
            return new FlowLogger(null, level, "console");
        }
    }

    // ---------- resolve: level ----------

    /**
     * Приоритет: -Dflow.log.level → bootstrap.log-level (YAML) → INFO.
     */
    private static Level resolveLevel() {
        String fromSys = System.getProperty("flow.log.level");
        if (fromSys != null && !fromSys.isBlank()) {
            Level parsed = parseLevel("system property", fromSys);
            if (parsed != null) return parsed;
        }

        String fromYaml = null;
        try {
            fromYaml = FlowConfig.get().getBootstrap().getLogLevel();
        } catch (Throwable t) {
            System.err.println("[flow-agent] Cannot read log level from config: " + t.getMessage());
        }
        if (fromYaml != null && !fromYaml.isBlank()) {
            Level parsed = parseLevel("yaml", fromYaml);
            if (parsed != null) return parsed;
        }

        return Level.INFO;
    }

    private static Level parseLevel(String source, String raw) {
        try {
            Level lvl = Level.valueOf(raw.trim().toUpperCase());
            System.err.println("[flow-agent] Log level (" + source + "): " + lvl);
            return lvl;
        } catch (IllegalArgumentException e) {
            System.err.println("[flow-agent] Invalid log-level: \"" + raw
                    + "\" (" + source + "). Expected ERROR|WARN|INFO|DEBUG");
            return null;
        }
    }

    // ---------- resolve: path ----------

    /**
     * Приоритет: bootstrap.log-dir (YAML) → -Dflow.log → консоль.
     * Если задана директория — имя файла генерируется по timestamp.
     */
    private static Path resolveLogPath() {
        String dirFromYaml = null;
        try {
            dirFromYaml = FlowConfig.get().getBootstrap().getLogDir();
        } catch (Throwable t) {
            System.err.println("[flow-agent] Cannot read log dir from config: " + t.getMessage());
        }
        if (dirFromYaml != null && !dirFromYaml.isBlank()) {
            return buildLogFile("yaml", dirFromYaml);
        }

        String fromSys = System.getProperty("flow.log");
        if (fromSys != null && !fromSys.isBlank()) {
            return logResolvedPath("system property", fromSys);
        }

        return null;
    }

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

    // ---------- public API ----------

    public static FlowLogger get() {
        return INSTANCE;
    }

    public void error(String msg) { log(Level.ERROR, msg, null); }
    public void warn(String msg)  { log(Level.WARN,  msg, null); }
    public void info(String msg)  { log(Level.INFO,  msg, null); }
    public void debug(String msg) { log(Level.DEBUG, msg, null); }

    public void error(String msg, Throwable t) { log(Level.ERROR, msg, t); }
    public void warn(String msg, Throwable t)  { log(Level.WARN,  msg, t); }
    public void info(String msg, Throwable t)  { log(Level.INFO,  msg, t); }
    public void debug(String msg, Throwable t) { log(Level.DEBUG, msg, t); }

    /** Быстрая проверка без аллокаций — для горячих путей (FlowAdvice). */
    public boolean isDebugEnabled() { return Level.DEBUG.ordinal() <= threshold.ordinal(); }
    public boolean isInfoEnabled()  { return Level.INFO.ordinal()  <= threshold.ordinal(); }
    public boolean isWarnEnabled()  { return Level.WARN.ordinal()  <= threshold.ordinal(); }
    public boolean isErrorEnabled() { return Level.ERROR.ordinal() <= threshold.ordinal(); }

    public String source() { return source; }
    public Level threshold() { return threshold; }

    // ---------- core ----------

    private void log(Level level, String msg, Throwable t) {
        if (level.ordinal() > threshold.ordinal()) return;
        if (closed) return;

        String line = TS.format(LocalDateTime.now()) + " [" + level + "] " + msg;

        // ERROR/WARN всегда дублируем в stderr
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

    private static String stackTraceToString(Throwable t) {
        java.io.StringWriter sw = new java.io.StringWriter();
        t.printStackTrace(new java.io.PrintWriter(sw));
        return sw.toString();
    }
}