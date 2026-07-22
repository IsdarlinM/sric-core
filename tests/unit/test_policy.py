from sric.models import ActionClass, ActionProposal, OperationMode
from sric.policy import PolicyEngine


def proposal(cls: ActionClass, mode: OperationMode = OperationMode.VALIDATE) -> ActionProposal:
    return ActionProposal(
        action_id="A1",
        actor="tester",
        method="POST",
        target="https://example.com",
        action_class=cls,
        mode=mode,
    )


def test_destructive_requires_human_approval() -> None:
    p = PolicyEngine()
    assert not p.decide(proposal(ActionClass.MUTATING_DESTRUCTIVE)).allowed
    assert p.decide(proposal(ActionClass.MUTATING_DESTRUCTIVE), human_approved=True).allowed


def test_prohibited_hard_denied_even_with_approval() -> None:
    assert not PolicyEngine().decide(proposal(ActionClass.PROHIBITED), human_approved=True).allowed
