1) Собрать java agent:
mvn clean install
2) Запускать приложение с агентом, добавить аргумент jvm при запуске jar:
-javaagent:flow-mvp-1.0-SNAPSHOT.jar
3) Указать -Dflow.config

Посмотреть класс после инструментации javaagent-ом
-Dnet.bytebuddy.dump=D://work/bytebudyy

# Включение junit jfr событий
Добавить в cmd запуска:
-XX:StartFlightRecording=filename=D:/work/jfr/recording-%p-%t.jfr 
-Djunit.jupiter.extensions.autodetection.enabled=true

org.junit.TestExecution - отслеживание выполнения тестового метода 

Преобразовать recording.jfr в json
jfr print --json --events "ru.dev.flow.advice.LogRecordingEvent" recording.jfr > output.json

Использовать jfr_test_intersection.py
