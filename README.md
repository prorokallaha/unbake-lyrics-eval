# Unbake Lyrics Sync Baseline Eval

Практический baseline-прогон для тестового задания **Unbake Lyrics Sync API**.

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

## Что было сделано

1. Поднят GPU pod на RunPod.
2. Установлены `faster-whisper`, `ffmpeg`, `jiwer`, `rapidfuzz`.
3. Запущен batch-прогон по всем 9 `.m4a` vocal stems.
4. Для 7 / 9 треков автоматически подтянуты reference lyrics из LRCLIB.
5. Посчитаны WER/CER.
6. Отдельно отмечены ограничения такой оценки.

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
```

## Что запускалось

Основной batch-прогон:

```bash
python batch_transcribe.py
```

Оценка WER/CER по найденным reference lyrics:

```bash
python eval_mapping.py
```

## Ограничения

- Аудио из предоставленного датасета не добавлено в репозиторий.
- LRCLIB используется только как быстрый reference source, а не как идеальный ground truth.
- Timestamp MAE не вынесен как финальная метрика, потому что в датасете нет ручной word-level разметки.
- BELLAKEO отмечен как outlier из-за возможного mismatch между LRCLIB lyrics и фактическим vocal stem.

## Вывод

`faster-whisper large-v3` как self-hosted baseline работает достаточно быстро и дёшево для MVP, но качество текста на `htdemucs v4` vocal stems нестабильное.

Практический вывод: финальный pipeline лучше строить не как `Whisper only`, а как hybrid:

```text
ASR baseline
+ lyrics prior через ShazamKit/LRCLIB
+ fuzzy similarity check
+ fallback на ASR для каверов/изменённого текста
+ confidence warnings / line-level fallback для ненадёжных участков
```
