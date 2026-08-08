import click
from typer.main import get_command
from typer.testing import CliRunner

from sric.cli_all import app


def _paths(command: click.Command, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            path = (*prefix, name)
            output.append(path)
            output.extend(_paths(child, path))
    return output


def test_unknown_options_fail_closed_without_tracebacks() -> None:
    runner = CliRunner()
    for path in [(), *_paths(get_command(app))]:
        result = runner.invoke(app, [*path, "--sentinel-invalid-option"])
        assert result.exit_code != 0, path
        assert "Traceback" not in result.output, f"{' '.join(path)}: {result.output}"
