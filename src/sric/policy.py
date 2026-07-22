from __future__ import annotations

from .models import ActionClass, ActionProposal, OperationMode, PolicyDecision


class PolicyEngine:
    """Deterministic policy gate. LLM output never bypasses this component."""

    def preflight(self, proposal: ActionProposal) -> PolicyDecision:
        """Evaluate policy without treating human approval as already granted."""
        if proposal.action_class in {ActionClass.OUT_OF_SCOPE, ActionClass.PROHIBITED}:
            return PolicyDecision(
                action_id=proposal.action_id,
                allowed=False,
                decision="deny",
                matched_rule="hard-deny-action-class",
            )
        if (
            proposal.mode == OperationMode.PASSIVE
            and proposal.action_class != ActionClass.READ_ONLY_SAFE
        ):
            return PolicyDecision(
                action_id=proposal.action_id,
                allowed=False,
                decision="deny",
                matched_rule="passive-mode-read-only-safe",
            )
        if proposal.action_class == ActionClass.MUTATING_DESTRUCTIVE:
            return PolicyDecision(
                action_id=proposal.action_id,
                allowed=True,
                decision="conditional",
                matched_rule="destructive-human-approval",
                requires_approval=True,
            )
        if proposal.action_class == ActionClass.MUTATING_REVERSIBLE:
            return PolicyDecision(
                action_id=proposal.action_id,
                allowed=True,
                decision="conditional",
                matched_rule="mutation-human-approval",
                requires_approval=True,
            )
        return PolicyDecision(
            action_id=proposal.action_id,
            allowed=True,
            decision="allow",
            matched_rule="default-safe-policy",
        )

    def decide(self, proposal: ActionProposal, *, human_approved: bool = False) -> PolicyDecision:
        preflight = self.preflight(proposal)
        if not preflight.allowed:
            return preflight
        if preflight.requires_approval and not human_approved:
            return preflight.model_copy(update={"allowed": False, "decision": "deny"})
        if preflight.requires_approval:
            return preflight.model_copy(update={"allowed": True, "decision": "allow"})
        return preflight
