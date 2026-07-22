from typer.testing import CliRunner
from sric.cli import app

runner = CliRunner()


def test_root_help_variants() -> None:
    for args in (["--help"], ["-h"], ["help"]):
        r = runner.invoke(app, args)
        assert r.exit_code == 0, r.output
        assert "doctor" in r.output and "workspace" in r.output


def test_subcommand_help() -> None:
    for args in (["doctor", "--help"], ["doctor", "-h"]):
        r = runner.invoke(app, args)
        assert r.exit_code == 0, r.output
