# Lyrics Sync API – практический baseline-прогон

## Цель



- запускается ли self-hosted Whisper-based подход на реальных vocal stems;
- какое получается время обработки;
- укладывается ли подход в целевую стоимость;
- насколько стабильным получается текст;
- где baseline ломается.

## Окружение

- Датасет: 9 `.m4a` vocal-файлов из предоставленного Unbake dataset.
- Тип separation: htdemucs v4 vocal stems.
- Модель: `faster-whisper large-v3`.
- GPU: NVIDIA A40 48GB, RunPod.
- Цена GPU во время прогона: `$0.44/hour`.
- Python: 3.12.


```python
word_timestamps=True
vad_filter=True
beam_size=5
condition_on_previous_text=False
hallucination_silence_threshold=2.0
