# JFR Test Overlap Analyzer

Инструмент для анализа пересечений тестов JUnit 5 на основе полётных записей Java Flight Recorder (JFR). Поднимает локальную веб-страницу с таймлайном выполнения тестов, распределением по потокам и списком пересекающихся пар.

---

## Возможности

- 🎯 Поиск пересекающихся пар тестов
- 📊 Таймлайн выполнения на общей шкале времени
- 🧵 Распределение по потокам
- 🔍 Поиск по названию теста
- 🎭 Демо-режим, если JFR-записей нет

---

## Требования

| Компонент | Версия |
|---|---|
| Python | 3.10+ |
| JDK | 17+ |
| JUnit | 5.x |

---

## Установка

```bash
git clone https://github.com/your-user/jfr-test-overlap.git
cd jfr-test-overlap

python -m venv .venv
source .venv/bin/activate    # Linux / macOS
.venv\Scripts\Activate.ps1   # Windows

pip install -r requirements.txt
```

---

## Настройка JUnit 5 для записи JFR

Для junit version<6 Добавьте в `pom.xml`:

```xml
<dependency>
    <groupId>org.junit.platform</groupId>
    <artifactId>junit-platform-jfr</artifactId>
    <version>1.14.4</version>
    <scope>test</scope>
</dependency>
```

Добавьте в команду запуска тестов следующие параметры JVM:

```
-XX:StartFlightRecording=filename=D:/work/jfr/recording-%p-%t.jfr
-Djunit.jupiter.extensions.autodetection.enabled=true
```

| Параметр | Назначение |
|---|---|
| `-XX:StartFlightRecording=filename=...` | Запускает запись JFR с момента старта JVM. `%p` — PID, `%t` — метка времени. |
| `-Djunit.jupiter.extensions.autodetection.enabled=true` | Автоподхват расширений JUnit 5 через `ServiceLoader`. |

Пример полной команды:

```bash
java \
  -XX:StartFlightRecording=filename=D:/work/jfr/recording-%p-%t.jfr \
  -Djunit.jupiter.extensions.autodetection.enabled=true \
  -jar junit-platform-console-standalone.jar \
  --scan-classpath
```

---

## Запуск

Задайте пути в `run.py`:

```python
jfr_dir = Path("D:/work/jfr")
json_dir = Path("D:/work/jfr/json")
```

- `jfr_dir` — каталог с `.jfr`-файлами;
- `json_dir` — каталог для JSON-версий записей.

Запустите:

```bash
python run.py
```

Скрипт парсит JFR-файлы, ищет пересечения и поднимает веб-страницу. Если JFR-файлов нет — используются демо-данные.

**Ожидаемый вывод:**

```
Найдены JFR-файлы, парсим...
Событий: 128
Пересекающихся пар: 17
```

---

## Что показывает страница

Для каждого совпадения отображается:

- **название теста** — полное имя (класс + метод);
- **таймлайн** — интервал выполнения на общей шкале времени;
- **поток** — идентификатор потока, в котором выполнялся тест.

Это позволяет быстро увидеть, какие тесты шли параллельно и где возникали пересечения во времени.

---

## Решение проблем

| Проблема | Решение |
|---|---|
| `JFR-файлы не найдены` | Добавьте `-XX:StartFlightRecording` в запуск тестов |
| `jfr: command not found` | Установите JDK 17+ и добавьте `bin/` в `PATH` |
| Пустой список событий | Проверьте автодетект расширений JUnit 5 |
| Порт занят | Укажите другой порт в `serve(...)` |

---