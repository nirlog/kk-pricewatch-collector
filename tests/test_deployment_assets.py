from pathlib import Path

WINDOWS_DEPLOYMENT = Path("deploy/windows")


def test_expected_windows_deployment_assets_exist() -> None:
    expected = {
        "Install-CollectorService.ps1",
        "Update-Collector.ps1",
        "Uninstall-CollectorService.ps1",
        "Get-CollectorStatus.ps1",
        "Install-CaddyService.ps1",
        "Uninstall-CaddyService.ps1",
        "templates/collector-service.xml",
        "templates/caddy-service.xml",
    }
    assert all((WINDOWS_DEPLOYMENT / relative).is_file() for relative in expected)


def test_scripts_have_strict_failure_settings() -> None:
    for script in WINDOWS_DEPLOYMENT.glob("*.ps1"):
        text = script.read_text(encoding="utf-8")
        assert "Set-StrictMode -Version Latest" in text
        assert "$ErrorActionPreference = 'Stop'" in text


def test_templates_contain_no_token_value_placeholder_or_public_uvicorn_bind() -> None:
    templates = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (WINDOWS_DEPLOYMENT / "templates").glob("*.xml")
    )
    assert "API_TOKEN_FILE" in templates
    assert "{{API_TOKEN}}" not in templates
    assert "0.0.0.0" not in templates
    assert "--host 127.0.0.1 --port 8000" in templates


def test_no_third_party_executables_are_committed() -> None:
    assert not list(WINDOWS_DEPLOYMENT.rglob("*.exe"))
