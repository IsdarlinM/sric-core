from typer.testing import CliRunner

from sric import __version__
from sric.cli_all import app


runner = CliRunner()


def test_root_version_flag_matches_package_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == __version__
