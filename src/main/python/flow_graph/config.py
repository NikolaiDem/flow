# config.py
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml


# ---------- Типы ----------

Node = tuple[str, str]


# ---------- Настройки по умолчанию ----------
# Меняются либо здесь, либо через config.yaml (секция flow),
# либо через переменные окружения (см. ALLOW_DEMO_FALLBACK).

OUTPUT_HTML     = Path("call_graph.html")
DEMO_SEED       = 42
SAVE_DEMO_JSON: Path | None = None
SHOW_FULL_CLASS = False
OPEN_BROWSER    = True
HIERARCHICAL    = True           # топологическая раскладка сверху вниз
PER_THREAD      = True
THREAD_MODE     = "border"       # "border" | "cluster" | "none"
SHOW_SEQUENTIAL = True

# Разрешать ли демо-режим, если конфиг вообще не задан или данных нет.
# В CI имеет смысл ставить False:
#   FLOW_ALLOW_DEMO=0 python build_graph.py
ALLOW_DEMO_FALLBACK = os.environ.get("FLOW_ALLOW_DEMO", "1") not in ("0", "false", "False")

# Палитра для раскраски потоков (циклически).
THREAD_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9a6324",
    "#fffac8", "#800000", "#aaffc3", "#808000", "#ffd8b1", "#000075",
]


# ---------- Исключения ----------

class ConfigNotFound(RuntimeError):
    """Конфиг не указан и не найден по дефолтному пути."""


# ---------- Определение пути к конфигу ----------

def resolve_config_path() -> Path | None:
    """
    Определяет путь к YAML-конфигу по приоритету:
      1. --config / -c в argv (явный CLI)   → файл обязан существовать
      2. переменная окружения FLOW_CONFIG   → файл обязан существовать
      3. ./config.yaml рядом                → если есть, берём
      4. ничего не найдено                  → возвращаем None (демо-режим)

    Возвращает None только в случае (4). Во всех остальных случаях
    возвращает абсолютный Path, существование которого гарантировано.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", "-c", type=Path, default=None)
    known, _ = parser.parse_known_args()

    # 1. Явный CLI
    if known.config is not None:
        p = known.config.expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(
                f"Конфиг указан явно (--config), но не найден: {p}"
            )
        print("[config] source: CLI (--config)", file=sys.stderr)
        return p

    # 2. Переменная окружения
    env_raw = os.environ.get("FLOW_CONFIG")
    if env_raw:
        p = Path(env_raw).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(
                f"Конфиг указан через FLOW_CONFIG, но не найден: {p}"
            )
        print("[config] source: env FLOW_CONFIG", file=sys.stderr)
        return p

    # 3. Дефолт рядом со скриптом / в cwd
    default = Path("config.yaml")
    if default.exists():
        p = default.resolve()
        print("[config] source: default ./config.yaml", file=sys.stderr)
        return p

    # 4. Ничего нет — демо-режим
    print("[config] source: none (config.yaml не найден)", file=sys.stderr)
    return None


# ---------- Чтение YAML ----------

def load_config(path: Path | None) -> dict | None:
    """
    Читает YAML. None → None (конфига нет, демо-режим).
    Существующий путь → dict. Битый YAML → ValueError.
    """
    if path is None:
        return None

    with path.open(encoding="utf-8-sig") as f:   # utf-8-sig — на случай BOM
        try:
            cfg = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"{path}: ошибка парсинга YAML: {e}") from e

    if not isinstance(cfg, dict):
        raise ValueError(f"{path}: корень YAML должен быть словарём")
    return cfg


# ---------- Валидация схемы ----------

def validate_config(cfg: dict | None) -> None:
    """
    Валидирует только если конфиг есть. None пропускаем — это демо-режим.
    Бросает ValueError с внятным сообщением при нарушении схемы.
    """
    if cfg is None:
        return

    flow = cfg.get("flow")
    if not isinstance(flow, dict):
        raise ValueError("config: отсутствует секция 'flow' (или она не словарь)")

    raw = flow.get("stack-output")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("config: flow.stack-output должен быть непустой строкой")


# ---------- Разрешение путей из конфига ----------

def get_stacks_dir(cfg: dict | None, config_path: Path | None) -> Path | None:
    """
    Возвращает абсолютный путь к директории стеков или None, если конфига нет.
    Относительные пути в YAML трактуются относительно директории конфига
    (а не cwd) — это предсказуемо при запуске из любого места.
    """
    if cfg is None or config_path is None:
        return None

    raw = cfg["flow"]["stack-output"]
    p = Path(raw)
    if not p.is_absolute():
        p = (config_path.parent / p).resolve()
    return p

def get_html_out_dir(cfg: dict | None, config_path: Path | None) -> Path:
    """
    Директория для HTML-файлов.
    Правило: <flow.stack-output>/html
    Если конфига нет — ./html рядом со скриптом (демо).
    """
    stacks_dir = get_stacks_dir(cfg, config_path)
    if stacks_dir is None:
        return Path("html").resolve()
    return (stacks_dir / "html").resolve()