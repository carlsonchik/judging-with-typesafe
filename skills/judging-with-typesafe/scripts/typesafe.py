#!/usr/bin/env python3
"""Обёртка над TypeSafe System One (Jev) для суждений по критериям.

Ключ берётся из TYPESAFE_API_KEY через свежий логин-шелл, чтобы работать
даже когда приложение запущено со старым окружением.

Использование:
    python3 typesafe.py noul  "состояние" "вопрос"
    python3 typesafe.py choice "состояние" "вопрос" -o вариант1 вариант2 вариант3
    python3 typesafe.py score  "состояние" "вопрос" -o уровень1 уровень2 уровень3
    python3 typesafe.py batch  state.txt questions.json       # много вопросов на одном состоянии
"""
import json, subprocess, sys, argparse

API = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"


def _call(payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).replace("'", "'\\''")
    cmd = [
        "zsh", "-lic",
        f'''curl -s --max-time 120 -X POST "{API}" '''
        f'''-H "Authorization: Bearer $TYPESAFE_API_KEY" '''
        f'''-H "Content-Type: application/json" -d '{data}' '''
    ]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return {"error": f"не разобрать ответ: {out[:300]}"}


def ask(state, questions: dict) -> dict:
    """Один запрос: состояние + карта типизированных вопросов."""
    return _call({"state": state, "model": MODEL, "questions": questions})


def noul(state, instructions, criteria=None):
    """Вероятность «да» 0..1. Близко к 0.5 — неопределённость, а не «средне»."""
    q = {"type": "noul", "instructions": instructions}
    if criteria:
        q["criteria"] = criteria                      # {"true": "...", "false": "..."}
    r = ask(state, {"q": q})
    a = (r.get("answers") or {}).get("q") or {}
    return a.get("noul"), r


def choice(state, instructions, options):
    """Выбор одного варианта. Возвращает (вариант, вероятности, уверенность)."""
    r = ask(state, {"q": {"type": "choice", "instructions": instructions, "criteria": list(options)}})
    a = (r.get("answers") or {}).get("q") or {}
    return a.get("choice"), a.get("probabilities"), a.get("confidence"), r


def score(state, instructions, levels):
    """Позиция на упорядоченной шкале. criteria обязан быть СПИСКОМ, иначе 422."""
    r = ask(state, {"q": {"type": "score", "instructions": instructions, "criteria": list(levels)}})
    a = (r.get("answers") or {}).get("q") or {}
    return a.get("score"), a.get("probabilities"), a.get("confidence"), r


def main():
    p = argparse.ArgumentParser(description="Суждение по критерию через TypeSafe Jev")
    p.add_argument("kind", choices=["noul", "choice", "score", "batch"])
    p.add_argument("state")
    p.add_argument("question", nargs="?")
    p.add_argument("-o", "--options", nargs="+", default=[])
    p.add_argument("--json", action="store_true", help="вернуть сырой ответ")
    a = p.parse_args()

    if a.kind == "noul":
        v, full = noul(a.state, a.question)
        print(json.dumps({"noul": v, "usage": full.get("usage")}, ensure_ascii=False) if a.json else f"{v}")
    elif a.kind == "choice":
        c, probs, conf, full = choice(a.state, a.question, a.options)
        print(json.dumps(full, ensure_ascii=False) if a.json else f"{c}\tвероятности={probs}\tуверенность={conf}")
    elif a.kind == "score":
        s, probs, conf, full = score(a.state, a.question, a.options)
        print(json.dumps(full, ensure_ascii=False) if a.json else f"{s}\tвероятности={probs}\tуверенность={conf}")
    elif a.kind == "batch":
        state = open(a.state, encoding="utf-8").read() if a.state.endswith((".txt", ".md")) else a.state
        questions = json.load(open(a.question, encoding="utf-8"))
        r = ask(state, questions)
        print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
