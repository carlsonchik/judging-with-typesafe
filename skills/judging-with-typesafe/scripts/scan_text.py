#!/usr/bin/env python3
"""Скан текста по абзацам через TypeSafe Jev.

Три режима:
  verify  — «можно ли проверить утверждение, не обращаясь к автору?» (основной)
  rubric  — рубрика из четырёх вопросов, решение принимается по сводке
  claim   — «содержит ли фрагмент утверждение, требующее проверки?»

Ключевые правила (проверены на живом API):
  * Значения 0.30–0.70 — это «не знаю», а не «средне». Они идут в колонку «нужен человек».
  * Низкий балл не значит «плохой текст»: он значит «не тот тип фрагмента».
  * Для философской прозы различение слабое — вопрос про проверяемость там шумит.

Использование:
    python3 scan_text.py файл.md --mode verify --min-len 400
    python3 scan_text.py файл.md --mode rubric
"""
import argparse, json, os, re, statistics, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
WRAP = os.path.join(HERE, "typesafe.py")

RUBRIC = {
    "objects": "Фрагмент называет конкретные объекты и операции или только описывает значимость темы?",
    "verifiable": "Можно ли проверить утверждение фрагмента, не обращаясь к автору?",
    "substance": "Если убрать оценочные слова, останется ли в фрагменте проверяемое содержание?",
    "definite": "Фрагмент сообщает что-то определённое или создаёт впечатление глубины?",
}
VERIFY_Q = RUBRIC["verifiable"]
CLAIM_Q = "Содержит ли фрагмент утверждение, которое требует проверки?"
UNCERTAIN = (0.30, 0.70)


def judge(state, question):
    out = subprocess.run(["python3", WRAP, "noul", state, question],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except Exception:
        return None


def blocks(text, min_len):
    out = []
    for i, b in enumerate(re.split(r'\n\s*\n', text)):
        p = re.sub(r'^#+\s*', '', b).strip()
        p = re.sub(r'^\*\*[^*]+\*\*\s*', '', p).strip()
        if len(p) < min_len or p.startswith(("**Ключевые", "**Keywords", "---", "|")):
            continue
        out.append((i, p))
    return out


def verdict(v):
    if v is None:
        return "нет ответа", "bad"
    if v > UNCERTAIN[1]:
        return "проверяемо / есть содержание", "ok"
    if v < UNCERTAIN[0]:
        return "не проверяемо / общие слова", "low"
    return "НЕ ЯСНО — нужен человек", "uncertain"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--mode", choices=["verify", "rubric", "claim"], default="verify")
    p.add_argument("--min-len", type=int, default=400)
    p.add_argument("--out", default=None)
    a = p.parse_args()

    text = open(a.path, encoding="utf-8").read()
    rows = []
    print(f"файл: {a.path}")
    print(f"режим: {a.mode} | пороги: <{UNCERTAIN[0]} не проверяемо, "
          f"{UNCERTAIN[0]}–{UNCERTAIN[1]} нужен человек, >{UNCERTAIN[1]} проверяемо\n")

    for i, plain in blocks(text, a.min_len):
        rec = {"block": i, "start": re.sub(r'\s+', ' ', plain)[:68], "text": plain}
        if a.mode == "rubric":
            vals = {k: judge(plain, q) for k, q in RUBRIC.items()}
            rec["scores"] = vals
            good = [v for v in vals.values() if v is not None]
            mean = round(statistics.mean(good), 3) if good else None
            rec["mean"] = mean
            un = sum(1 for v in good if UNCERTAIN[0] <= v <= UNCERTAIN[1])
            mark, _ = verdict(mean)
            if un >= 2:
                mark = "НЕ ЯСНО по рубрике — нужен человек"
            brief = " ".join(f"{k}={v}" for k, v in vals.items())
            print(f"  {str(mean):>5}  {mark:<34} {rec['start']}\n         {brief}")
        else:
            q = VERIFY_Q if a.mode == "verify" else CLAIM_Q
            v = judge(plain, q)
            rec["verdict"] = v
            mark, _ = verdict(v)
            print(f"  {str(v):>5}  {mark:<34} {rec['start']}")
        rows.append(rec)

    vals = [r.get("verdict") if a.mode != "rubric" else r.get("mean") for r in rows]
    vals = [v for v in vals if v is not None]
    if vals:
        un = sum(1 for v in vals if UNCERTAIN[0] <= v <= UNCERTAIN[1])
        print(f"\nабзацев: {len(vals)} | среднее {statistics.mean(vals):.3f}"
              f" | определённых: {sum(1 for v in vals if v > UNCERTAIN[1])}"
              f" | неясных (нужен человек): {un}"
              f" | явно слабых: {sum(1 for v in vals if v < UNCERTAIN[0])}")
    out = a.out or os.path.splitext(a.path)[0] + f"-скан-{a.mode}.json"
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"результат: {out}")


if __name__ == "__main__":
    main()
