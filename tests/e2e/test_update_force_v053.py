from typer.main import get_command
from typer.testing import CliRunner

from sric.cli_all import app


runner = CliRunner()


def test_update_exposes_force_option() -> None:
    root = get_command(app)
    update = root.commands["update"]
    assert any("--force" in getattr(param, "opts", ()) for param in update.params)


def test_check_and_force_are_rejected_as_user_error() -> None:
    result = runner.invoke(app, ["update", "--check", "--force"])
    assert result.exit_code == 2
    assert "--check and --force cannot be used together" in result.output
    assert "Traceback" not in result.output
