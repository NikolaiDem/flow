# Flow MVP — Java Agent

Java-агент для записи JFR-событий инициализации Spring-контекста. Не требует изменения кода приложения.

## Что делает

Инструментирует `SpringApplication` и подменяет `ApplicationStartup` на `FlightRecorderApplicationStartup`. Всё, что происходит при загрузке Spring-контекста, попадает в JFR.

## Требования

- JDK 17+
- Maven 3.8+
- Spring Boot 2.5+

## Сборка

```bash
mvn clean install
```

Результат: `target/flow-mvp-1.0-SNAPSHOT.jar`

## Запуск

```bash
java -javaagent:/path/to/flow-mvp-1.0-SNAPSHOT.jar=<args> \
     -XX:StartFlightRecording:filename=context-startup.jfr,duration=60s \
     -jar your-application.jar
```

`-javaagent` должен идти **до** `-jar`. Без аргументов агент выключен.

## Включение Spring-инструментации

Добавьте флаг `spring-jfr=true`:

```bash
java -javaagent:/path/to/flow-mvp-1.0-SNAPSHOT.jar=spring-jfr=true \
     -XX:StartFlightRecording:filename=context-startup.jfr,duration=60s \
     -jar your-application.jar
```

> `spring-jfr=true` включает инструментацию, но JFR-запись нужно активировать отдельно через `-XX:StartFlightRecording`.

## Параметры

| Параметр         | По умолчанию | Описание                                |
|------------------|---|-----------------------------------------|
| `spring-jfr`     | `false` | Инструментирование `SpringApplication`. |
| `flow-recording` | `false` | Запись исполняющихся методов.           |

Параметры передаются через `-javaagent:agent.jar=key=value,key=value` или через `-Dflow.config="key=value,..."`. Аргументы `premain` имеют приоритет.

## Проверка
```

Результат — файл `context-startup.jfr`. Откройте в JDK Mission Control:

```bash
jmc context-startup.jfr
```

Ищите события `spring.context.refresh`, `spring.beans.instantiate`.

## Траблшутинг

| Проблема | Причина | Решение |
|---|---|---|
| `Failed to find Premain-Class` | Неверный `MANIFEST.MF` | Проверьте `Premain-Class` в манифесте |
| Трансформер не срабатывает | Classloader | Включите `verbose=true`, проверьте `transforming ...` |
| JFR-файл пустой | Нет `-XX:StartFlightRecording` или `spring-jfr=true` | Проверьте оба флага |
| `-Dflow.config` игнорируется | Заданы аргументы `premain` | Уберите один из источников |
| Конфликт с другими агентами | Порядок `-javaagent` | Ставьте Spring-агент после APM, до `-jar` |

## Итоговая команда

```bash
java \
  -javaagent:/path/to/flow-mvp-1.0-SNAPSHOT.jar=enabled=true,spring-jfr=true,flow-recording=true \
  -Dflow.config=D://work/config/config.yml
  -XX:StartFlightRecording:filename=context-startup.jfr\
  -jar your-application.jar
```



Добавить в pom.xml для записи деталиции spring контекстов в тестах

```xml
<dependency>
    <groupId>digital.pragmatech.testing</groupId>
    <artifactId>spring-test-profiler</artifactId>
    <version>0.4.0</version>
    <scope>test</scope>
</dependency>
```