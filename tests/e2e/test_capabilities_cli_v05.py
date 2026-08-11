from typer.testing import CliRunner

from sric.cli_all import app, normalize_help_argv


runner = CliRunner()


def test_capabilities_cli_and_help_variants() -> None:
    for args in (["capabilities", "--help"], ["capabilities", "-h"], ["capabilities", "help"]):
        argv = normalize_help_argv(["sric", *args])[1:]
        result = runner.invoke(app, argv)
        assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    assert '"core_distribution": "sric-core"' in result.output
