"""Hermes CLI delivery with transport evidence, stdin text, and durable dedup."""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import time
import requests
from core.audit import redact
from core.tool_result import ToolResult
from services.whatsapp.models import Message, validate_chat_id
from services.whatsapp.store import WhatsAppStore


class HermesAdapter:
    def __init__(self, store: WhatsAppStore, command: list[str] | None = None, runner=None, transport=None) -> None:
        self.store, self.command = store, command
        self.runner = runner or subprocess.run
        self.transport = transport

    def _command(self) -> list[str]:
        if self.command:
            return self.command
        executable = shutil.which('hermes')
        if not executable:
            raise FileNotFoundError('Hermes CLI is not installed or not on PATH.')
        if os.name == 'nt' and executable.lower().endswith(('.cmd', '.bat')):
            # Ask the trusted launcher for its native Python argv. Never pass
            # contact text through cmd.exe or a batch command line.
            output = self.runner([executable, '--print-runtime-command', 'send'], capture_output=True,
                                 text=True, encoding='utf-8', timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
            command = json.loads(output.stdout)
            if output.returncode or not isinstance(command, list) or not all(isinstance(x, str) for x in command):
                raise RuntimeError('Hermes did not return a native runtime command.')
            self.command = command
        else:
            self.command = [executable, 'send']
        return self.command

    def send(self, chat_id: str, text: str, request_id: str, reply_to_id: str | None = None) -> ToolResult:
        validate_chat_id(chat_id)
        if not text.strip() or len(text) > 20000 or not request_id:
            return ToolResult('failed', 'Message text and an idempotency request ID are required.')
        if re.search(r'(?i)MEDIA\s*:|\[\[', text):
            return ToolResult('failed', 'Transport attachment/control directives are not allowed in text messages.')
        previous = self.store.rows('SELECT * FROM wa_send_intents WHERE request_id=?', (request_id,))
        if previous:
            item = previous[0]
            if item['chat_id'] != chat_id or item['text'] != text:
                return ToolResult('failed', 'Request ID already belongs to a different message.')
            return ToolResult('success' if item['status'] == 'accepted' else 'partial',
                              'Message already accepted; it was not sent again.' if item['status'] == 'accepted' else 'Prior send is failed or uncertain; inspect it before explicitly retrying.',
                              {'message_id': item['message_id'], 'transport_status': item['status'], 'deduplicated': True},
                              [{'message_id': item['message_id'], 'request_id': request_id}], side_effect=item['status'] == 'accepted')
        try:
            command = self._command() if self.transport is None else None
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            return ToolResult('failed', f'Hermes unavailable: {error}')
        if not self.store.reserve_send(request_id, chat_id, text):
            return ToolResult('partial', 'Another worker has reserved this send; no duplicate was sent.')
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        try:
            if self.transport is not None:
                completed = self.transport.send(chat_id, text, reply_to_id)
            else:
                completed = self.runner([*command, '--to', 'whatsapp:' + chat_id, '--json', '--file', '-'],
                                        input=text, capture_output=True, text=True, encoding='utf-8', timeout=60, **options)
            payload = json.loads(completed.stdout or '{}')
            message_id = payload.get('message_id')
            accepted = completed.returncode == 0 and payload.get('success') is True and bool(message_id) and not payload.get('error')
            if accepted:
                message_id = str(message_id)
                self.store.finish_send(request_id, 'accepted', message_id, 'Hermes accepted the message.')
                self.store.ingest(Message(message_id, chat_id, 'zaya', text, time.time(), 'outgoing', 'zaya',
                                          ai_generated=True, reply_to_id=reply_to_id, transport_status='accepted'))
                return ToolResult('success', 'Hermes accepted the message; recipient read/delivery receipts are not available.',
                                  {'message_id': message_id, 'transport_status': 'accepted'},
                                  [{'message_id': message_id, 'exit_code': completed.returncode}], side_effect=True)
            detail = str(redact(payload.get('error') or 'Hermes returned no confirmed message identifier.'))[:500]
            status = 'failed' if completed.returncode != 0 or payload.get('error') else 'unknown'
            self.store.finish_send(request_id, status, None, detail)
            return ToolResult('failed' if status == 'failed' else 'partial', detail,
                              {'transport_status': status}, [{'exit_code': completed.returncode}], side_effect=True)
        except (OSError, ValueError, subprocess.SubprocessError, requests.RequestException) as error:
            self.store.finish_send(request_id, 'unknown', None, str(redact(str(error)))[:500])
            return ToolResult('partial', 'Transport outcome is unknown; message will not be resent automatically.',
                              {'transport_status': 'unknown'}, side_effect=True)
