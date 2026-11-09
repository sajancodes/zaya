import pytest
from pathlib import Path

def test_prompt_txt_enforces_strict_english():
    prompt_path = Path("core/prompt.txt")
    assert prompt_path.exists(), "core/prompt.txt must exist"
    content = prompt_path.read_text(encoding="utf-8")

    # Strict English rules must be present
    assert "Always speak and respond in English by default" in content
    assert "[DEFAULT LANGUAGE POLICY — STRICT ENGLISH]" in content
    assert "Even if the owner speaks in another language" in content or "Even if the user speaks another language" in content
    assert "¿Ya?" in content
    assert "talk in Nepali" in content

    # Obsolete auto-switching lines must NOT be present
    assert "Use the owner's language and its ordinary respectful address" not in content
    assert "Use the conversation's language." not in content


def test_main_system_prompt_includes_language_policy():
    main_path = Path("main.py")
    assert main_path.exists(), "main.py must exist"
    content = main_path.read_text(encoding="utf-8")

    # Check for strict language requirement context in main.py
    assert "[LANGUAGE REQUIREMENT — STRICT ENGLISH BY DEFAULT]" in content
    assert "You MUST ALWAYS speak and respond in ENGLISH by default" in content
    assert "¿Ya?" in content
    assert "talk in Nepali" in content
    assert "lang_policy_ctx" in content
    assert "parts = [time_ctx, identity_ctx, lang_policy_ctx, boundary_prompt()]" in content


def test_briefing_clauses_enforce_english():
    main_path = Path("main.py")
    content = main_path.read_text(encoding="utf-8")

    # Old auto-switching clauses must be gone
    assert "follow the user's own language from their first reply onward" not in content
    assert "unless the user has since spoken another language, in which case use theirs" not in content

    # English default briefing clauses must be present
    assert "Speak in English. Always remain in English" in content
