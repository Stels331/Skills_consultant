from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Callable


@dataclass(frozen=True)
class WorkspaceRuntimeContext:
    organization_id: str
    workspace_id: str
    session_id: str | None
    user_id: str | None
    workspace_version_id: str
    graph_version: str

    @property
    def namespace_key(self) -> str:
        return f"{self.organization_id}:{self.workspace_id}"

    def cache_key(self, kind: str, identifier: str = "default") -> str:
        return f"{self.namespace_key}:{kind}:{identifier}"


@dataclass(frozen=True)
class RuntimeBindResult:
    reset_applied: bool
    previous_namespace: str | None
    active_namespace: str
    cleared_buffers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IsolationFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class WorkspaceIsolationResult:
    status: str
    reason_codes: list[str]
    findings: list[IsolationFinding]

    def as_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "findings": [asdict(item) for item in self.findings],
        }


def _entity_workspace(entity: Any) -> str | None:
    if isinstance(entity, dict):
        for key in ("workspace_id", "workspace_ref"):
            value = entity.get(key)
            if value:
                return str(value)
        for key in ("chunk_id", "fragment_ref", "lineage_ref", "ref"):
            value = entity.get(key)
            if isinstance(value, str) and ":" in value:
                return value.split(":", 1)[0]
    return None


class WorkspaceRuntimeState:
    def __init__(self) -> None:
        self._active_context: WorkspaceRuntimeContext | None = None
        self._prompt_cache: dict[str, Any] = {}
        self._retrieval_cache: dict[str, Any] = {}
        self._version_state_cache: dict[str, Any] = {}
        self._ui_drafts: dict[str, str] = {}

    def reset(self) -> None:
        self._active_context = None
        self._prompt_cache.clear()
        self._retrieval_cache.clear()
        self._version_state_cache.clear()
        self._ui_drafts.clear()

    def bind(self, context: WorkspaceRuntimeContext) -> RuntimeBindResult:
        previous_namespace = self._active_context.namespace_key if self._active_context else None
        reset_applied = previous_namespace is not None and previous_namespace != context.namespace_key
        cleared_buffers: list[str] = []
        if reset_applied:
            self._prompt_cache.clear()
            self._retrieval_cache.clear()
            self._version_state_cache.clear()
            self._ui_drafts.clear()
            cleared_buffers = ["prompt_cache", "retrieval_cache", "version_state_cache", "ui_drafts"]
        self._active_context = context
        return RuntimeBindResult(
            reset_applied=reset_applied,
            previous_namespace=previous_namespace,
            active_namespace=context.namespace_key,
            cleared_buffers=cleared_buffers,
        )

    def remember_prompt(self, context: WorkspaceRuntimeContext, prompt: str) -> str:
        key = context.cache_key("prompt")
        self._prompt_cache[key] = prompt
        return key

    def remember_retrieval(self, context: WorkspaceRuntimeContext, payload: Any, identifier: str = "latest") -> str:
        key = context.cache_key("retrieval", identifier)
        self._retrieval_cache[key] = payload
        return key

    def remember_version_state(self, context: WorkspaceRuntimeContext, payload: Any) -> str:
        key = context.cache_key("version_state")
        self._version_state_cache[key] = payload
        return key

    def save_draft(self, context: WorkspaceRuntimeContext, draft: str) -> str:
        key = context.cache_key("draft")
        self._ui_drafts[key] = draft
        return key

    def get_draft(self, context: WorkspaceRuntimeContext) -> str | None:
        return self._ui_drafts.get(context.cache_key("draft"))


class WorkspaceIsolationValidator:
    def __init__(self) -> None:
        self._entity_validators: dict[str, Callable[[WorkspaceRuntimeContext, list[Any]], list[IsolationFinding]]] = {}
        self.register_entity_validator("used_claims", self._validate_workspace_entities)
        self.register_entity_validator("used_artifacts", self._validate_workspace_entities)
        self.register_entity_validator("prompt_fragments", self._validate_workspace_entities)
        self.register_entity_validator("lineage_refs", self._validate_workspace_entities)

    def register_entity_validator(
        self,
        entity_name: str,
        validator: Callable[[WorkspaceRuntimeContext, list[Any]], list[IsolationFinding]],
    ) -> None:
        self._entity_validators[entity_name] = validator

    def validate(
        self,
        *,
        context: WorkspaceRuntimeContext,
        answer_payload: dict[str, Any],
        prompt_text: str,
    ) -> WorkspaceIsolationResult:
        findings: list[IsolationFinding] = []
        findings.extend(self._validate_prompt_text(context, prompt_text))
        for entity_name, validator in self._entity_validators.items():
            entities = list(answer_payload.get(entity_name) or [])
            findings.extend(validator(context, entities))
        if findings:
            return WorkspaceIsolationResult(
                status="block",
                reason_codes=[item.code for item in findings],
                findings=findings,
            )
        return WorkspaceIsolationResult(status="pass", reason_codes=[], findings=[])

    def _validate_workspace_entities(
        self,
        context: WorkspaceRuntimeContext,
        entities: list[Any],
    ) -> list[IsolationFinding]:
        findings: list[IsolationFinding] = []
        for entity in entities:
            workspace_id = _entity_workspace(entity)
            if workspace_id and workspace_id != context.workspace_id:
                findings.append(
                    IsolationFinding(
                        code="OUT_OF_WORKSPACE_REFERENCE",
                        severity="block",
                        message=f"Entity from workspace {workspace_id} leaked into active workspace {context.workspace_id}",
                    )
                )
        return findings

    def _validate_prompt_text(
        self,
        context: WorkspaceRuntimeContext,
        prompt_text: str,
    ) -> list[IsolationFinding]:
        findings: list[IsolationFinding] = []
        workspace_refs = re.findall(r"workspace_id=([^\n]+)", prompt_text)
        if not workspace_refs:
            findings.append(
                IsolationFinding(
                    code="MISSING_WORKSPACE_CONTEXT",
                    severity="block",
                    message="Prompt does not declare active workspace context",
                )
            )
        for ref in workspace_refs:
            if ref.strip() != context.workspace_id:
                findings.append(
                    IsolationFinding(
                        code="PROMPT_WORKSPACE_LEAK",
                        severity="block",
                        message=f"Prompt references foreign workspace {ref.strip()}",
                    )
                )
        return findings
