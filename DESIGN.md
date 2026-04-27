# Lyrics Sync API – design proposal

## 1. Задача

Нужно API, которое принимает `s3 presigned url` на vocal stem в формате `.m4a`, отделённый через `htdemucs v4`, и возвращает текст песни с таймстемпами.

Желательный формат ответа близкий к LRCLIB:

- `plainLyrics` – обычный текст;
- `syncedLyrics` – LRC line-level формат;
- `lines` – строки с `start_ms/end_ms`;
- `words` – word-level timestamps, если confidence позволяет.

Главный приоритет – accuracy. Лучше вернуть честный line-level / warning, чем уверенно отдать неправильные word timestamps.

---

## 2. Ключевые вводные

- Вход: vocal stem `.m4a`, 256 kbps.
- Вокал уже отделён через `htdemucs v4`.
- Вокал может содержать lead vocals + backing vocals.
- Разделение голосов пока out of scope.
- Пользователи могут загружать не только оригинальные песни, но и каверы / изменённые версии.
- iOS-клиент может бесплатно использовать ShazamKit и передавать metadata.
- Первый этап: около 100 запросов в день.
- Целевой cost: меньше `$0.05` за 3-минутный трек.
- On-device inference не рассматривается.

---

## 3. API design

Я бы делал async job API, а не sync HTTP request.

Причина: обработка трека может занимать 10–60 секунд. Держать мобильный клиент на одном HTTP request хуже, чем выдать `job_id` и позволить клиенту polling.

### POST `/v1/lyrics/sync`

Создаёт задачу на обработку.

Request:

```json
{
  "audio_url": "https://s3.amazonaws.com/bucket/vocal.m4a?...",
  "language_hint": "ru",
  "track": {
    "title": "rockstar",
    "artist": "Post Malone",
    "duration_ms": 218000,
    "shazam_confidence": 0.94
  },
  "options": {
    "return_lrc": true,
    "return_words": true
  }
}
```

Поля:

- `audio_url` – обязательный presigned URL;
- `language_hint` – optional, если клиент знает язык;
- `track` – optional metadata из ShazamKit;
- `return_lrc` – вернуть LRC line-level format;
- `return_words` – вернуть word-level timestamps, если качество позволяет.

Response `202 Accepted`:

```json
{
  "job_id": "job_01j9xkv3m",
  "status": "queued",
  "estimated_wait_seconds": 20
}
```

---

### GET `/v1/lyrics/sync/{job_id}`

Возвращает статус или готовый результат.

Response `200 OK`:

```json
{
  "job_id": "job_01j9xkv3m",
  "status": "complete",
  "language": "ru",
  "source": "asr",
  "confidence": 0.81,
  "warnings": [
    "low_confidence_segments: 3",
    "possible_backing_vocals"
  ],
  "plainLyrics": "Никогда, никогда\nНе сдавайся...",
  "syncedLyrics": "[00:04.12] Никогда, никогда\n[00:07.30] Не сдавайся",
  "lines": [
    {
      "text": "Никогда, никогда",
      "start_ms": 4120,
      "end_ms": 6400
    }
  ],
  "words": [
    {
      "word": "Никогда",
      "start_ms": 4120,
      "end_ms": 4780,
      "confidence": 0.92
    },
    {
      "word": "никогда",
      "start_ms": 4900,
      "end_ms": 5560,
      "confidence": 0.89
    }
  ]
}
```

---

## 4. Statuses and errors

Statuses:

| Status | Meaning |
|---|---|
| `queued` | задача в очереди |
| `processing` | worker скачал аудио и обрабатывает его |
| `complete` | результат готов |
| `failed` | обработка завершилась ошибкой |

Error codes:

| Error code | Meaning |
|---|---|
| `audio_fetch_failed` | не удалось скачать файл |
| `audio_url_expired` | presigned URL истёк |
| `audio_too_large` | файл слишком большой |
| `audio_too_long` | трек слишком длинный |
| `unsupported_format` | формат не поддерживается |
| `transcription_failed` | ошибка ASR |
| `alignment_failed` | ошибка forced alignment |
| `internal_error` | неожиданная ошибка |

---

## 5. Pipeline

Базовый pipeline:

```text
POST /v1/lyrics/sync
    ↓
validate request
    ↓
enqueue job
    ↓
GPU worker downloads audio
    ↓
ffmpeg decode to 16 kHz mono wav
    ↓
ASR: faster-whisper large-v3
    ↓
optional lyrics prior lookup via LRCLIB
    ↓
ASR text vs candidate lyrics similarity check
    ↓
alignment / post-processing
    ↓
build plainLyrics, syncedLyrics, lines, words
    ↓
save result with TTL
    ↓
GET /v1/lyrics/sync/{job_id}
```

---

## 6. Baseline model choice

Для первого MVP baseline я выбрал:

```text
faster-whisper large-v3
```

Причины:

- хорошее multilingual покрытие;
- self-hosted дешевле managed API;
- есть word-level timestamps;
- можно контролировать параметры против галлюцинаций;
- работает на доступных GPU уровня RTX 3090 / RTX 4090 / A40.

Ключевые параметры baseline-прогона:

```python
word_timestamps=True
vad_filter=True
beam_size=5
condition_on_previous_text=False
hallucination_silence_threshold=2.0
```

`condition_on_previous_text=False` важен, потому что на вокале после Demucs Whisper может начинать “додумывать” текст по предыдущему контексту.

---

## 7. Hybrid ASR + lyrics prior

Я бы не строил финальный pipeline как `Whisper only`.

Причина: в задаче есть два конфликтующих фактора:

1. ASR слышит фактическое исполнение, но может ошибаться и галлюцинировать.
2. Published lyrics чище, но могут не соответствовать каверу или изменённой версии.

Поэтому предлагаемый подход:

```text
ASR transcript
    ↓
candidate lyrics from LRCLIB using ShazamKit metadata
    ↓
fuzzy similarity check
    ↓
high similarity → use clean lyrics + alignment
low similarity  → use ASR result + warnings/fallback
```

Логика:

1. Всегда запускаем ASR.
2. Если iOS-клиент передал `title/artist` из ShazamKit, ищем lyrics в LRCLIB.
3. Сравниваем ASR transcript и candidate lyrics через fuzzy similarity.
4. Если similarity высокий – считаем, что текст совпадает, и используем clean lyrics.
5. Если similarity низкий – считаем, что это может быть кавер / changed lyrics, и используем ASR.
6. Низкоуверенные участки помечаем в `warnings`.

---

## 8. Alternatives considered

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| `faster-whisper large-v3` self-hosted | Хорошее multilingual качество, word timestamps, контроль параметров, низкая стоимость | Нужен GPU worker, возможны hallucinations на грязном вокале | MVP baseline |
| `large-v3-turbo` | Быстрее и дешевле | Нужно проверить качество на RU/PL/JP/ES, может быть хуже на сложном вокале | Проверить следующим шагом |
| WhisperX / stable-ts | Может улучшить timestamp accuracy | Больше зависимостей, выше latency, не все языки одинаково хорошо поддержаны | Проверить после baseline |
| LRCLIB + ShazamKit | Чистый текст для известных треков | Нельзя доверять при каверах / changed lyrics | Использовать как lyrics prior |
| OpenAI Whisper API | Нет своей infra, быстро проверить | Нет нормального контроля параметров, нет полноценного word-level sync, vendor cost | Не основной вариант |
| Deepgram / AssemblyAI | Managed, word timestamps | Дороже, слабее контроль, качество по RU/JP/PL под вопросом | Не первый выбор |
| Fine-tuning | Может дать лучшее качество на Demucs vocals | Дорого по времени и данным, рано для MVP | Не делать на старте |

---

## 9. Hardware and cost

Для MVP не нужен A100/H100.

Достаточно GPU уровня:

- RTX 3090 24GB;
- RTX 4090 24GB;
- A40 48GB;
- A10 24GB.

Фактический baseline-прогон:

| Metric | Value |
|---|---:|
| GPU | NVIDIA A40 48GB |
| Provider | RunPod |
| GPU price | `$0.44/hour` |
| Files processed | 9 / 9 |
| Total transcription time | `~154.95 sec` |
| Average time per track | `~17.22 sec` |
| Raw GPU cost per track | `~$0.0021` |

Cost calculation:

```text
$0.44 / hour = ~$0.0001222 / sec
154.95 sec for 9 tracks = ~$0.0189 total
$0.0189 / 9 = ~$0.0021 per track
```

Даже с учётом cold start, storage, retries и idle time self-hosted GPU worker выглядит реалистичным для лимита `< $0.05` за 3-минутный трек.

---

## 10. MVP infrastructure

Для старта:

```text
API server: small CPU VPS
Queue: Redis / RQ
Worker: GPU pod
Storage: Redis TTL / S3 for temporary outputs
```

Компоненты:

| Component | Choice | Why |
|---|---|---|
| API server | 2–4 vCPU VPS | только HTTP, auth, validation, queue |
| Queue | Redis | просто и достаточно для MVP |
| GPU worker | RunPod / Vast / similar | дешёвый self-hosted inference |
| Result storage | Redis TTL / S3 | результат можно хранить 7 дней |
| Logs | plain structured logs | достаточно для MVP |

Я бы не проектировал сложный scale на 10k/day в первой версии. Но очередь и worker-модель позволяют позже добавить больше GPU workers без переписывания API.

---

## 11. Evaluation strategy

Нельзя выбирать pipeline “на слух”. Нужны метрики.

Что считаем:

| Metric | Purpose |
|---|---|
| WER | качество текста для EN/FR/ES/IT/PT/RU/PL |
| CER | полезно для RU/PL/JP и ошибок внутри слов |
| Hallucination rate | доля явно лишних/выдуманных фрагментов |
| Word start MAE | точность word-level timestamps |
| % words within 100ms | доля очень точных слов |
| % words within 250ms | доля приемлемых слов |
| Line start MAE | точность line-level sync |

Что уже было сделано в baseline:

- прогнаны все 9 `.m4a` файлов из provided dataset;
- посчитаны WER/CER по 7 трекам, где удалось автоматически подтянуть lyrics из LRCLIB;
- измерены latency и raw GPU cost;
- timestamp MAE не посчитан как финальная метрика, потому что нет ручной word-level разметки.

Почему timestamp MAE пока не считаю:

- LRCLIB даёт line-level timestamps;
- word-level ground truth в датасете отсутствует;
- равномерно распределять слова внутри строки – misleading;
- для честной оценки нужно вручную разметить 30–60 секунд на трек в Audacity.

---

## 12. Baseline results

Summary:

| Metric | Value |
|---|---:|
| Processed files | 9 / 9 |
| Failed files | 0 |
| Evaluated refs | 7 / 9 |
| AVG WER | 0.3446 |
| AVG CER | 0.2370 |
| AVG WER without BELLAKEO outlier | 0.2766 |
| AVG CER without BELLAKEO outlier | 0.1747 |

By track:

| Track | Lang | WER | CER |
|---|---:|---:|---:|
| rockstar | EN | 0.3243 | 0.2396 |
| BELLAKEO | ES | 0.7525 | 0.6108 |
| BRUCE WAYNE | ES | 0.3951 | 0.2898 |
| SOLICITADO | ES | 0.2047 | 0.1535 |
| Place de la République | FR | 0.2807 | 0.1566 |
| Last of Us | RU | 0.2530 | 0.1097 |
| Дико, например | RU | 0.2016 | 0.0992 |

`BELLAKEO` отмечен как outlier. Similarity между LRCLIB reference и ASR hypothesis:

```text
token_set_ratio: ~77.7
token_sort_ratio: ~55.4
partial_ratio: ~61.6
```

Это похоже не только на ASR failure, но и на mismatch версии / структуры lyrics.

---

## 13. Что может пойти не так

| Risk | Mitigation |
|---|---|
| Whisper hallucinations на Demucs-артефактах | `condition_on_previous_text=False`, confidence filtering, warnings |
| Backing vocals / overlapping vocals | не разделять голоса на MVP, помечать low confidence |
| Каверы с изменённым текстом | не доверять LRCLIB без ASR similarity check |
| LRCLIB lyrics не совпадают с фактической версией | fuzzy similarity threshold |
| JP tokenization | считать CER, отдельно продумать word splitting |
| Presigned URL expired | требовать TTL > 30 min, возвращать `audio_url_expired` |
| GPU cold start | async job API + realistic ETA |
| Spot eviction | retry job, queue persistence |
| Misleading word timestamps | не отдавать low-confidence word timestamps как точные |
| Copyright / lyrics storage | хранить только результат обработки, проверить TOS LRCLIB |

---

## 14. Что ещё нужно проверить

1. Добрать IT/PT/PL/JP треки, потому что provided dataset покрыл EN/ES/FR/RU.
2. Сравнить `large-v3` и `large-v3-turbo`.
3. Проверить WhisperX / stable-ts на timestamp accuracy.
4. Сделать ручную word-level разметку 30–60 секунд на трек.
5. Подобрать fuzzy similarity threshold для ASR vs lyrics prior.
6. Добавить hallucination detection:
   - repeated phrases;
   - low `avg_logprob`;
   - high `no_speech_prob`;
   - generated text over silent/low-energy audio.
7. Отдельно измерить качество на:
   - original songs;
   - covers with same lyrics;
   - covers with changed lyrics;
   - noisy Demucs stems;
   - backing vocals heavy tracks.

---

## 15. Итоговое решение

Для MVP я бы выбрал:

```text
Async API
+ queue
+ self-hosted faster-whisper large-v3 baseline
+ optional LRCLIB lyrics prior via ShazamKit metadata
+ fuzzy similarity validation
+ line-level fallback
+ confidence warnings
```

Почему:

- self-hosted inference укладывается в cost target;
- latency приемлемая для мобильного UX;
- ASR нужен, потому что у каверов может быть изменённый текст;
- lyrics prior нужен, потому что чистый ASR нестабилен на Demucs vocal stems;
- word-level timestamps нужно отдавать только там, где confidence достаточно высокий.

Главный вывод baseline-прогона: задача технически реалистична, но production-качество требует не `Whisper only`, а hybrid ASR + lyrics prior + fallback logic.
