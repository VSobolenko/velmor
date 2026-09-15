from __future__ import annotations

import logfire

from packages.core.src.bootstrap.platform_settings import PlatformSettings


class Observability:
    """Process-wide tracing bootstrap.

    One instance is created by the composition root and configured once, before
    any agent graph is built. Framework instrumentation attaches to the
    OpenTelemetry provider that :func:`logfire.configure` registers, so a single
    call makes every span visible to every backend listening on it.
    """

    def __init__(self, service_name: str) -> None:
        self._service_name = service_name
        self._frameworks_instrumented = False

    def configure(self, settings: PlatformSettings) -> None:
        logfire.configure(
            token=settings.logfire_token.get_secret_value(),
            service_name=self._service_name,
            environment=settings.environment,
            console=False,
            send_to_logfire=settings.logfire_enabled,
        )
        if settings.logfire_enabled:
            self._instrument_frameworks()

    def _instrument_frameworks(self) -> None:
        """Attach LLM framework tracing to the global OpenTelemetry provider.

        The instrumentors are imported here rather than at module scope so that
        importing ``packages.core`` does not drag in the OpenAI, Anthropic and
        LangChain SDKs. Most callers - the rights engine, the connectors, the
        tests - never build a span, and paying for those imports on every process
        start would be cost without benefit.
        """
        if self._frameworks_instrumented:
            return

        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from openinference.instrumentation.openai import OpenAIInstrumentor

        logfire.instrument_pydantic_ai()
        LangChainInstrumentor().instrument()
        OpenAIInstrumentor().instrument()
        AnthropicInstrumentor().instrument()
        self._frameworks_instrumented = True
