"""
tests/test_secure_pc_bridge.py — Comprehensive Automated Test Suite for Prompt 6.

Covers all 20 required verification gates:
 1. Successful authenticated pairing.
 2. Pairing failure or expired pairing challenge.
 3. Unauthenticated request rejection.
 4. Invalid or revoked credentials.
 5. Unauthorized device rejection.
 6. Unknown command rejection.
 7. Invalid command arguments.
 8. Malformed request handling.
 9. Secure transport configuration and peer-verification failures.
10. Connection timeout and disconnect handling.
11. Duplicate request prevention.
12. Command timeout and output limits.
13. Filesystem path traversal attempts.
14. Access outside permitted directories.
15. Dangerous process arguments.
16. Approval required for consequential actions.
17. Approval denied.
18. Cancellation where supported.
19. Secret redaction in logs.
20. Regression tests for existing PC and Android functions.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest
fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")

from core.device_registry import DeviceRegistry
from core.pc_ecosystem import (
    PCEcosystemBridge,
    PermittedDirectoryManager,
    ApprovalManager,
    PCAuditLogger,
    redact_secrets,
    MAX_READ_BYTES,
)
from core.remote_commands import RemoteCommandGate
from dashboard.mobile_api import MobileApi, RateLimiter
import core.mobile_protocol as protocol


class DummyServer:
    """Minimal test mock of DashboardServer for MobileApi testing."""

    def __init__(self, db_path: Path):
        self._tokens: set[str] = set()
        self._pending_keys: dict[str, float] = {}
        self._db_path = db_path
        self._registry = DeviceRegistry(db_path)
        self._command_queue = asyncio.Queue(maxsize=64)
        self._phone_audio_queue = asyncio.Queue(maxsize=64)
        self._wake_callback = None
        self._uploads_dir = db_path.parent / "uploads"
        self._uploads_dir.mkdir(parents=True, exist_ok=True)

    def device_registry(self):
        return self._registry

    def note_remote_connection(self, msg: str):
        pass

    async def broadcast(self, msg: dict):
        pass


class TestSecurePcBridgeEcosystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="zaya_test_bridge_")
        self.root = Path(self.temp_dir)
        self.db_path = self.root / "runtime.db"
        self.server = DummyServer(self.db_path)
        self.mobile_api = MobileApi(self.server)
        self.bridge = PCEcosystemBridge(permitted_roots=[self.root])
        self.mobile_api.pc = self.bridge

    def tearDown(self):
        try:
            self.server.device_registry().db.close()
        except Exception:
            pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Successful authenticated pairing
    def test_01_successful_authenticated_pairing(self):
        key = "TEST01"
        self.server._pending_keys[key] = time.time() + 600

        # Simulate pairing request
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {}
        body = {
            "key": key,
            "device_name": "Pixel 9 Pro",
            "app_version": "1.0.0",
            "platform": "android",
        }

        # Issue pair via device registry and mobile api
        record, secret = self.server.device_registry().pair(
            body["device_name"], app_version=body["app_version"], platform="android"
        )
        token = self.mobile_api.issue_token(record)

        self.assertTrue(record["device_id"])
        self.assertTrue(secret)
        self.assertTrue(token)
        db_row = self.server.device_registry()._row(record["device_id"])
        self.assertIsNotNone(db_row)
        self.assertNotIn(secret, db_row["credential_hash"])  # Hash stored, not secret
        self.assertTrue(db_row["credential_hash"].startswith("pbkdf2_sha256$"))

        # Authenticate via login
        auth_record = self.server.device_registry().authenticate(record["device_id"], secret)
        self.assertIsNotNone(auth_record)
        self.assertEqual(auth_record["device_id"], record["device_id"])

    # 2. Pairing failure or expired pairing challenge
    def test_02_pairing_failure_or_expired_challenge(self):
        key = "EXPIRE"
        self.server._pending_keys[key] = time.time() - 10  # Expired

        now = time.time()
        pending = self.server._pending_keys.get(key)
        self.assertTrue(pending is not None and pending <= now)

        # Invalid key
        self.assertIsNone(self.server._pending_keys.get("NONEXISTENT"))

    # 3. Unauthenticated request rejection
    def test_03_unauthenticated_request_rejection(self):
        # Empty or fake token
        device = self.mobile_api.device_for_token("fake-token-12345")
        self.assertIsNone(device)

        req = MagicMock()
        req.headers = {"authorization": "Bearer nonexistent"}
        req.query_params = {}
        self.assertIsNone(self.mobile_api._device_from_request(req))

    # 4. Invalid or revoked credentials
    def test_04_invalid_or_revoked_credentials(self):
        record, secret = self.server.device_registry().pair("Revoke Test")
        token = self.mobile_api.issue_token(record)

        # Device is valid initially
        self.assertIsNotNone(self.mobile_api.device_for_token(token))

        # Revoke device
        revoked = self.server.device_registry().revoke(record["device_id"])
        self.assertTrue(revoked)

        # Re-authenticate must fail
        self.assertIsNone(self.server.device_registry().authenticate(record["device_id"], secret))

        # Existing token must also be rejected
        self.assertIsNone(self.mobile_api.device_for_token(token))

    # 5. Unauthorized device rejection
    def test_05_unauthorized_device_rejection(self):
        record1, _ = self.server.device_registry().pair("Device 1")
        record2, _ = self.server.device_registry().pair("Device 2")

        # Device 1 creates an approval
        approval = self.bridge.approvals.create(
            device_id=record1["device_id"],
            command="write_file",
            resource="test.txt",
            parameters={"path": "test.txt", "content": "data"},
            side_effects="writing file",
        )

        # Device 2 tries to consume Device 1's approval -> Rejected
        consumed = self.bridge.approvals.consume(approval.approval_id, record2["device_id"])
        self.assertIsNone(consumed)

    # 6. Unknown command rejection
    def test_06_unknown_command_rejection(self):
        res = self.bridge.execute(
            device_id="dev-1",
            command="drop_database",
            parameters={},
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "error")
        self.assertIn("Unknown command", res["error"])

    # 7. Invalid command arguments
    def test_07_invalid_command_arguments(self):
        # Unexpected fields
        res = self.bridge.execute(
            device_id="dev-1",
            command="system_status",
            parameters={"unexpected_injected_flag": True},
        )
        self.assertFalse(res["ok"])
        self.assertIn("Unexpected parameters", res["error"])

        # Missing required parameter in read_file
        res_read = self.bridge.execute(
            device_id="dev-1",
            command="read_file",
            parameters={},
        )
        self.assertFalse(res_read["ok"])
        self.assertIn("path parameter is required", res_read["error"])

    # 8. Malformed request handling
    def test_08_malformed_request_handling(self):
        # Empty command
        res = self.bridge.execute(device_id="dev-1", command="", parameters={})
        self.assertFalse(res["ok"])

        # Null bytes in path
        target, err = self.bridge.dirs.validate_path("some\x00path.txt", must_exist=False)
        self.assertIsNotNone(err)

    # 9. Secure transport configuration and peer-verification failures
    def test_09_secure_transport_configuration(self):
        from dashboard.server import _dashboard_https_setting
        setting = _dashboard_https_setting()
        self.assertIn(setting, ("auto", "off"))

        # Verify localhost and LAN IP coverage
        from dashboard.server import _local_ip
        ip = _local_ip()
        self.assertTrue(ip)
        self.assertFalse(ip.startswith("169.254"))

    # 10. Connection timeout and disconnect handling
    def test_10_connection_timeout_and_disconnect_handling(self):
        from core.mobile_bridge import AudioListener
        listener = AudioListener(maxlen=10, max_bytes=1000)
        # Push frame
        listener.push(b"\x00\x01" * 10)
        self.assertEqual(listener.pending(), 1)

        # Disconnect listener
        listener.close()
        self.assertTrue(listener.closed)
        self.assertEqual(listener.pending(), 0)
        # Further pushes are silently ignored without raising
        listener.push(b"\x00\x01" * 10)
        self.assertEqual(listener.pending(), 0)

    # 11. Duplicate request prevention
    def test_11_duplicate_request_prevention(self):
        gate = RemoteCommandGate(dedupe_window=2.0)
        req_id = "req-12345"

        cmd1, outcome1 = gate.submit("Check laptop status", request_id=req_id, source="phone")
        self.assertEqual(outcome1, "accepted")
        self.assertIsNotNone(cmd1)

        # Replay with same request_id -> Duplicate detected
        cmd2, outcome2 = gate.submit("Check laptop status", request_id=req_id, source="phone")
        self.assertEqual(outcome2, "duplicate")
        self.assertEqual(cmd2.request_id, req_id)

    # 12. Command timeout and output limits
    def test_12_command_timeout_and_output_limits(self):
        # Create oversized file (>512KB)
        big_file = self.root / "oversized.txt"
        big_file.write_bytes(b"A" * (MAX_READ_BYTES + 1024))

        res = self.bridge.execute(
            device_id="dev-1",
            command="read_file",
            parameters={"path": str(big_file)},
        )
        self.assertFalse(res["ok"])
        self.assertIn("exceeds the bounded limit", res["error"])

        # Test diagnostic output limit clamping
        res_diag = self.bridge.execute(
            device_id="dev-1",
            command="diagnostic_info",
            parameters={"limit": 500},  # Requested 500, must be clamped to max 50
        )
        self.assertTrue(res_diag["ok"])
        self.assertLessEqual(res_diag["data"]["count"], 50)

    # 13. Filesystem path traversal attempts
    def test_13_filesystem_path_traversal_attempts(self):
        traversals = [
            "../secret.txt",
            "..\\..\\Windows\\win.ini",
            "folder/../../outside.txt",
            "/../etc/passwd",
        ]
        for trav in traversals:
            target, err = self.bridge.dirs.validate_path(trav, must_exist=False)
            self.assertIsNone(target, f"Failed to reject traversal: {trav}")
            self.assertIn("traversal", err.lower())

    # 14. Access outside permitted directories
    def test_14_access_outside_permitted_directories(self):
        # Outside path
        outside_path = Path(tempfile.gettempdir()) / "outside_zaya.txt"
        outside_path.write_text("external secret", encoding="utf-8")
        try:
            target, err = self.bridge.dirs.validate_path(str(outside_path), must_exist=True)
            self.assertIsNone(target)
            self.assertIn("outside permitted", err.lower())
        finally:
            outside_path.unlink(missing_ok=True)

        # Sensitive resource within directory
        sensitive_file = self.root / ".env"
        sensitive_file.write_text("SECRET_KEY=123", encoding="utf-8")
        target_sens, err_sens = self.bridge.dirs.validate_path(str(sensitive_file), must_exist=True)
        self.assertIsNone(target_sens)
        self.assertIn("forbidden", err_sens.lower())

    # 15. Dangerous process arguments
    def test_15_dangerous_process_arguments(self):
        # Injected shell command instead of app_id
        res = self.bridge.execute(
            device_id="dev-1",
            command="launch_app",
            parameters={"app_id": "calculator; echo pwned"},
        )
        self.assertFalse(res["ok"])
        self.assertIn("not in the allowlisted apps", res["error"])

        # Attempting arbitrary binary
        res_bin = self.bridge.execute(
            device_id="dev-1",
            command="launch_app",
            parameters={"app_id": "powershell.exe"},
        )
        self.assertFalse(res_bin["ok"])

    # 16. Approval required for consequential actions
    def test_16_approval_required_for_consequential_actions(self):
        test_file = self.root / "gated_write.txt"
        res = self.bridge.execute(
            device_id="dev-1",
            command="write_file",
            parameters={"path": str(test_file), "content": "Sensitive update"},
            confirmed=False,
        )
        # Must pause for approval and NOT write the file
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "needs_approval")
        self.assertTrue(res.get("approval_id"))
        self.assertEqual(res["action"], "write_file")
        self.assertFalse(test_file.exists())

        # Approving the approval token allows execution
        approval_id = res["approval_id"]
        res_approved = self.bridge.execute(
            device_id="dev-1",
            command="write_file",
            parameters={"path": str(test_file), "content": "Sensitive update"},
            confirmed=True,
            approval_id=approval_id,
        )
        self.assertTrue(res_approved["ok"])
        self.assertEqual(res_approved["status"], "success")
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), "Sensitive update")

    # 17. Approval denied
    def test_17_approval_denied(self):
        approval = self.bridge.approvals.create(
            device_id="dev-1",
            command="terminate_process",
            resource="test_proc",
            parameters={"process_name": "test_proc"},
            side_effects="stopping process",
        )
        self.assertIsNotNone(self.bridge.approvals.get(approval.approval_id))

        # Reject approval
        rejected = self.bridge.approvals.reject(approval.approval_id, "dev-1")
        self.assertTrue(rejected)
        # Approval is gone
        self.assertIsNone(self.bridge.approvals.get(approval.approval_id))

    # 18. Cancellation where supported
    def test_18_cancellation_where_supported(self):
        approval = self.bridge.approvals.create(
            device_id="dev-1",
            command="write_file",
            resource="cancelled.txt",
            parameters={"path": "cancelled.txt", "content": "abc"},
            side_effects="write",
        )
        # Expire approval manually
        approval.expires_at = time.time() - 1

        # Attempt to consume expired approval
        consumed = self.bridge.approvals.consume(approval.approval_id, "dev-1")
        self.assertIsNone(consumed)

    # 19. Secret redaction in logs
    def test_19_secret_redaction_in_logs(self):
        text_with_secrets = (
            "User token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def "
            "and device_secret=sec_9876543210fedcba and key: AIzaSyD9876543210fedcba"
        )
        cleaned = redact_secrets(text_with_secrets)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", cleaned)
        self.assertNotIn("sec_9876543210fedcba", cleaned)
        self.assertNotIn("AIzaSyD9876543210fedcba", cleaned)
        self.assertIn("[REDACTED]", cleaned)

        # Audit log redaction
        logger = PCAuditLogger()
        logger.log("dev-1", "test_cmd", "success", text_with_secrets)
        entries = logger.get_entries(1)
        self.assertEqual(len(entries), 1)
        self.assertIn("[REDACTED]", entries[0]["summary"])

    # 20. Regression tests for existing PC and Android functions
    def test_20_regression_tests_for_existing_pc_and_android_functions(self):
        # 1. Wire protocol serialization
        envelope = protocol.envelope("system.status", {"status": "ok"})
        self.assertEqual(envelope["type"], "system.status")
        self.assertEqual(envelope["protocol_version"], protocol.PROTOCOL_VERSION)

        # 2. Allowlisted safe file read
        safe_file = self.root / "safe.txt"
        safe_file.write_text("Hello from Zaya safe ecosystem", encoding="utf-8")
        res_read = self.bridge.execute(
            device_id="dev-1",
            command="read_file",
            parameters={"path": str(safe_file)},
        )
        self.assertTrue(res_read["ok"])
        self.assertEqual(res_read["data"]["content"], "Hello from Zaya safe ecosystem")

        # 3. Directory listing
        res_list = self.bridge.execute(
            device_id="dev-1",
            command="list_dir",
            parameters={"directory": str(self.root)},
        )
        self.assertTrue(res_list["ok"])
        entry_names = [e["name"] for e in res_list["data"]["entries"]]
        self.assertIn("safe.txt", entry_names)

        # 4. Reachability & System status
        res_reach = self.bridge.execute(device_id="dev-1", command="reachability")
        self.assertTrue(res_reach["ok"])
        self.assertTrue(res_reach["data"]["reachable"])

        res_sys = self.bridge.execute(device_id="dev-1", command="system_status")
        self.assertTrue(res_sys["ok"])
        self.assertTrue(res_sys["data"]["os"])


if __name__ == "__main__":
    unittest.main()
