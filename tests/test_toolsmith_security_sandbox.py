import pytest
from core.toolsmith_engine import ToolsmithEngine

def test_ast_security_catches_attribute_escapes_and_disallowed_modules():
    engine = ToolsmithEngine()

    code_subclasses = '''
def bad_subclasses(params):
    return ().__class__.__bases__[0].__subclasses__()

TOOL = {"name": "bad", "description": "bad", "parameters": {"type": "OBJECT", "properties": {}}, "handler": bad_subclasses}
'''
    ok, reason = engine.validate_code_safety(code_subclasses)
    assert ok is False
    assert "forbidden" in reason.lower()

    code_os = '''
import os
def bad_os(params):
    return os.listdir('.')
TOOL = {"name": "bad_os", "description": "bad", "parameters": {"type": "OBJECT", "properties": {}}, "handler": bad_os}
'''
    ok_os, reason_os = engine.validate_code_safety(code_os)
    assert ok_os is False
    assert "approved safe modules list" in reason_os

    code_getattr = '''
def bad_getattr(params):
    return getattr(dict, '__init__')
TOOL = {"name": "bad_get", "description": "bad", "parameters": {"type": "OBJECT", "properties": {}}, "handler": bad_getattr}
'''
    ok_get, reason_get = engine.validate_code_safety(code_getattr)
    assert ok_get is False
    assert "getattr" in reason_get
