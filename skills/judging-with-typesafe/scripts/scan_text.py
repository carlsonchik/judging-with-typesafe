#!/usr/bin/env python3
"""Скан текста по абзацам через TypeSafe Jev.

Задаёт каждому абзацу ОДИН вопрос и возвращает карту: где аргумент есть,
где фрагмент другого типа (перечисление, признание открытости, список).

Важно: низкий балл НЕ значит «плохой абзац». Он значит, что этот абзац
не является утверждением с основаниями — например, это список или постановка вопроса.
Такой абзац надо оценивать другим вопросом, а не понижать в качестве.

Использование:
    python3 scan_text.py <файл.md> [--mode argument|claim|source] [--min-len 300]
Режимы (что именно меряем в каждом абзаце):
    argument — есть ли утверждение с приведёнными основаниями (по умолчанию)
    claim    — заявлено ли нечто, требующее проверки
    source   — указан ли проверяемый источник
"""
import argparse, json, re, statistics, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
WRAP = os.path.join(HERE, "typesafe.py")

QUESTIONS = {
    "argument": "В этом фрагменте есть утверждение, для которого приведены основания?",
    "claim": "Этот фрагмент содержит утверждение, которое требует проверки?",
    "source": "В этом фрагменте указан проверяемый источник утверждения?",
}


def judge(state: str, question: str):
    out = subprocess.run(["python3", WRAP, "noul", state, question],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except Exception:
        return None


def blocks_of(text: str, min_len: int):
    out = []
    for i, b in enumerate(re.split(r'\n\s*\n', text)):
        plain = re.sub(r'^#+\s*', '', b).strip()
        plain = re.sub(r'^\*\*[^*]+\*\*\s*', '', plain).strip()   # снять ведущий жирный заголовок
        if len(plain) < min_len:
            continue
        if plain.startswith(("**Ключевые", "**Keywords", "---", "|")):
            continue
        out.append((i, plain))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--mode", choices=list(QUESTIONS), default="argument")
    p.add_argument("--min-len", type=int, default=300)
    p.add_argument("--out", default=None)
    a = p.parse_args()

    question = QUESTIONS[a.mode]
    text = open(a.path, encoding="utf-8").read()
    rows = []
    print(f"файл: {a.path}")
    print(f"режим: {a.mode} — «{question}»")
    print(f"абзацев длиннее {a.min_len} символов\n")
    for i, plain in blocks_of(text, a.min_len):
        v = judge(plain, question)
        head = re.sub(r'\s+', ' ', plain)[:68]
        if v is None:
            mark = "нет ответа"
        elif v < 0.35:
            mark = "не утверждение (список/постановка)"
        elif v < 0.55:
            mark = "близко к порогу"
        else:
            mark = "утверждение с основаниями"
        print(f"  {v if v is not None else '—':>5}  {mark:<32} {head}")
        rows.append({"block": i, "verdict": v, "kind": mark, "start": head, "text": plain})
    vals = [r["verdict"] for r in rows if r["verdict"] is not None]
    if vals:
        print(f"\nабзацев: {len(vals)} | среднее {statistics.mean(vals):.3f} "
              f"| утверждений с основаниями: {sum(1 for v in vals if v >= 0.55)} "
              f"| не-утверждений: {sum(1 for v in vals if v < 0.35)}")
    out = a.out or os.path.splitext(a.path)[0] + f"-скан-{a.mode}.json"
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"результат: {out}")


if __name__ == "__main__":
    main()
