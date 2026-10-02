"""Compose operations boundaries, tested from the infrastructure release tree."""

from pathlib import Path
import re


def test_compose_operations_boundary_is_private_and_application_services_have_no_admin():
    source = (Path(__file__).resolve().parents[1] / "runtime.compose.yml").read_text()
    # Source guards deliberately require the bounded operations block and anchor;
    # effective Compose parsing is an additional author/reviewer check.
    service = re.search(r"^  migrate:\n(.*?)(?=^\S|^  [a-z])", source, re.M | re.S).group(1)
    assert "    <<: *application\n" in service
    assert "    profiles: [operations]\n" in service
    assert "    restart: 'no'\n" in service
    assert "    command: ['python', '-m', 'app.runtime_migrate']\n" in service
    environment = re.search(r"^    environment:\n(.*?)(?=^    \S)", service, re.M | re.S).group(1)
    assert environment == ("      APP_ENV: production\n"
                           "      DATABASE_URL_FILE: /run/secrets/admin-database-url\n"
                           "      DEMANDRIFT_APPLICATION_DATABASE_FILE: /run/secrets/application-database-url\n"
                           "      DATABASE_APP_ROLE: demandrift_app\n")
    assert "    secrets: [admin-database-url, application-database-url]\n" in service
    assert "    volumes: []\n" in service and "    networks: [data]\n" in service
    assert "ports:" not in service and "entrypoint:" not in service
    anchor = source.split("x-application: &application\n", 1)[1].split("x-environment:", 1)[0]
    assert "  read_only: true\n" in anchor and "  user: '10001:10001'\n" in anchor
    assert "  cap_drop: [ALL]\n" in anchor and "no-new-privileges:true" in anchor
    for name in ("api", "worker"):
        application = re.search(rf"^  {name}:\n(.*?)(?=^\S|^  [a-z])", source, re.M | re.S).group(1)
        assert "admin-database-url" not in application
        assert "<<: *environment" in application or "environment: *environment" in application
        assert "DEMANDRIFT_APPLICATION_DATABASE_FILE" not in application
    shared = source.split("x-environment: &environment\n", 1)[1].split("services:", 1)[0]
    assert "  DATABASE_URL_FILE: /run/secrets/application-database-url\n" in shared
    assert "admin-database-url" not in shared

