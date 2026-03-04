from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetDecision:
    requested_tokens: int
    effective_tokens: int
    warning: bool
    compression_required: bool


class ContextBudgetEnforcer:
    DEFAULT_MAX_CONTEXT_TOKENS = 30_000
    DEFAULT_WARNING_THRESHOLD = 24_000

    def __init__(
        self,
        max_context_tokens: int | None = None,
        warning_threshold: int | None = None,
    ) -> None:
        self.max_context_tokens = max_context_tokens or self.DEFAULT_MAX_CONTEXT_TOKENS
        self.warning_threshold = warning_threshold or self.DEFAULT_WARNING_THRESHOLD
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be > 0")
        if not (0 < self.warning_threshold <= self.max_context_tokens):
            raise ValueError("warning_threshold must be > 0 and <= max_context_tokens")

    def check_budget(self, required_tokens: int) -> BudgetDecision:
        if required_tokens < 0:
            raise ValueError("required_tokens must be >= 0")

        if required_tokens > self.max_context_tokens:
            # v1 behavior: force compression path and reduce loaded context.
            return BudgetDecision(
                requested_tokens=required_tokens,
                effective_tokens=min(3_500, self.max_context_tokens),
                warning=True,
                compression_required=True,
            )

        return BudgetDecision(
            requested_tokens=required_tokens,
            effective_tokens=required_tokens,
            warning=required_tokens > self.warning_threshold,
            compression_required=False,
        )
