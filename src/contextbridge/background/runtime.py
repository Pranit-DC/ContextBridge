"""Optional provider assembly is local configuration, never a fake production default."""

import importlib
from dataclasses import dataclass, field

from contextbridge.engine.modules import ModuleGateway


@dataclass(frozen=True)
class WorkerProviders:
    modules: ModuleGateway = field(default_factory=ModuleGateway)
    embedder: object | None = None
    verifier: object | None = None
    factory: object | None = None
    configuration: object | None = field(default=None, kw_only=True)
    execution_guard: object | None = None

    def fresh(self):
        return self.factory() if self.factory is not None else self

    def bind_guard(self, guard):
        if self.execution_guard is not None:
            self.execution_guard(guard)


def load_providers(settings, sessions):
    if (
        settings.integration_factory is not None
        or settings.embedding_provider is not None
        or settings.formation_enabled
        or settings.provider_settings_file is not None
    ):
        from contextbridge.runtime import load_integration

        return load_integration(settings, sessions)
    if settings.worker_factory is None:
        raise ValueError("PROVIDER_UNAVAILABLE")
    module_name, name = settings.worker_factory.split(":")
    providers = getattr(importlib.import_module(module_name), name)(settings, sessions)
    if not isinstance(providers, WorkerProviders):
        raise ValueError("INVALID_PROVIDER_OUTPUT")
    return providers
