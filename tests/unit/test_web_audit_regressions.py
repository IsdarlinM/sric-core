from __future__ import annotations

import typer
from typer.main import get_command

from sric.web_catalog import _classify_catalog_command, _option_metadata
from sric.webui import AnalysisPage, _page_html


def _sample_params() -> dict[str, object]:
    app = typer.Typer()

    @app.command()
    def sample(
        workspace: str = typer.Argument(...),
        cancel: bool = typer.Option(False, "--cancel"),
    ) -> None:
        pass

    root = get_command(app)
    commands = getattr(root, "commands", None)
    command = commands["sample"] if isinstance(commands, dict) else root
    return {str(param.name): param for param in command.params}


def test_typer_arguments_are_not_serialized_as_options() -> None:
    params = _sample_params()
    workspace = _option_metadata(params["workspace"])
    cancel = _option_metadata(params["cancel"])

    assert workspace["kind"] == "argument"
    assert workspace["opts"] == []
    assert cancel["kind"] == "option"
    assert cancel["opts"] == ["--cancel"]


def test_known_state_mutations_fail_closed_to_approval() -> None:
    for path in (
        ("collect-url",),
        ("evidence",),
        ("validate",),
        ("demo",),
        ("notebook",),
        ("jobs",),
        ("workspace",),
    ):
        classification, approval_required, context_only = _classify_catalog_command(path)
        assert classification == "MUTATING_REVERSIBLE"
        assert approval_required is True
        assert context_only is False


def test_analysis_page_is_importable_on_supported_python_and_escapes_bootstrap() -> None:
    page = _page_html(
        AnalysisPage(
            title="Audit",
            description="Regression",
            endpoint="/api/test",
            example_payload={"value": "</script>"},
        ),
        prefix="/audit",
    )
    assert "window.SENTINEL_ANALYSIS=" in page
    assert "</script></script>" not in page
    assert "\\u003c/script>" in page
