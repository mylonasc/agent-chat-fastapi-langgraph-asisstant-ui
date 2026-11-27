"""One policy resolver for baked defaults, admin policy, and thread preferences."""

import hashlib
from copy import deepcopy
from importlib.util import find_spec

from .catalog import CATALOG, TOOLKITS, TOOLS, ids, installation_extras
from .store import SettingsStore


class ToolkitManager:
    def __init__(self, settings):
        self.allowed = ids(
            settings.allowed_toolsets
            if settings.allowed_toolsets is not None
            else settings.toolsets
        )
        selected = ids(settings.toolsets)
        if not set(selected) <= set(self.allowed):
            raise ValueError("toolsets must be a subset of allowed_toolsets")
        self.tool_names = {
            tool.name for name in self.allowed for tool in TOOLKITS[name].tools
        }
        self.defaults = {"toolsets": list(selected), "tools": {}}
        for name in self.tool_names:
            self.defaults["tools"][name] = {
                "enabled": True,
                "config": {
                    key: knob.default for key, knob in TOOLS[name].knobs.items()
                },
            }
        for name, config in settings.tool_config.items():
            if name not in self.tool_names:
                raise ValueError(f"Tool configuration outside allowed_toolsets: {name}")
            self.defaults["tools"][name]["config"].update(
                self.validate_config(name, config, "startup")
            )
        for name in self.allowed:
            missing = [
                module
                for module in TOOLKITS[name].dependencies
                if find_spec(module) is None
            ]
            if missing:
                raise ValueError(
                    f"Toolset {name} needs optional dependencies ({', '.join(missing)}). Install the '{installation_extras((name,))[0]}' extra."
                )
        self.store = SettingsStore(settings.tool_settings_path)
        self.web_data_path = settings.tool_data_path

    @staticmethod
    def thread_scope(thread_id, subject):
        # Owner-scoped storage also protects preferences when a deleted thread
        # ID is later reused by a different principal.
        return f"{hashlib.sha256(subject.encode()).hexdigest()}:{thread_id}"

    def validate_config(self, name, config, scope):
        if not isinstance(config, dict):
            # Invalid JSON settings use one validation error type at the API boundary.
            raise ValueError("Tool configuration must be an object")  # noqa: TRY004
        result = {}
        for key, value in config.items():
            knob = TOOLS[name].knobs.get(key)
            if knob is None:
                raise ValueError(f"Unknown setting {name}.{key}")
            if scope == "conversation" and knob.scope != "conversation":
                raise ValueError(f"{name}.{key} is not configurable per conversation")
            if scope == "admin" and knob.scope == "startup":
                raise ValueError(
                    f"{name}.{key} requires startup configuration and reindexing"
                )
            result[key] = knob.validate(value)
        return result

    def _global(self, saved):
        revision, state = saved.get("global", (0, {}))
        result = deepcopy(self.defaults)
        if "toolsets" in state:
            result["toolsets"] = [
                name for name in state["toolsets"] if name in self.allowed
            ]
        for name, values in state.get("tools", {}).items():
            if name not in self.tool_names:
                continue
            result["tools"][name]["enabled"] = values["enabled"]
            # Startup-only values always come from the current deployment.
            for key, value in values["config"].items():
                knob = TOOLS[name].knobs.get(key)
                if knob and knob.scope != "startup":
                    result["tools"][name]["config"][key] = knob.validate(value)
        return revision, result

    def snapshot(self, thread_id=None):
        scopes = ("global", f"thread:{thread_id}") if thread_id else ("global",)
        saved = self.store.read(*scopes)
        global_revision, policy = self._global(saved)
        revision, preference = (
            saved.get(f"thread:{thread_id}", (0, {}))
            if thread_id
            else (global_revision, policy)
        )
        selected = [
            name
            for name in preference.get("toolsets", policy["toolsets"])
            if name in self.allowed
        ]
        effective_sets = set(selected) & set(policy["toolsets"])
        enabled = {}
        toolkits = []
        for toolkit in CATALOG:
            if toolkit.id not in self.allowed:
                continue
            tools = []
            for spec in toolkit.tools:
                global_tool = policy["tools"][spec.name]
                overrides = (
                    preference.get("tools", {}).get(spec.name, {}) if thread_id else {}
                )
                config = {**global_tool["config"], **overrides.get("config", {})}
                available = toolkit.id in policy["toolsets"] and global_tool["enabled"]
                active = (
                    toolkit.id in effective_sets
                    and available
                    and overrides.get("enabled", True)
                )
                if active:
                    enabled[spec.name] = config
                tools.append(
                    {
                        "id": spec.name,
                        "title": spec.title,
                        "available": available,
                        "enabled": active,
                        "selected": overrides.get("enabled", global_tool["enabled"]),
                        "config": config,
                        "fields": {
                            key: knob.public() for key, knob in spec.knobs.items()
                        },
                    }
                )
            toolkits.append(
                {
                    "id": toolkit.id,
                    "title": toolkit.title,
                    "description": toolkit.description,
                    "available": toolkit.id in policy["toolsets"],
                    "selected": toolkit.id in selected,
                    "tools": tools,
                }
            )
        return {
            "revision": revision,
            "global_revision": global_revision,
            "toolsets": list(selected),
            "catalog": toolkits,
            "enabled_tools": enabled,
        }

    def update(self, payload, thread_id=None):
        current = self.snapshot(thread_id)
        selected = ids(payload.toolsets)
        if not set(selected) <= set(self.allowed):
            raise ValueError("Cannot enable toolsets outside the deployment allowlist")
        if thread_id:
            global_state = self.snapshot()
            if not set(selected) <= (
                set(global_state["toolsets"]) | set(current["toolsets"])
            ):
                raise ValueError("An administrator has disabled a selected toolset")
        scope = f"thread:{thread_id}" if thread_id else "global"
        previous = self.store.read(scope).get(scope, (0, {}))[1]
        # Treat tool entries as updates, retaining dormant preferences when a
        # global restriction temporarily makes their controls unavailable.
        tools = deepcopy(previous.get("tools", {}))
        for name, value in payload.tools.items():
            if name not in self.tool_names:
                raise ValueError(f"Unknown or disallowed tool {name}")
            if set(value) - {"enabled", "config"}:
                raise ValueError(f"Unknown tool fields for {name}")
            enabled = value.get("enabled", tools.get(name, {}).get("enabled", True))
            if type(enabled) is not bool:
                raise ValueError("enabled must be boolean")
            if thread_id and enabled:
                global_tool = next(
                    tool
                    for group in global_state["catalog"]
                    for tool in group["tools"]
                    if tool["id"] == name
                )
                previous_tool = next(
                    tool
                    for group in current["catalog"]
                    for tool in group["tools"]
                    if tool["id"] == name
                )
                if not global_tool["available"] and not previous_tool["selected"]:
                    raise ValueError(f"An administrator has disabled {name}")
            config = {
                **tools.get(name, {}).get("config", {}),
                **self.validate_config(
                    name,
                    value.get("config", {}),
                    "conversation" if thread_id else "admin",
                ),
            }
            tools[name] = {"enabled": enabled, "config": config}
        self.store.write(
            scope,
            payload.revision,
            {"toolsets": list(selected), "tools": tools},
            global_revision=payload.global_revision if thread_id else None,
        )
        return self.snapshot(thread_id)
