# Lyrics Sync API – практический baseline-прогон

## Цель

Проверить простой ASR baseline для задачи синхронизации текста песни по vocal stem, отделённому через `htdemucs v4`.

Цель этого прогона – не собрать финальный production pipeline, а быстро проверить на реальных данных:

- запускается ли self-hosted Whisper-based подход на реальных vocal stems;
- какое получается время обработки;
- укладывается ли подход в целевую стоимость;
- насколько стабильным получается текст;
- где baseline ломается;
- можно ли использовать такой подход как основу для MVP.

---

## Окружение

- Датасет: 9 `.m4a` vocal-файлов из предоставленного Unbake dataset.
- Тип separation: `htdemucs v4 vocal stems`.
- Модель: `faster-whisper large-v3`.
- GPU: NVIDIA A40 48GB, RunPod.
- Цена GPU во время прогона: `$0.44/hour`.
- Python: 3.12.
- FFmpeg: 6.1.1.

Основные параметры запуска:

- `word_timestamps=True`
- `vad_filter=True`
- `beam_size=5`
- `condition_on_previous_text=False`
- `hallucination_silence_threshold=2.0`

`condition_on_previous_text=False` был выбран осознанно: на вокале с Demucs-артефактами Whisper может начинать “додумывать” текст из предыдущего контекста. Для lyrics sync лучше потерять немного связности, чем получить уверенные галлюцинации.

---

## Batch-прогон

Был запущен batch-прогон по всем 9 `.m4a` файлам из датасета.

Все файлы обработались без ошибок.

| Метрика | Значение |
|---|---:|
| Обработано файлов | 9 / 9 |
| Ошибок обработки | 0 |
| Суммарное время транскрибации | ~154.95 sec |
| Среднее время на трек | ~17.22 sec |
| GPU price | $0.44/hour |
| Raw GPU cost на весь batch | ~$0.0189 |
| Raw GPU cost на трек | ~$0.0021 |

Расчёт raw GPU cost:

$0.44 / hour = ~$0.0001222 / sec
154.95 sec на 9 треков = ~$0.0189 total
$0.0189 / 9 = ~$0.0021 per track


Это не включает cold start, storage, idle time, retries, очередь, margin и production overhead. Но даже с запасом видно, что целевой лимит `< $0.05 за 3-минутный трек` реалистичен для self-hosted GPU worker.

---

## Результаты транскрибации по файлам

| # | Язык | Файл | Время | Chars | Words | Lines | Error |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | EN | Post Malone & 21 Savage – rockstar.m4a | 14.39s | 2102 | 427 | 51 | None |
| 2 | ES | Peso Pluma & Anitta – BELLAKEO.m4a | 51.13s | 1095 | 216 | 32 | None |
| 3 | ES | Peso Pluma – BRUCE WAYNE.m4a | 5.35s | 977 | 193 | 23 | None |
| 4 | ES | Peso Pluma – SOLICITADO.m4a | 5.28s | 991 | 197 | 26 | None |
| 5 | FR | Cœur de pirate – Place de la République.m4a | 6.80s | 1118 | 246 | 35 | None |
| 6 | RU | Би-2 – русскоязычный vocal stem | 6.03s | 466 | 79 | 15 | None |
| 7 | RU | Русскоязычный vocal stem | 45.24s | 1980 | 390 | 60 | None |
| 8 | RU | Miyagi & Эндшпиль – Last of Us.m4a | 9.39s | 1741 | 321 | 58 | None |
| 9 | RU | Pharaoh – Дико, например.m4a | 11.34s | 1399 | 258 | 36 | None |

Некоторые русские имена файлов в окружении отображались как escaped unicode, поэтому в таблице они частично сокращены. На сам прогон это не влияло.

---

## Оценка качества текста

Для быстрой оценки были автоматически подтянуты reference lyrics из LRCLIB там, где они нашлись.

Важно: LRCLIB не является идеальным ground truth для этой задачи. Vocal stem из датасета может отличаться от текста в LRCLIB из-за:

- другой версии трека;
- повторов / adlibs;
- cut / radio edit;
- каверного исполнения;
- ошибок metadata;
- отличий между фактическим исполнением и опубликованным lyrics.

Поэтому WER/CER ниже – это practical baseline, а не финальная научная оценка качества.

Оценено: 7 / 9 треков.

| Трек | Язык | WER | CER | Ref words | Hyp words |
|---|---:|---:|---:|---:|---:|
| rockstar | EN | 0.3243 | 0.2396 | 515 | 427 |
| BELLAKEO | ES | 0.7525 | 0.6108 | 396 | 216 |
| BRUCE WAYNE | ES | 0.3951 | 0.2898 | 243 | 193 |
| SOLICITADO | ES | 0.2047 | 0.1535 | 215 | 197 |
| Place de la République | FR | 0.2807 | 0.1566 | 228 | 218 |
| Last of Us | RU | 0.2530 | 0.1097 | 328 | 321 |
| Дико, например | RU | 0.2016 | 0.0992 | 258 | 258 |

Средние значения:

| Срез | Кол-во треков | AVG WER | AVG CER |
|---|---:|---:|---:|
| Все evaluated refs | 7 | 0.3446 | 0.2370 |
| Без BELLAKEO как outlier | 6 | 0.2766 | 0.1747 |

---

## Комментарий по BELLAKEO

`BELLAKEO` оказался явным outlier.

По WER/CER он выглядит как сильный провал:

| Metric | Value |
|---|---:|
| WER | 0.7525 |
| CER | 0.6108 |

Но дополнительная проверка similarity между reference из LRCLIB и ASR hypothesis показала:

- `token_set_ratio`: ~77.7
- `token_sort_ratio`: ~55.4
- `partial_ratio`: ~61.6

Это означает, что тексты частично пересекаются, но структура/порядок/версия заметно расходятся.

Поэтому WER 0.7525 по этому треку нельзя трактовать только как ошибку ASR. Там смешаны:

- реальные ошибки распознавания;
- возможное несовпадение версии reference lyrics;
- повторы и adlibs;
- особенности vocal stem;
- возможные hallucinated fragments.

Для корректной оценки этот трек нужно вручную сверить с фактическим аудио.

---

## Наблюдения по качеству

По первым результатам видно:

1. `faster-whisper large-v3` справляется с задачей технически: все 9 файлов обработались без ошибок.
2. Latency хорошая для MVP: в среднем около 17 секунд на трек.
3. Стоимость self-hosted inference выглядит сильно ниже целевого лимита `$0.05` за 3-минутный трек.
4. Качество текста нестабильное:
   - на некоторых RU/ES/FR треках результат выглядит приемлемо;
   - на отдельных треках появляются серьёзные расхождения;
   - часть расхождений может быть не ошибкой ASR, а несовпадением reference lyrics и фактического vocal stem.
5. Для production нельзя слепо доверять ни ASR, ни LRCLIB:
   - ASR может ошибаться и галлюцинировать;
   - LRCLIB может не соответствовать каверу/другой версии/изменённому тексту.

---

## Timestamp evaluation

Модель вернула word-level timestamps через `faster-whisper`.

Но я не считаю timestamp MAE как финальную метрику на этом этапе, потому что в датасете нет ручной word-level разметки.

Использовать LRCLIB synced lyrics как word-level ground truth некорректно: там в лучшем случае line-level timestamps, и распределение слов внутри строки даст misleading numbers.

Для честной timestamp evaluation я бы сделал так:

1. Взять 30–60 секунд каждого трека.
2. Разметить начало слов вручную в Audacity.
3. Посчитать:
   - word start MAE;
   - median timestamp error;
   - `% words within 100ms`;
   - `% words within 250ms`;
   - line start MAE.

Это даст честную оценку именно sync-качества, а не искусственную метрику на основе line-level lyrics.

---

## Вывод по архитектуре

`faster-whisper large-v3` как self-hosted baseline на htdemucs-v4 vocal stems работает быстро и дёшево, но качество текста нестабильное.

Практический вывод:

- чистый `Whisper only` pipeline я бы не выбирал как финальное решение;
- baseline достаточно дешёвый для MVP;
- качество нужно стабилизировать через hybrid-подход.

Предлагаемый MVP pipeline:

1. Сначала запускать ASR, чтобы получить фактически исполненный текст.
2. Если iOS-клиент передал metadata из ShazamKit – искать candidate lyrics через LRCLIB.
3. Сравнивать ASR text и candidate lyrics через fuzzy similarity.
4. Если similarity высокий – использовать clean lyrics как текстовый источник и выравнивать по аудио.
5. Если similarity низкий – считать, что это может быть кавер/другая версия, и использовать ASR.
6. Low-confidence участки не притворять точными: возвращать warnings, line-level fallback или `null` timestamps для ненадёжных слов.

---

## Почему не Whisper only

Whisper-only подход прост и дешёв, но для этой задачи он рискованный:

- вокал после Demucs содержит артефакты;
- backing vocals и adlibs могут сбивать ASR;
- модель может галлюцинировать на тихих/шумных участках;
- published lyrics могут не совпадать с фактическим исполнением;
- для iOS-клиента лучше честный fallback, чем уверенно неправильные word timestamps.

Поэтому более безопасная схема – ASR-first + lyrics prior validation:

ASR transcript
↓
candidate lyrics from LRCLIB / ShazamKit metadata
↓
fuzzy similarity check
↓
high similarity → use clean lyrics + alignment
low similarity → use ASR result + warnings/fallback


---

## Что бы я проверял следующим шагом

1. Сравнить `faster-whisper large-v3` и `large-v3-turbo`.
2. Проверить `WhisperX` / `stable-ts` на timestamp accuracy.
3. Вручную разметить 30–60 секунд на каждом треке для честного word-level timestamp eval.
4. Добавить hallucination detection:
   - suspicious repeated phrases;
   - low avg_logprob;
   - high no_speech_prob;
   - long text generated over low-energy audio.
5. Проверить отдельно каверы / changed lyrics cases.
6. Подобрать threshold для fuzzy similarity между ASR и candidate lyrics.
7. Считать метрики отдельно по языкам, потому что RU/ES/FR ведут себя по-разному.

---

## Итог

Baseline подтверждает, что задача технически реалистична в рамках cost target.

Self-hosted `faster-whisper large-v3` на GPU даёт быстрый и дешёвый первый проход, но production-качество требует:

- hybrid ASR + lyrics prior;
- confidence/fallback logic;
- ручной timestamp benchmark;
- отдельной обработки outlier cases;
- честного API output с warnings, а не “идеальными” timestamps там, где модель не уверена.
