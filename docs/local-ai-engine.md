# Zaya modular local AI engine

Zaya is created and developed by Sajan Rai. Gemini Live is still the preferred
native audio path. The modular engine is an alternate, explicitly selected
pipeline: microphone → speech-to-text → language model → text-to-speech. It
shares Zaya's tools, trust checks, confirmation gate, phone bridge, mission
supervisor, conversation archive, avatar and playback queue.

## Enable it

1. Open **AI ENGINE** in Zaya's settings drawer.
2. Choose **LOCAL PIPELINE**.
3. Choose an LLM provider, model and endpoint.
4. Optionally set a faster-whisper model and a Piper voice.
5. Save and restart Zaya.

Engine selection is stored as `engine_mode` in `config/api_keys.json`. The
accepted values are `gemini_live` and `local_pipeline`; `local`, `offline`,
`pipeline`, `gemini`, `live` and `native` are accepted aliases. Existing
configurations without this key continue to use Gemini Live.

## Language model providers

The provider catalog covers Gemini, OpenAI, OpenRouter, Groq, DeepSeek, Mistral,
xAI, Together, Cerebras, Ollama, LM Studio, llama.cpp server, vLLM, and a custom
OpenAI-compatible endpoint. Selecting a provider only supplies defaults; the
model and endpoint remain editable.

For a custom endpoint, mark it **THIS MACHINE / LAN** when it is local. A remote
custom endpoint needs an API key. This prevents an owner who selected a private
local setup from accidentally treating an unauthenticated remote address as a
safe default.

Useful configuration keys:

| Key | Meaning |
| --- | --- |
| `local_llm_provider` | Catalog key such as `ollama`, `lmstudio` or `custom`. |
| `local_llm_model` | Model name understood by the endpoint. |
| `local_llm_base_url` | Endpoint base URL. |
| `local_llm_api_key` | Optional key for the selected endpoint. |
| `local_stt_model` | faster-whisper model (`tiny`, `base`, `small`, `medium`, ...). |
| `local_stt_device` | `auto`, `cpu` or a supported accelerated device. |
| `local_stt_compute` | faster-whisper compute type, normally `int8`. |
| `local_stt_language` | Optional fixed transcription language; empty auto-detects. |
| `local_tts_model` | Path to a Piper `.onnx` voice. |
| `local_tts_voice_map` | JSON object mapping languages to Piper voice paths. |
| `local_tts_fallback_voice` | Voice used when the detected language has no mapping. |
| `allow_cloud_fallback` | Explicitly allow a different provider after failure; default `false`. |
| `local_timings` | Write content-free stage timings; default `true`. |

## Speech dependencies and models

Install the optional packages:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-local-speech.txt
```

Piper needs a voice model and its matching JSON metadata file. Download a voice
from the Piper voice collection, keep both files together, and enter the `.onnx`
path in **AI ENGINE**. Different languages can use different voices through
`local_tts_voice_map`, for example:

```json
{
  "en": "C:/zaya/voices/en_US-lessac-medium.onnx",
  "ne": "C:/zaya/voices/ne_NP-google-medium.onnx"
}
```

faster-whisper downloads a model on first use. If speed matters more than
accuracy, start with `base` or `small`; `medium` and larger models need more RAM
and time. A CUDA failure falls back to CPU `int8` when the selected device is not
already CPU.

## Failure behavior

Every readiness failure names the component and provider:

- **STT unavailable:** voice turns show the transcription failure; typed turns
  still reach the language model.
- **TTS unavailable:** text is still displayed and archived; a synthesis error
  is reported separately.
- **LLM unavailable:** Zaya names the provider and endpoint/rejection. It does
  not blame the microphone or speaker.

Readiness is written to `logs/runtime/local_engine_readiness.json`. Timings are
appended as JSON lines to `logs/runtime/local_pipeline_timings.jsonl`; they
contain stage durations, provider name and text length, not conversation text.

## Privacy and limits

- When the selected provider is local, cloud failover is off unless the owner
  enables it. A local provider never silently escalates to a remote service.
- The modular pipeline accepts text and microphone audio. A screenshot or camera
  frame arriving through the shared live-session interface is reported as
  unsupported rather than silently discarded as if it had been analyzed.
- Gemini Live remains the native audio path and its existing behavior is kept.
  The modular engine uses the same operator, confirmation gate, tool budgets,
  result statuses and mission states.
- Piper and faster-whisper are optional; their absence must not prevent Zaya
  from starting or answering in text.

## Focused checks

```powershell
.venv\Scripts\python.exe -m pytest tests\test_ai_engine.py tests\test_speech_pipeline.py tests\test_local_pipeline.py tests\test_provider_streaming.py -q
```
