import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("analyze_jfr")

# --------------------------------------------------------------------------- #
# Конвертация JFR -> JSON
# --------------------------------------------------------------------------- #
def jfr_to_json(jfr_dir: Path, out_dir: Path, *, force: bool = False) -> None:
    """Конвертирует все *.jfr в out_dir/*.json через `jfr print`."""
    out_dir.mkdir(parents=True, exist_ok=True)

    jfr_files = sorted(jfr_dir.glob("*.jfr"))
    if not jfr_files:
        log.warning("В %s не найдено ни одного .jfr файла", jfr_dir)
        return

    for jfr_file in jfr_files:
        out_file = out_dir / (jfr_file.stem + ".json")

        # Пропускаем, если JSON свежее исходного JFR
        if (
            not force
            and out_file.exists()
            and out_file.stat().st_mtime >= jfr_file.stat().st_mtime
        ):
            log.info("Skip (up to date): %s", out_file.name)
            continue

        cmd = [
            "jfr", "print",
            "--json",
            #"--events", TEST_EVENT_TYPE,
            str(jfr_file),
        ]
        log.info("Converting: %s -> %s", jfr_file.name, out_file.name)

        try:
            with open(out_file, "w", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    check=False,
                )
        except FileNotFoundError:
            log.error("Команда 'jfr' не найдена. Установите JDK (jfr в PATH).")
            sys.exit(1)

        if result.returncode != 0:
            log.error("jfr failed: %s", result.stderr.strip())
            out_file.unlink(missing_ok=True)
        else:
            log.info("  OK")

