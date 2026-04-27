# Unbake Lyrics Sync Baseline Eval

Практический baseline-прогон для тестового задания Unbake Lyrics Sync API.

Цель – проверить, как `faster-whisper large-v3` работает на vocal stems, отделённых через `htdemucs v4`, и получить первые реальные цифры по latency, cost и качеству текста.

## Коротко

- Датасет: 9 `.m4a` vocal-файлов из предоставленного Unbake dataset
- Separation: `htdemucs v4`
- Модель: `faster-whisper large-v3`
- GPU: NVIDIA A40 48GB, RunPod
- Обработано: 9 / 9 файлов
- Ошибок: 0
- Суммарное время транскрибации: ~154.95 sec
- Среднее время на трек: ~17.22 sec
- Raw GPU cost на трек: ~$0.0021 при $0.44/hour

## Метрики

Reference lyrics были автоматически подтянуты из LRCLIB там, где это удалось сделать.

Оценено: 7 / 9 треков.

| Scope | Tracks | AVG WER | AVG CER |
|---|---:|---:|---:|
| Все evaluated refs | 7 | 0.3446 | 0.2370 |
| Без BELLAKEO outlier | 6 | 0.2766 | 0.1747 |

Важно: LRCLIB не является идеальным ground truth для этой задачи, потому что версия трека / повторы / adlibs / каверное исполнение могут отличаться от reference lyrics.

## Основной отчёт

Подробный отчёт с выводами, cost calculation, таблицей WER/CER и комментариями по ограничениям находится здесь:

[REPORT.md](./REPORT.md)

## Структура

```text
.
├── REPORT.md
├── README.md
├── batch_transcribe.py
├── transcribe.py
├── eval_text.py
├── eval_mapping.py
├── fetch_refs_lrclib.py
├── outputs/
│   ├── summary.json
│   └── eval_results.json
├── outputs_txt/
└── refs/
    └── mapping.json
