"""Architecture boundaries.

The dependency direction in ``.cursor/rules/02-architecture-layers.mdc`` is a
claim about the code. This module is what keeps it true: a rule file can be
ignored by accident, and a reviewer reading a diff cannot see an import that
quietly points the wrong way.

Two things are asserted:

* A package imports only the layers beneath it. ``packages/core`` knowing that
  agents exist would make the core untestable and the direction reversible.
* The deterministic surface - rights, domain, screening - does not import the
  agent stack at all. That is what makes a verdict reproducible and auditable.

The scan parses every module with ``ast``, including an import written inside a
function, because a deferred import still creates the dependency.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from packages.core.src.bootstrap.project_root import PROJECT_ROOT

# A layer name maps to the module prefix that identifies it.
LAYER_PREFIXES: dict[str, str] = {
    'core': 'packages.core',
    'services': 'packages.services',
    'scout': 'packages.scout',
    'auditor': 'packages.auditor',
    'api': 'packages.api',
    'velmor': 'velmor',
}

# Which layers each layer may import, itself included. The composition root is the
# only place that may see all of them.
ALLOWED_IMPORTS: dict[str, frozenset[str]] = {
    'core': frozenset({'core'}),
    'services': frozenset({'core', 'services'}),
    'scout': frozenset({'core', 'services', 'scout'}),
    'auditor': frozenset({'core', 'services', 'auditor'}),
    'api': frozenset({'core', 'services', 'api'}),
    'velmor': frozenset(LAYER_PREFIXES),
}

# Directories whose contents must be a pure function of their inputs.
DETERMINISTIC_DIRECTORIES: frozenset[str] = frozenset({'rights', 'domain', 'screening'})

# Root module names that would put a model or a graph inside a rights decision.
AGENT_STACK_MODULES: frozenset[str] = frozenset(
    {
        'anthropic',
        'deepagents',
        'langchain',
        'langchain_core',
        'langgraph',
        'langfuse',
        'openai',
        'pydantic_ai',
    }
)

SEARCH_ROOTS: tuple[str, ...] = ('packages', 'velmor')
EXCLUDED_DIRECTORIES: frozenset[str] = frozenset({'__pycache__', 'tests'})


@dataclass(frozen=True)
class Violation:
    """One import that breaks an architectural rule."""

    path: Path
    origin: str
    target: str


class SourceModules:
    """Read the import statements of every module in the repository."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._files: tuple[Path, ...] = self._discover()

    def files(self) -> tuple[Path, ...]:
        return self._files

    def layer_of(self, path: Path) -> str | None:
        """Return the layer a module belongs to, or ``None`` if it is not layered.

        A file sitting directly in ``packages/`` is packaging, not a layer.
        """
        parts = path.relative_to(self.root).parts
        if parts[0] == 'velmor':
            return 'velmor'
        if len(parts) < 3:
            return None
        return parts[1]

    def is_deterministic(self, path: Path) -> bool:
        parts = path.relative_to(self.root).parts
        if parts[:3] != ('packages', 'services', 'src'):
            return False
        return len(parts) > 3 and parts[3] in DETERMINISTIC_DIRECTORIES

    @staticmethod
    def layer_of_import(module: str) -> str | None:
        for layer, prefix in LAYER_PREFIXES.items():
            if module == prefix or module.startswith(f'{prefix}.'):
                return layer
        return None

    @staticmethod
    def imports_of(path: Path) -> tuple[str, ...]:
        """Every module this file imports, deferred imports included."""
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules.append(node.module)
        return tuple(modules)

    def _discover(self) -> tuple[Path, ...]:
        found: list[Path] = []
        for search_root in SEARCH_ROOTS:
            base = self.root / search_root
            discovered = sorted(base.rglob('*.py'))
            found.extend(path for path in discovered if not self._is_excluded(path))
        return tuple(found)

    def _is_excluded(self, path: Path) -> bool:
        parts = path.relative_to(self.root).parts
        return not EXCLUDED_DIRECTORIES.isdisjoint(parts)


class ArchitectureAudit:
    """Both boundary checks, over one scan of the repository."""

    def __init__(self, modules: SourceModules) -> None:
        self._modules = modules

    def layering_violations(self) -> tuple[Violation, ...]:
        """Imports that point against the fixed dependency direction."""
        found: list[Violation] = []
        for path in self._modules.files():
            origin = self._modules.layer_of(path)
            if origin is None:
                continue
            found.extend(self._layering_violations_of(path, origin))
        return tuple(found)

    def purity_violations(self) -> tuple[Violation, ...]:
        """Agent-stack imports inside the deterministic surface."""
        found: list[Violation] = []
        for path in self._modules.files():
            if not self._modules.is_deterministic(path):
                continue
            found.extend(self._purity_violations_of(path))
        return tuple(found)

    def report(self, violations: tuple[Violation, ...]) -> str:
        return '\n'.join(
            f'  {violation.path.as_posix()}: {violation.origin} -> {violation.target}'
            for violation in violations
        )

    def _layering_violations_of(self, path: Path, origin: str) -> list[Violation]:
        allowed = ALLOWED_IMPORTS[origin]
        found: list[Violation] = []
        for module in self._modules.imports_of(path):
            target = self._modules.layer_of_import(module)
            if target is not None and target not in allowed:
                found.append(
                    Violation(
                        path=path.relative_to(self._modules.root), origin=origin, target=module
                    )
                )
        return found

    def _purity_violations_of(self, path: Path) -> list[Violation]:
        found: list[Violation] = []
        for module in self._modules.imports_of(path):
            if module.split('.')[0] not in AGENT_STACK_MODULES:
                continue
            found.append(
                Violation(
                    path=path.relative_to(self._modules.root),
                    origin='deterministic',
                    target=module,
                )
            )
        return found


class TestSourceModules:
    """The scanner must be trustworthy before it can judge anything."""

    def test_scan_finds_the_repository(self) -> None:
        assert len(SourceModules(PROJECT_ROOT).files()) > 30

    def test_imports_are_parsed_from_a_real_module(self) -> None:
        target = PROJECT_ROOT / 'packages' / 'services' / 'src' / 'rights' / 'engine.py'
        imports = SourceModules(PROJECT_ROOT).imports_of(target)
        assert 'packages.services.src.rights.publication_gate' in imports

    def test_deferred_imports_are_parsed(self) -> None:
        # velmor/cli.py imports the agents inside AgentDispatcher.dispatch, not at
        # module scope, and the dependency still has to be visible.
        imports = SourceModules(PROJECT_ROOT).imports_of(PROJECT_ROOT / 'velmor' / 'cli.py')
        assert 'velmor.agents.scout' in imports

    def test_packaging_files_have_no_layer(self) -> None:
        packaging = PROJECT_ROOT / 'packages' / '__init__.py'
        assert SourceModules(PROJECT_ROOT).layer_of(packaging) is None

    def test_a_layer_module_resolves_to_its_layer(self) -> None:
        module = PROJECT_ROOT / 'packages' / 'api' / 'src' / 'routers' / '__init__.py'
        assert SourceModules(PROJECT_ROOT).layer_of(module) == 'api'


class TestLayering:
    def test_dependency_direction_is_respected(self) -> None:
        audit = ArchitectureAudit(SourceModules(PROJECT_ROOT))
        violations = audit.layering_violations()
        # The report is built only when the assertion fails.
        assert not violations, audit.report(violations)

    def test_every_layer_is_described(self) -> None:
        assert set(ALLOWED_IMPORTS) == set(LAYER_PREFIXES)

    def test_composition_root_may_import_every_layer(self) -> None:
        assert ALLOWED_IMPORTS['velmor'] == frozenset(LAYER_PREFIXES)

    def test_core_may_import_nothing_above_it(self) -> None:
        assert ALLOWED_IMPORTS['core'] == frozenset({'core'})

    def test_services_never_imports_an_agent(self) -> None:
        assert ALLOWED_IMPORTS['services'] == frozenset({'core', 'services'})

    def test_an_agent_never_imports_another_agent(self) -> None:
        assert 'auditor' not in ALLOWED_IMPORTS['scout']
        assert 'scout' not in ALLOWED_IMPORTS['auditor']

    def test_the_api_does_not_import_an_agent(self) -> None:
        assert 'scout' not in ALLOWED_IMPORTS['api']
        assert 'auditor' not in ALLOWED_IMPORTS['api']


class TestDeterministicPurity:
    def test_rights_surface_does_not_import_the_agent_stack(self) -> None:
        audit = ArchitectureAudit(SourceModules(PROJECT_ROOT))
        violations = audit.purity_violations()
        assert not violations, audit.report(violations)

    def test_the_scan_covers_the_rights_surface(self) -> None:
        modules = SourceModules(PROJECT_ROOT)
        scanned = [path for path in modules.files() if modules.is_deterministic(path)]
        assert len(scanned) >= 8
