"""Zaya regression and operator acceptance tests."""

# Tests simulate owner-level operations. The production default is fail-closed
# (TRUST_UNKNOWN), so we must explicitly establish owner trust for the test process.
# Individual tests that verify non-owner trust behaviour set their own context and
# reset it in a finally block, overriding this default for their scope.
from core.execution_policy import trust_context, TRUST_LOCAL_OWNER as _TRUST_LOCAL_OWNER  # noqa: E402
trust_context.set(_TRUST_LOCAL_OWNER)
