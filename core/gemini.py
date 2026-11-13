"""
One place where the assistant's one-shot Gemini calls are made.

WHY THIS EXISTS
    The live conversation runs on the Live API and is not what this file is
    about. Everything else — reading a screenshot, parsing a flight page,
    turning a request into a shell command, working out which WhatsApp button
    answers a call — was a separate `genai.Client(...)` built at the point of
    use, with the model name written inline. Sixteen files did it, twenty-six
    times, and not one of them set a timeout.

    That is not tidiness, it is three real faults:

    NO TIMEOUT.  The SDK waits forever by default. `gemini-flash-latest` spent
    an afternoon returning 504 DEADLINE_EXCEEDED, and every one of those calls
    became an unbounded hang — measured at ten seconds of silence while a phone
    rang, and worse elsewhere, because nothing was there to give up.

    NO FALLBACK.  One hardcoded alias meant that when that alias was unwell,
    the feature was simply gone. A ladder costs nothing when the first rung
    works and saves the feature when it does not.

    NO SINGLE PLACE TO CHANGE.  A new model release meant editing sixteen files
    and hoping none were missed.

THE LIVE MODEL DOES THIS WORK, AND IT LEADS THE LADDER
    Not the user's conversation — a separate, throwaway session per call, so
    nothing a plugin asks is ever heard by the person at the microphone.

    It leads because of quota. This is a voice assistant; the Live API is the
    dependency it already has, and it draws on a different pool from the text
    models. On the free tier it is the TEXT pool that runs out, and when it does
    every side call fails and the feature behind it dies with it. Putting Live
    first means ordinary use stops spending the pool that runs dry.

    The reply arrives through output_transcription, because these models refuse
    response_modalities=["TEXT"] with a 1007 — they only speak. That sounds
    fatal for structured output and is not: the transcription is the model's own
    text of what it said, and it returned "Mum ❤ click here for contact info",
    indented Python inside markdown fences, and src/utils/helpers_v2.py
    character for character.

    It cannot carry grounding metadata, so grounded web search stays on REST.

THE LADDER, MEASURED
    Live, one throwaway session:
        connect                     0.24s
        short structured JSON       1.7 - 2.8s
        2300 characters of code     3.39s, not truncated
        three concurrent sessions   all fine, 4.77s wall clock
    REST text models, same prompt, same afternoon:
        gemini-2.5-flash-lite       0.76s   ...then 429, quota exhausted
        gemini-2.5-flash            0.80s   ...then 429
        gemini-flash-lite-latest    2.58s
        gemini-flash-latest         504, every time
    So REST is two to four times quicker while it lasts, and the whole point of
    the ladder is that it does not last. Pinned REST names sit behind Live;
    rolling `-latest` aliases sit behind those, because they were the ones
    having a bad day.

    Where the answer depends only on stable input, cache it and neither pool is
    touched twice: `plugins/_whatsapp_core.py` is the worked example — one
    request per WhatsApp language for the lifetime of the install.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).resolve().parent.parent

_KEY_FILE = _BASE / "config" / "api_keys.json"

# Ladders, tried left to right. Change a model HERE and the whole app follows.
FAST = "fast"      # short classification, extraction, one-line decisions
SMART = "smart"    # reasoning, generation, long documents, images
SEARCH = "search"  # grounded search — REST only, see below
PROCESS = "process"  # deep reasoning on the processing model, see below

# A rung that means "ask the Live model instead", through a short throwaway
# session rather than the REST text API.
#
# WHY IT LEADS
#     This is a voice assistant: the Live API is the dependency it already has,
#     and it draws on a DIFFERENT quota pool from the text models. On the free
#     tier the text pool is the one that runs out — an afternoon of ordinary use
#     exhausts it, and when it does, every one of these side calls fails and the
#     feature behind it dies. The Live pool is untouched by that.
#
# WHAT IT COSTS, MEASURED
#     connect                      0.24s
#     short structured JSON        1.7 - 2.8s   (REST: 0.76s)
#     2300 characters of code      3.39s, not truncated
#     three concurrent sessions    all fine, 4.77s wall clock
#     So it is two to four times slower than REST when REST is available, and
#     infinitely faster than REST when REST is out of quota.
#
# THE THING WORTH KNOWING
#     These models only speak — response_modalities=["TEXT"] is refused with a
#     1007. The reply comes back through output_transcription, which sounds like
#     it would mangle anything structured. It does not: it is the model's own
#     text of what it said, and it survived "Mum ❤ click here for contact info",
#     indented Python inside markdown fences, and src/utils/helpers_v2.py
#     character for character. That is what makes this usable at all.
#
#     What it cannot carry is grounding metadata, so grounded web search stays
#     on REST — see SEARCH.
LIVE = "live"

# Every model this key can reach, in the order to try them. A rung that runs
# out of quota is skipped for a while and the next one answers — which is the
# whole point: one model a day means one daily limit, a ladder means the sum of
# them. Names verified against the live model list rather than guessed.
# Order is measured, not assumed. Timed against this key, same prompt:
#     gemini-3.5-flash-lite      0.56s      gemini-2.5-flash        0.67s
#     gemini-3.1-flash-lite      0.60s      gemini-2.5-flash-lite   0.74s
#     gemini-flash-lite-latest   0.60s      gemini-3.5-flash        1.13s
#     gemini-3-flash-preview     504, after 14.7s of waiting
#     gemini-3.6-flash           504, after 12.0s
#     gemini-flash-latest        503 UNAVAILABLE
# The three that fail sit at the BOTTOM rather than being deleted: they are
# real quota when they are healthy, and a rung that is down is set aside by the
# cooldown after one attempt instead of being paid for on every call.
_LADDERS = {
    FAST: (LIVE,
           "gemini-2.5-flash-lite", "gemini-3.5-flash-lite",
           "gemini-3.1-flash-lite", "gemini-flash-lite-latest",
           "gemini-2.5-flash", "gemini-3.5-flash",
           "gemini-3.6-flash", "gemini-3-flash-preview"),
    # Reasoning work goes to the processing model first. The Live model still
    # leads FAST: those callers are latency-critical (screen grounding, short
    # classifications) and hydrogen is a deliberate, slower thinker. Keeping
    # the two ladders separate is what lets the conversation stay on
    # gemini-3.8-live while background processing uses hydrogen.
    SMART: (PROCESS, LIVE,
            "gemini-2.5-flash", "gemini-3.5-flash",
            "gemini-2.5-flash-lite", "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.6-flash", "gemini-3-flash-preview", "gemini-flash-latest"),
    # Grounded search needs response.candidates[...].grounding_metadata, which a
    # Live turn does not produce. REST only, and it says so rather than silently
    # returning an answer with no sources behind it.
    SEARCH: ("gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.5-flash-lite",
             "gemini-flash-latest"),
}

# The conversation's own model, and ONE careful fallback behind it.
#
# Deliberately not a long ladder. The Live quota is not the one that runs out —
# the text models are — and Live models are not interchangeable the way text
# models are: they differ in which config fields they accept and in what they
# can do, so falling through a list of them risks connecting to something that
# behaves like a different assistant. The key also offers transcribe-live,
# live-translate and a robotics streaming model, none of which are assistants
# at all.
#
# So there are two: the current one, and the native-audio model this assistant
# used before it, which is known to work here. A mismatch in config is already
# survivable — the connect loop drops the tuning and proactive-audio fields and
# reconnects when the server rejects them.
LIVE_MODELS = (
    "models/gemini-3.8-live",
    "models/gemini-3.1-flash-live-preview",
    "models/gemini-2.5-flash-native-audio-preview-12-2025",
)

# The model that does the reasoning work behind the assistant, through the
# interactions endpoint. It is intentionally NOT in LIVE_MODELS: the realtime
# conversation stays on gemini-3.8-live, and only the one-shot SMART ladder
# reaches this. A failure here falls through to the existing Live/REST rungs,
# so processing can degrade without ever touching the live session.
PROCESS_MODEL = "gemini-4-hydrogen"

# Below this deadline a reasoning call is latency-critical (screen grounding,
# UI element lookup). Do not put a deliberately slow model in front of it: skip
# straight to the fast ladder instead of paying for a guaranteed timeout.
PROCESS_MIN_TIMEOUT_MS = 20_000

# The Live model to use for one-shot calls. main.py owns the real one; this is
# only the fallback for when this module is imported without it (tests).
_LIVE_FALLBACK = "models/gemini-3.8-live"

# How many one-shot Live sessions may exist at once.
#
# THE USER'S CONVERSATION OUTRANKS EVERY SIDE CALL.
# Nothing here can reach the microphone or the speaker — main.py has exactly one
# `.receive()` and it is bound to its own session, and audio only reaches the
# speaker through that one loop — so a side call cannot answer the user or talk
# over the reply. Verified alongside a live main session: four side calls fired
# while it was connected, each got its own answer, and the main session replied
# correctly both before and after with no errors.
#
# What a side call CAN do is take up a concurrent-session slot. That is the one
# way it could hurt the conversation, so it is capped, and a call that cannot
# get a slot quickly does not queue behind the others — it falls to the REST
# rung, which is what the ladder is for.
# Three, from the measurement: four side calls plus the conversation ran
# together without complaint, so three leaves the conversation a slot in hand
# while still covering any burst this app actually produces — tool calls run one
# after another, and the screen agent's loop is sequential.
_LIVE_SLOTS = threading.BoundedSemaphore(3)
_LIVE_SLOT_WAIT = 3.0

_ONE_SHOT_SYSTEM = (
    "You are a data-processing function, not an assistant and not in a "
    "conversation. There is no person listening to you. Produce exactly the "
    "output the request asks for and nothing else: no greeting, no "
    "acknowledgement, no 'Understood', no explanation, no closing remark, no "
    "restating of the question. If the request asks for JSON, emit only the "
    "JSON. If it asks for code, emit only the code. If it asks for one word, "
    "emit that one word. Preserve the exact spelling, punctuation, capitals "
    "and whitespace of anything you are asked to copy or return."
)

# Milliseconds. Not a preference: the API rejects anything under ten seconds
# with "Minimum allowed deadline is 10s", so this is the tightest bound it will
# accept. Callers with a long job (a whole document, a big image) pass more.
DEFAULT_TIMEOUT_MS = 10_000
MIN_TIMEOUT_MS = 10_000

_key_lock = threading.Lock()
_cached_key: str | None = None

# A rung that answered 429 is out of quota, and on the free tier it will stay
# that way for a while. Retrying it on every single call is a wasted round trip
# in front of every request the assistant makes — measured on this key, the
# lite rung was 429ing continuously, so every call was paying for it before
# reaching the model that could actually answer. Remembering that for a few
# minutes turns the ladder from a cost into a saving.
_COOLDOWN_SECONDS = 300
# A model that does not exist, or that this key may not use, is not coming back
# in five minutes. Retrying it on every call is a wasted round trip in front of
# everything the assistant does, so it is set aside for the session instead.
_GONE_SECONDS = 6 * 60 * 60
# Overloaded or timing out. Usually passes, so a shorter rest than "gone" —
# but long enough that the fourteen-second wait is paid once, not repeatedly.
_UNAVAILABLE_SECONDS = 30 * 60
_cooldown: dict[str, float] = {}
_cool_lock = threading.Lock()


def _cool(model: str, seconds: float = _COOLDOWN_SECONDS) -> None:
    with _cool_lock:
        _cooldown[model] = time.monotonic() + seconds


def is_quota_error(err: str) -> bool:
    return "429" in err or "RESOURCE_EXHAUSTED" in err


def is_unavailable_error(err: str) -> bool:
    """The model is up but not answering — overloaded, or a deadline expired.

    Worth its own case because of what it costs: a 504 from one of these took
    fourteen seconds to arrive. Retrying that on every call puts the wait in
    front of everything the assistant does, so a rung that times out is rested
    like an exhausted one — for less long, since it is usually passing.
    """
    low = err.lower()
    return ("503" in err or "504" in err
            or "unavailable" in low or "deadline_exceeded" in low)


def is_gone_error(err: str) -> bool:
    """The model is not there, or not ours to use — a different thing from busy."""
    low = err.lower()
    return ("404" in err or "not found" in low or "is not supported" in low
            or "permission" in low or "403" in err)


def live_model() -> str:
    """The Live model to open the conversation with: the first rung that is not
    resting. If every one is resting the ladder is used from the top anyway —
    refusing to connect at all is never the better answer."""
    from memory.config_manager import get_voice
    candidates = LIVE_MODELS[:1] if get_voice() == "Nika" else LIVE_MODELS
    for m in candidates:
        if not _cooling(m):
            return m
    return LIVE_MODELS[0]


def note_live_failure(model: str, err: str) -> bool:
    """Record why a Live model failed. True when it is worth trying the next.

    Only quota and availability move the ladder along. A bad API key or a
    dropped network is not the model's fault, and stepping down the ladder for
    those would work through every model and reach the same wall four times.
    """
    if is_quota_error(err):
        _cool(model, _COOLDOWN_SECONDS)
        print(f"[Gemini] Live model {model} is out of quota — "
              f"switching for {_COOLDOWN_SECONDS // 60} minutes.")
        return True
    if is_gone_error(err):
        _cool(model, _GONE_SECONDS)
        print(f"[Gemini] Live model {model} is unavailable to this key — "
              f"setting it aside.")
        return True
    return False


def _cooling(model: str) -> bool:
    with _cool_lock:
        until = _cooldown.get(model, 0.0)
        if until and time.monotonic() < until:
            return True
        _cooldown.pop(model, None)
        return False


def api_key(refresh: bool = False) -> str:
    """Return a single configured key; comma lists never reach the provider."""
    from core.gemini_keys import pool, KeysCooling
    try:
        return pool.select('rest')
    except (ValueError, KeysCooling):
        return ''


def client(timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = ""):
    """A configured genai.Client with a deadline on it. Raises if there is no
    key, because a caller that cannot work without one should say so."""
    from google import genai
    from google.genai import types as gtypes

    key = key or api_key()
    if not key:
        raise RuntimeError("no Gemini API key is configured")
    return genai.Client(
        api_key=key,
        http_options=gtypes.HttpOptions(timeout=max(MIN_TIMEOUT_MS, int(timeout_ms)),
                                        retry_options=gtypes.HttpRetryOptions(attempts=1)),
    )


class _Reply:
    """What a Live turn hands back, shaped like the REST response's `.text` so
    every existing call site keeps working unchanged."""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text


def _live_model() -> str:
    """Whatever main.py is running, so upgrading the assistant upgrades this."""
    return getattr(sys.modules.get("main"), "LIVE_MODEL", None) or _LIVE_FALLBACK


def _to_live_parts(contents) -> list:
    """REST `contents` -> Live `parts`. Accepts a bare string, a list of
    strings, and the SDK's Part objects (which is how every image is passed
    here), because those are the three shapes the call sites actually use."""
    import base64

    items = contents if isinstance(contents, (list, tuple)) else [contents]
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append({"text": item})
            continue
        blob = getattr(item, "inline_data", None)
        if blob is not None:
            data = getattr(blob, "data", None)
            mime = getattr(blob, "mime_type", None) or "application/octet-stream"
            if isinstance(data, bytes):
                data = base64.b64encode(data).decode("ascii")
            parts.append({"inline_data": {"mime_type": mime, "data": data}})
            continue
        txt = getattr(item, "text", None)
        if txt:
            parts.append({"text": txt})
            continue
        if isinstance(item, dict):
            parts.append(item)
    return parts


def _process_kind(mime: str) -> str:
    mime = str(mime or "").lower()
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "document"


def _process_blob(data, mime: str):
    """One inline byte payload in the interactions content shape."""
    import base64

    if isinstance(data, bytes):
        data = base64.b64encode(data).decode("ascii")
    if not data:
        return None
    mime = str(mime or "application/octet-stream")
    return {"type": _process_kind(mime), "data": data, "mime_type": mime}


def _to_process_input(contents) -> list:
    """REST/Live `contents` -> interactions content items.

    The interactions endpoint takes typed text/image/document/audio/video
    items. Zaya's call sites use strings, google.genai Part objects, plain
    inline_data dicts, PIL images and types.Content — accept all of them so a
    processing call looks the same to every existing caller.
    """
    import io

    items = contents if isinstance(contents, (list, tuple)) else [contents]
    out = []
    for item in items:
        if isinstance(item, str):
            if item:
                out.append({"type": "text", "text": item})
            continue
        if isinstance(item, dict):
            inline = item.get("inline_data")
            if isinstance(inline, dict):
                blob = _process_blob(inline.get("data"), inline.get("mime_type"))
                if blob:
                    out.append(blob)
            elif item.get("text"):
                out.append({"type": "text", "text": str(item["text"])})
            elif item.get("type") in {"text", "image", "document", "audio", "video"}:
                out.append(item)
            continue
        blob = getattr(item, "inline_data", None)
        if blob is not None:
            converted = _process_blob(
                getattr(blob, "data", None), getattr(blob, "mime_type", None))
            if converted:
                out.append(converted)
            continue
        file_data = getattr(item, "file_data", None)
        if file_data is not None:
            uri = getattr(file_data, "file_uri", None)
            mime = getattr(file_data, "mime_type", None) or ""
            if uri:
                out.append({"type": _process_kind(mime), "uri": uri,
                            "mime_type": mime})
            continue
        txt = getattr(item, "text", None)
        if txt:
            out.append({"type": "text", "text": str(txt)})
            continue
        parts = getattr(item, "parts", None)
        if parts:
            out.extend(_to_process_input(parts))
            continue
        # file_processor passes PIL images straight through.
        if hasattr(item, "save") and hasattr(item, "mode"):
            buf = io.BytesIO()
            item.save(buf, format="PNG")
            converted = _process_blob(buf.getvalue(), "image/png")
            if converted:
                out.append(converted)
    return out


async def _live_turn(parts: list, system: str, key: str, timeout_s: float) -> str:
    from google import genai
    from google.genai import types as gtypes

    cl = genai.Client(api_key=key, http_options={"api_version": "v1beta"})
    # Silence the persona, or it answers instead of complying.
    #
    # These are conversational models and they behave like it: asked "Reply with
    # one word: ok" a Live turn came back with "Understood." — it treated the
    # instruction as something to acknowledge rather than something to do. The
    # REST models do not, because nobody ever taught them to be in a
    # conversation. Every call through this module wants a value, not a reply,
    # so the session is told what it is before it is told what to do.
    kwargs = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
        "system_instruction": _ONE_SHOT_SYSTEM + (f"\n\n{system}" if system else ""),
    }

    cm = cl.aio.live.connect(model=_live_model(),
                             config=gtypes.LiveConnectConfig(**kwargs))
    session = await asyncio.wait_for(cm.__aenter__(), 30)
    try:
        await session.send_client_content(
            turns={"role": "user", "parts": parts}, turn_complete=True)
        chunks: list[str] = []

        async def drain():
            async for resp in session.receive():
                sc = getattr(resp, "server_content", None)
                if sc and sc.output_transcription and sc.output_transcription.text:
                    chunks.append(sc.output_transcription.text)

        await asyncio.wait_for(drain(), timeout=timeout_s)
        # The transcription can trail the audio turn by a beat; a short second
        # drain stops a reply being cut mid-token. chat_takeover learned this
        # the same way and for the same reason.
        try:
            await asyncio.wait_for(drain(), timeout=1.5)
        except asyncio.TimeoutError:
            pass
        return "".join(chunks).strip()
    finally:
        try:
            await cm.__aexit__(None, None, None)
        except Exception:
            pass


def _live_call(contents, config, timeout_ms: int, key: str):
    """One throwaway Live session, run on its own loop in its own thread.

    A dedicated thread rather than asyncio.run() on the caller's: these are
    invoked from plugin executor threads, from UI worker threads and from
    main.py's own event loop, and asyncio.run() inside a thread that already has
    a running loop raises. Its own thread has no loop to collide with, wherever
    it was called from.

    Reconnecting costs 0.24s, so nothing is kept alive between calls — no
    session lifetime cap to manage, no GoAway to handle, no shared state.
    """
    system = ""
    if config is not None:
        system = getattr(config, "system_instruction", None) or \
            (config.get("system_instruction") if isinstance(config, dict) else "") or ""

    parts = _to_live_parts(contents)
    if not parts:
        return None

    if not _LIVE_SLOTS.acquire(timeout=_LIVE_SLOT_WAIT):
        # Every slot is busy. Do not wait it out: falling to REST costs less
        # than holding a session the user's conversation might want.
        raise RuntimeError("no free Live slot — leaving them for the conversation")

    box: dict = {}
    cancelled = threading.Event()
    control_lock = threading.Lock()
    control: dict = {}

    async def execute():
        with control_lock:
            control.update(loop=asyncio.get_running_loop(), task=asyncio.current_task())
        if cancelled.is_set():
            return None
        return await _live_turn(parts, str(system), key, max(10.0, timeout_ms / 1000.0))

    def runner():
        try:
            text = asyncio.run(execute())
            if not cancelled.is_set():
                box["text"] = text
        except BaseException as e:                     # noqa: BLE001
            if not cancelled.is_set():
                box["error"] = e
        finally:
            # A stuck worker still owns its slot: never accumulate more Live
            # sessions than the limit by releasing before the worker exits.
            _LIVE_SLOTS.release()

    try:
        th = threading.Thread(target=runner, daemon=True, name="gemini-live-oneshot")
        th.start()
    except BaseException:
        _LIVE_SLOTS.release()
        raise
    th.join(timeout=max(15.0, timeout_ms / 1000.0 + 20.0))
    if th.is_alive():
        cancelled.set()
        with control_lock:
            loop, task = control.get('loop'), control.get('task')
        if loop is not None and task is not None:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # The worker already closed its loop.
        raise TimeoutError('One-shot Live request exceeded its deadline and was cancelled.')
    if "error" in box:
        raise box["error"]
    text = box.get("text")
    return _Reply(text) if text else None


def _process_call(contents, config, timeout_ms: int, key: str):
    """One reasoning request on the processing model.

    Returns a _Reply so callers see the same `.text` shape as a REST response.
    None means this rung should be skipped (tools were requested, or there was
    no usable input); the caller then falls through to the Live/REST ladder.
    """
    items = _to_process_input(contents)
    if not items:
        return None

    def setting(name, default=None):
        if isinstance(config, dict):
            return config.get(name, default)
        return getattr(config, name, default)

    system = str(setting("system_instruction") or "")
    gen = {"thinking_level": "high"}
    for field in ("temperature", "max_output_tokens", "top_p", "seed",
                  "stop_sequences"):
        value = setting(field)
        if value is not None:
            gen[field] = value

    thinking = setting("thinking_config")
    if thinking is not None:
        budget = (thinking.get("thinking_budget") if isinstance(thinking, dict)
                  else getattr(thinking, "thinking_budget", None))
        if isinstance(budget, (int, float)):
            # hydrogen rejects 'minimal'; low is its fastest supported level.
            # A negative budget means "let the model decide".
            gen["thinking_level"] = ("high" if budget < 0
                                     else "low" if budget <= 512
                                     else "medium" if budget <= 2048
                                     else "high")

    # Grounding and function declarations are part of the caller's contract;
    # this rung cannot honour them faithfully, so let the REST rung do it.
    if setting("tools"):
        return None

    kwargs = {
        "model": PROCESS_MODEL,
        "input": items if len(items) > 1 else items[0].get("text", items),
        "generation_config": gen,
        "timeout": max(10.0, timeout_ms / 1000.0),
        "system_instruction": _ONE_SHOT_SYSTEM + (
            "\n\n" + system if system else ""),
    }

    mime = str(setting("response_mime_type") or "")
    if mime:
        response_format = {"type": "text", "mime_type": mime}
        schema = setting("response_schema")
        if schema is not None:
            if hasattr(schema, "model_dump"):
                try:
                    schema = schema.model_dump(exclude_none=True)
                except Exception:
                    schema = None
            if isinstance(schema, dict):
                response_format["schema"] = schema
        kwargs["response_format"] = response_format

    cl = client(timeout_ms=timeout_ms, key=key)
    try:
        result = cl.interactions.create(**kwargs)
    finally:
        cl.close()

    text = str(getattr(result, "output_text", "") or "").strip()
    return _Reply(text) if text else None


def call(contents, tier: str = FAST, config=None,
         timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = ""):
    """Run one generation, walking the ladder until one answers.

    Returns the SDK's own response object (or a `.text`-shaped _Reply for the
    Live and processing rungs), so callers that need more than the text —
    grounding metadata, candidates, usage — still get it. Returns None when
    every model on the ladder failed; the reason for each is printed, since a
    silent None during a session nobody can debug is how the original problem
    stayed hidden.
    """
    # `tier` is normally FAST or SMART. Anything else is taken to be an explicit
    # model name — screen_agent lets the user pick one in its settings — and it
    # is tried first, with the reasoning ladder behind it. So a user's choice is
    # honoured, and a user's choice that is having an outage still degrades to
    # something that answers instead of to nothing.
    _STREAMING_ONLY = {
        "models/gemini-robotics-er-2-streaming-preview",
        "gemini-robotics-er-2-streaming-preview",
        "models/gemini-3.8-live",
        "gemini-3.8-live",
    }
    ladder = _LADDERS.get(tier)
    if ladder is None:
        if tier in _STREAMING_ONLY:
            # The explicitly requested streaming model cannot serve a REST text
            # turn. Keep that call on the Live rung instead of handing it to the
            # processing model the caller did not ask for.
            ladder = (LIVE,) + tuple(m for m in _LADDERS[SMART]
                                     if m not in (LIVE, PROCESS))
        elif tier in (PROCESS_MODEL, "models/" + PROCESS_MODEL):
            # The processing model is not a REST generate_content model; route
            # an explicit selection back through its own rung.
            ladder = (PROCESS,) + tuple(m for m in _LADDERS[SMART]
                                        if m != PROCESS)
        else:
            ladder = (tier,) + tuple(m for m in _LADDERS[SMART] if m != tier)

    from core.gemini_keys import pool, KeysCooling
    from core.audit import redact
    if not key and not pool.keys():
        print('[Gemini] no Gemini API keys are configured')
        return None
    tried = [m for m in ladder if not _cooling(m)] or list(ladder)
    for model in tried:
        if model == PROCESS and timeout_ms < PROCESS_MIN_TIMEOUT_MS:
            continue
        resource = 'helper:' + model
        for _attempt in range(1 if key else len(pool.keys())):
            try:
                resolved_key = key or pool.select(resource)
            except (KeysCooling, ValueError):
                break
            cl = None
            try:
                if model == PROCESS:
                    reply = _process_call(contents, config, timeout_ms, resolved_key)
                    if reply is not None:
                        return reply
                    raise RuntimeError('the processing turn came back empty')
                if model == LIVE:
                    reply = _live_call(contents, config, timeout_ms, resolved_key)
                    if reply is not None:
                        return reply
                    raise RuntimeError('the Live turn came back empty')
                cl = client(timeout_ms=timeout_ms, key=resolved_key)
                kwargs = {'model': model, 'contents': contents}
                if config is not None:
                    kwargs['config'] = config
                return cl.models.generate_content(**kwargs)
            except Exception as error:
                msg = str(error)
                if is_quota_error(msg):
                    if not key:
                        pool.limited(resolved_key, error, resource)
                        print(f'[Gemini] {model}: rate limit; checking the next configured key')
                        continue
                    _cool(model)
                elif is_gone_error(msg):
                    _cool(model, _GONE_SECONDS)
                elif "timeout" in msg.lower() or "timed out" in msg.lower():
                    # A slow reasoning rung that overran this call's deadline is
                    # not gone; rest it briefly and let the next rung answer.
                    _cool(model, 60)
                elif is_unavailable_error(msg):
                    _cool(model, _UNAVAILABLE_SECONDS)
                else:
                    print(f'[Gemini] {model}: {type(error).__name__}: {redact(msg)[:140]}')
                break
            finally:
                if cl is not None:
                    cl.close()
    return None


def text(contents, tier: str = FAST, config=None,
         timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = "", default: str = "") -> str:
    """`call`, reduced to the reply text. `default` when nothing answered."""
    resp = call(contents, tier=tier, config=config,
                timeout_ms=timeout_ms, key=key)
    if resp is None:
        return default
    return (getattr(resp, "text", None) or "").strip() or default


def as_json(contents, tier: str = FAST, config=None,
            timeout_ms: int = DEFAULT_TIMEOUT_MS, key: str = "", default=None):
    """`text`, parsed as JSON, tolerating the fences and prose a model wraps it
    in. `default` when nothing answered or the answer would not parse."""
    raw = text(contents, tier=tier, config=config, timeout_ms=timeout_ms, key=key)
    if not raw:
        return default
    if "{" in raw and "}" in raw:
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
    elif "[" in raw and "]" in raw:
        raw = raw[raw.find("["): raw.rfind("]") + 1]
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"[Gemini] reply was not JSON: {e}")
        return default
