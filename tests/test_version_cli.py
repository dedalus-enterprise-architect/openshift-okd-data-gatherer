import subprocess
import sys
from pathlib import Path


def test_cli_version_matches_module():
    # Invoke the CLI via python module to avoid needing installation
    result = subprocess.run([sys.executable, "-m", "data_gatherer.run", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    output = result.stdout.strip()
    # Output format: data-gatherer, version X.Y.Z
    assert "data-gatherer" in output
    import data_gatherer
    from data_gatherer._version import __version__
    assert __version__ in output
    # Ensure __version__ surfaces at package root
    assert data_gatherer.__version__ == __version__
