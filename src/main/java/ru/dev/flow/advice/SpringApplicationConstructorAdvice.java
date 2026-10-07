package ru.dev.flow.advice;

import net.bytebuddy.asm.Advice;

public class SpringApplicationConstructorAdvice {

    @Advice.OnMethodExit
    public static void onExit(@Advice.This Object application) {
        // application — это экземпляр SpringApplication, но мы НЕ ссылаемся на его тип
        try {
            // Загружаем класс FlightRecorderApplicationStartup через загрузчик application
            Class<?> startupClass = Class.forName(
                    "org.springframework.core.metrics.jfr.FlightRecorderApplicationStartup",
                    true,
                    application.getClass().getClassLoader()
            );

            Object startupInstance = startupClass.getDeclaredConstructor().newInstance();

            // Вызываем setApplicationStartup через рефлексию
            java.lang.reflect.Method setMethod = application.getClass()
                    .getMethod("setApplicationStartup",
                            Class.forName("org.springframework.core.metrics.ApplicationStartup",
                                    true,
                                    application.getClass().getClassLoader())
                    );

            setMethod.invoke(application, startupInstance);
            System.err.println("[SpringStartupJfrAgent] ApplicationStartup set via reflection");
        } catch (Throwable t) {
            System.err.println("[SpringStartupJfrAgent] Failed: " + t.getMessage());
        }
    }
}