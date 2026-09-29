"""Provider-neutral chat model configuration and construction."""

import os
from dataclasses import dataclass, field
from typing import Any, Mapping

from langchain_core.language_models.chat_models import BaseChatModel


@dataclass(frozen=True)
class ModelConfig:
    """Describe a chat model without putting credentials in application config.

    ``model`` is opaque to this package.  In particular, values such as
    ``llama3.1:8b`` and ``anthropic/claude-sonnet-4-5`` are forwarded unchanged.
    ``credential_env`` names an environment variable; its value is only read
    while constructing the selected model.
    """

    model: str
    provider: str = "openai"
    base_url: str | None = None
    credential_env: str | None = None
    kwargs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if self.base_url is not None and not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if self.credential_env is not None and not self.credential_env.strip():
            raise ValueError("credential_env must not be empty")

    @classmethod
    def from_spec(cls, spec: str) -> "ModelConfig":
        """Parse the legacy ``provider:model`` syntax without parsing model ids."""
        if not spec.strip():
            raise ValueError("model spec must not be empty")
        provider, separator, model = spec.partition(":")
        if not separator:
            return cls(model=spec)
        return cls(provider=provider, model=model)

    @property
    def spec(self) -> str:
        """Return the legacy LangChain model specification."""
        return f"{self.provider}:{self.model}"

    def construction_kwargs(self) -> dict[str, Any]:
        """Return model kwargs with an optional referenced credential injected."""
        kwargs = dict(self.kwargs)
        if self.base_url is not None:
            kwargs.setdefault("base_url", self.base_url)
        if self.credential_env is not None:
            credential = os.getenv(self.credential_env)
            if credential:
                kwargs.setdefault("api_key", credential)
        return kwargs


def resolve_model(model: str | ModelConfig | BaseChatModel) -> BaseChatModel:
    """Resolve a legacy spec, structured config, or injected chat model.

    Most integrations are delegated to LangChain's generic initializer. LiteLLM
    has its own optional LangChain integration and is intentionally constructed
    lazily so it does not become a base dependency.
    """
    if isinstance(model, BaseChatModel):
        return model
    config = ModelConfig.from_spec(model) if isinstance(model, str) else model
    if config.provider == "litellm":
        return _resolve_litellm(config)

    from langchain.chat_models import init_chat_model

    return init_chat_model(config.spec, streaming=True, **config.construction_kwargs())


def _resolve_litellm(config: ModelConfig) -> BaseChatModel:
    try:
        from langchain_litellm import ChatLiteLLM
    except ImportError as exc:
        raise ImportError(
            "LiteLLM models require the 'litellm' extra: "
            "pip install 'agent-chat-fastapi-langgraph-assistant-ui[litellm]'"
        ) from exc

    kwargs = config.construction_kwargs()
    if "base_url" in kwargs:
        # ChatLiteLLM uses LiteLLM's api_base spelling rather than ChatOpenAI's
        # base_url spelling.
        kwargs.setdefault("api_base", kwargs.pop("base_url"))
    return ChatLiteLLM(model=config.model, streaming=True, **kwargs)
