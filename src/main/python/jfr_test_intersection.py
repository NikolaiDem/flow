# Начиная с версии junit-platform-launcher-6.0.3.jar
# Преобразовать recording.jfr в json
# jfr print --json --events "ru.dev.flow.advice.LogRecordingEvent" recording.jfr > output.json
# Структура event:
# "type": "org.junit.TestExecution",
#       "values": {
#         "startTime": "2026-10-01T17:50:51.628035091+03:00",
#         "duration": "PT4.809288896S",
#         "eventThread": {
#           "osName": "ForkJoinPool-1-worker-4",
#           "osThreadId": 14896,
#           "javaName": "ForkJoinPool-1-worker-4",
#           "javaThreadId": 56,
#           "group": {
#             "parent": {
#               "parent": null,
#               "name": "system"
#             },
#             "name": "main"
#           },
#           "virtual": false
#         },
#         "stackTrace": null,
#         "result": "SUCCESSFUL",
#         "exceptionClass": null,
#         "exceptionMessage": null,
#         "uniqueId": "[engine:junit-jupiter]\/[class:ru.alfabank.pc.api.diva.repo.CardOwnersTest]\/[method:cardOwnersByReqAmtWithIssAcctNumStartedWithPOOL()]",
#         "displayName": "\u0412 \u0432\u044b\u0431\u043e\u0440\u043a\u0443 \u043f\u043e\u043f\u0430\u0434\u0430\u044e\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438, \u0443 \u043a\u043e\u0442\u043e\u0440\u044b\u0445 iss_acct_num \u043d\u0435 \u043d\u0430\u0447\u0438\u043d\u0430\u0435\u0442\u0441\u044f \u0441 POOL (\u0437\u0430\u043f\u0440\u043e\u0441 \u0431\u0435\u0437 \u0424\u0418\u041e). ~48\u0441\u0435\u043a",
#         "tags": null,
#         "type": "TEST"
#       }
#     }

import isodate
from dateutil import parser
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import subprocess
from pathlib import Path

TEST_EVENT_TYPE = "org.junit.TestExecution"

def format_to_json(jfr_dir, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for jfr_file in sorted(jfr_dir.glob("*.jfr")):
        out_file = out_dir / (jfr_file.stem + ".json")
        cmd = ["jfr", "print", "--json", "--events", TEST_EVENT_TYPE, str(jfr_file)]
        print(f"Processing: {jfr_file.name} -> {out_file.name}")

        with open(out_file, "w", encoding="utf-8") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            out_file.unlink(missing_ok=True)
        else:
            print("  OK")


def parse_event(raw: dict) -> dict:
    v = raw["values"]
    event = {
        "threadName": v["eventThread"]["javaName"],
        "displayName": v["displayName"],
        "startTime": parser.isoparse(v["startTime"]),
        "duration": isodate.parse_duration(v["duration"]),
    }
    print(event)
    return event


def parse_file(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        parse_event(e)
        for e in data["recording"]["events"]
        # e["values"]["type"] может быть TEST или CONTAINER
        if e.get("type") == TEST_EVENT_TYPE and e["values"]["type"] == "TEST"
    ]


def collect_all(json_dir: Path) -> list[dict]:
    all_events = []
    for json_file in sorted(json_dir.glob("*.json")):
        try:
            all_events.extend(parse_file(json_file))
        except Exception as e:
            print(f"ERROR {json_file.name}: {e}")
    return all_events


def find_overlaps(events: list[dict]) -> list[tuple[dict, dict]]:
    """Возвращает все пары событий, чьи интервалы пересекаются."""
    points = []
    for i, e in enumerate(events):
        start = e["startTime"]
        end = start + e["duration"]
        points.append((start, 1, i))   # начало: +1
        points.append((end, -1, i))    # конец: -1

    # сортировка: по времени, концы раньше начал (при равенстве — касание не считаем пересечением)
    points.sort(key=lambda p: (p[0], p[1]))

    active = set()
    overlaps = []
    for t, delta, i in points:
        if delta == 1:
            for j in active:
                overlaps.append((events[j], events[i]))
            active.add(i)
        else:
            active.discard(i)
    return overlaps


if __name__ == "__main__":
    jfr_path = Path("D:/work/jfr")
    json_path = Path("D:/work/jfr/json")
    format_to_json(jfr_path, json_path)
    all_events = collect_all(Path("D:/work/jfr/json"))
    overlaps = find_overlaps(all_events)
    print('OVERLAPS')
    print(overlaps)
    print(f"events size {len(all_events)}")
    print(f"overlaps size {len(overlaps)}")
