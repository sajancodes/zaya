"""Action handler for Zaya intelligent model routing and health management.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from core.execution_policy import require_owner
from core.model_router import ComplexityTier, get_model_router
from core.tool_result import ToolResult


def model_routing_action(parameters: dict, **_kwargs) -> ToolResult:
    """Manage and inspect dynamic model routing and provider health."""
    action = (parameters.get("action") or "list").lower().strip()
    router = get_model_router()

    if action == "list":
        models = router.list_models()
        active = [m for m in models if m.get("enabled") and not m.get("in_cooldown")]
        return ToolResult(
            "success",
            f"Model Router: {len(active)} active / {len(models)} total registered models.",
            data={"models": models, "active_count": len(active)},
        )

    elif action == "route":
        comp_str = (parameters.get("complexity") or "standard").lower().strip()
        comp = {
            "light": ComplexityTier.LIGHT,
            "standard": ComplexityTier.STANDARD,
            "complex": ComplexityTier.COMPLEX,
            "reasoning": ComplexityTier.REASONING,
        }.get(comp_str, ComplexityTier.STANDARD)

        vision = bool(parameters.get("requires_vision", False))
        tools = bool(parameters.get("requires_tools", True))
        decision = router.route(complexity=comp, requires_vision=vision, requires_tools=tools)

        if decision.selected_model:
            return ToolResult(
                "success",
                decision.reason,
                data={
                    "selected_model": decision.selected_model.id,
                    "provider": decision.selected_model.provider.value,
                    "reason": decision.reason,
                    "evaluations": decision.candidates_evaluated,
                },
            )
        return ToolResult("failed", decision.reason, data={"evaluations": decision.candidates_evaluated})

    elif action == "reset":
        require_owner()
        router.reset_cooldowns()
        return ToolResult("success", "All model cooldowns and health penalties reset.", side_effect=True)

    elif action in {"enable", "disable"}:
        require_owner()
        model_id = parameters.get("model_id", "").strip()
        if not model_id:
            return ToolResult("failed", "Provide a model_id to enable or disable.")
        spec = router.get_model(model_id)
        if not spec:
            return ToolResult("failed", f"Model '{model_id}' not found in registry.")
        spec.enabled = (action == "enable")
        return ToolResult(
            "success",
            f"Model '{model_id}' is now {'enabled' if spec.enabled else 'disabled'}.",
            data={"model_id": model_id, "enabled": spec.enabled},
            side_effect=True,
        )

    return ToolResult("failed", f"Unknown action: '{action}'. Use list, route, reset, enable, disable.")


TOOL = {
    "name": "model_routing",
    "description": "Intelligent Model Routing & Health: Inspect registered models, check live health/cooldowns, and simulate routing decisions.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["list", "route", "reset", "enable", "disable"],
                "description": "list | route | reset | enable | disable",
            },
            "complexity": {
                "type": "STRING",
                "enum": ["light", "standard", "complex", "reasoning"],
                "description": "Task complexity for route simulation.",
            },
            "requires_vision": {"type": "BOOLEAN", "description": "True if task involves images/vision."},
            "requires_tools": {"type": "BOOLEAN", "description": "True if model must support function calling."},
            "model_id": {"type": "STRING", "description": "Model ID for enable/disable."},
        },
        "required": ["action"],
    },
    "handler": model_routing_action,
}
