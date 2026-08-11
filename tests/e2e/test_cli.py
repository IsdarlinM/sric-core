from collections.abc import Iterator

from typer.main import get_command
from typer.testing import CliRunner

from sric.cli_vnext import _normalize_trailing_help, app

runner = CliRunner()


def command_paths() -> Iterator[list[str]]:
    root = get_command(app)

    def walk(group: object, prefix: list[str]) -> Iterator[list[str]]:
        commands = getattr(group, "commands", None)
        if not isinstance(commands, dict):
            return
        for name, command in sorted(commands.items()):
            path = [*prefix, name]
            yield path
            if isinstance(getattr(command, "commands", None), dict):
                yield from walk(command, path)

    if isinstance(getattr(root, "commands", None), dict):
        yield from walk(root, [])


def test_root_help_variants_use_real_vnext_entrypoint() -> None:
    for args in (["--help"], ["-h"], ["help"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert "doctor" in result.output
        assert "workspace" in result.output
        assert "graph" in result.output
        assert "eval" in result.output
        assert "secret" in result.output


def test_every_registered_command_supports_short_and_long_help() -> None:
    paths = list(command_paths())
    assert paths
    for path in paths:
        for flag in ("--help", "-h"):
            result = runner.invoke(app, [*path, flag])
            assert result.exit_code == 0, f"{path} {flag}: {result.output}"
            assert "Traceback" not in result.output


def test_trailing_help_normalization_works_at_any_depth() -> None:
    for path in command_paths():
        if path == ["help"]:
            continue
        argv = ["sric", *path, "help"]
        normalized = _normalize_trailing_help(argv)
        assert normalized[-1] == "--help"
        assert normalized[:-1] == argv[:-1]


def test_help_command_supports_root_and_top_level_command() -> None:
    root = runner.invoke(app, ["help"])
    assert root.exit_code == 0, root.output

    doctor = runner.invoke(app, ["help", "doctor"])
    assert doctor.exit_code == 0, doctor.output
    assert "Check Python/runtime prerequisites" in doctor.output


def test_invalid_graph_max_depth_is_rejected_by_cli_parser() -> None:
    result = runner.invoke(
        app,
        ["graph", "path", "source", "target", "--workspace", ".", "--max-depth", "0"],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
