1) Собрать java agent:
mvn clean install
2) Запускать приложение с агентом, добавить аргумент jvm при запуске jar:
-javaagent:flow-mvp-1.0-SNAPSHOT.jar