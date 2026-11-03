import pytest
import httpx

from app.services.security_rules import get_registry
from app.services.security_rules_dependencies import DependencyVulnerabilityRule, OsvAdvisoryClient, parse_dependency_manifest


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("rule_id", "path", "source", "language", "severity", "line"),
    [
        ("SECRET_HARDCODED", "src/config.py", 'api_key = "abcdef0123456789abcdef"', "python", "critical", 1),
        ("SECRET_PASSWORD", "settings.py", 'password = "S3cure-Value"', "python", "high", 1),
        ("DANGEROUS_EVAL_EXEC", "src/eval.py", "value = eval(user_input)", "python", "high", 1),
        ("DANGEROUS_PICKLE", "src/deserialize.py", "value = pickle.loads(payload)", "python", "critical", 1),
        (
            "DANGEROUS_SUBPROCESS_SHELL",
            "src/command.py",
            "subprocess.run(command, shell=True)",
            "python",
            "high",
            1,
        ),
        (
            "DANGEROUS_SQL_INJECTION",
            "src/query.py",
            'cursor.execute("SELECT * FROM users WHERE name = %s" % user_name)',
            "python",
            "high",
            1,
        ),
        ("DANGEROUS_PATH_TRAVERSAL", "src/files.py", 'open("../" + name)', "python", "high", 1),
        ("DANGEROUS_WEAK_CRYPTO", "src/hash.py", "hashlib.md5(payload).hexdigest()", "python", "medium", 1),
        ("DOCKER_ROOT_USER", "Dockerfile", "USER root", "dockerfile", "medium", 1),
        ("DOCKER_FLOATING_TAG", "Dockerfile", "FROM python:latest", "dockerfile", "low", 1),
        ("DOCKER_SECRET_IN_BUILD", "Dockerfile", "ARG API_KEY=abcdef0123456789", "dockerfile", "high", 1),
        (
            "K8S_PRIVILEGED_CONTAINER",
            "deployment.yaml",
            "apiVersion: v1\nkind: Pod\nspec:\n  containers:\n    - name: app\n      image: app:1\n      securityContext:\n        privileged: true\n",
            "yaml",
            "high",
            1,
        ),
        (
            "K8S_MISSING_RESOURCES",
            "deployment.yaml",
            "apiVersion: v1\nkind: Pod\nspec:\n  containers:\n    - name: app\n      image: app:1\n",
            "yaml",
            "medium",
            1,
        ),
        ("CONFIG_DEBUG_MODE", "settings.py", "DEBUG = True", "python", "medium", 1),
    ],
)
def test_each_existing_security_rule_reports_expected_location_and_severity(
    rule_id: str,
    path: str,
    source: str,
    language: str,
    severity: str,
    line: int,
) -> None:
    rules = {rule.rule_id: rule for rule in get_registry().get_all()}
    rule = rules[rule_id]

    findings = rule.check(path, source, language)

    assert findings, f"{rule_id} did not detect its representative unsafe source"
    assert findings[0].rule_id == rule_id
    assert findings[0].severity == severity
    assert findings[0].file_path == path
    assert findings[0].start_line == line
    assert findings[0].end_line >= line
    assert findings[0].remediation


def test_every_registered_rule_is_accounted_for_by_the_test_matrix() -> None:
    expected = {
        "SECRET_HARDCODED",
        "SECRET_PASSWORD",
        "DANGEROUS_EVAL_EXEC",
        "DANGEROUS_PICKLE",
        "DANGEROUS_SUBPROCESS_SHELL",
        "DANGEROUS_SQL_INJECTION",
        "DANGEROUS_PATH_TRAVERSAL",
        "DANGEROUS_WEAK_CRYPTO",
        "DEP_VULNERABLE",
        "DEP_OUTDATED",
        "DOCKER_ROOT_USER",
        "DOCKER_FLOATING_TAG",
        "DOCKER_SECRET_IN_BUILD",
        "K8S_PRIVILEGED_CONTAINER",
        "K8S_MISSING_RESOURCES",
        "CONFIG_DEBUG_MODE",
    }

    assert {rule.rule_id for rule in get_registry().get_all()} == expected


def test_security_rules_redact_secrets_from_evidence() -> None:
    rule = get_registry().get_by_id("SECRET_HARDCODED")
    assert rule is not None

    findings = rule.check("src/config.py", 'api_key = "abcdef0123456789abcdef"', "python")

    assert len(findings) == 1
    assert "abcdef0123456789abcdef" not in findings[0].evidence
    assert "REDACTED" in findings[0].evidence


@pytest.mark.parametrize(
    ("rule_id", "path", "source", "language"),
    [
        ("SECRET_HARDCODED", "tests/test_config.py", 'api_key = "your_key_abcdef0123456789"', "python"),
        ("SECRET_PASSWORD", "settings.py", 'password = "changeme"', "python"),
        ("DANGEROUS_EVAL_EXEC", "src/app.py", "# eval(user_input) is discussed here", "python"),
        ("DEP_VULNERABLE", "requirements.txt", "django==4.2.10", "text"),
        ("DEP_OUTDATED", "requirements.txt", "requests==2.32.0", "text"),
        ("DOCKER_ROOT_USER", "Dockerfile", "USER app", "dockerfile"),
        ("DOCKER_FLOATING_TAG", "Dockerfile", "FROM python:3.11.9-slim", "dockerfile"),
        ("CONFIG_DEBUG_MODE", "settings.py", "# DEBUG = True", "python"),
    ],
)
def test_representative_safe_or_placeholder_cases_do_not_raise_findings(rule_id, path, source, language) -> None:
    rule = get_registry().get_by_id(rule_id)
    assert rule is not None

    assert rule.check(path, source, language) == []


def test_outdated_dependency_rule_does_not_guess_version_currentness() -> None:
    rule = get_registry().get_by_id("DEP_OUTDATED")
    assert rule is not None

    assert rule.check("package.json", '{"name":"service","dependencies":{"requests":"1.0.0"}}', "json") == []


def test_dependency_manifest_parser_only_queries_exact_resolved_versions() -> None:
    dependencies, incomplete = parse_dependency_manifest(
        "requirements.txt",
        "# comment\nDjango==2.2.0\nrequests>=2.0\n-e git+https://example.test/pkg.git\n",
    )

    assert incomplete is False
    assert [(dep.ecosystem, dep.name, dep.version, dep.line) for dep in dependencies] == [
        ("PyPI", "Django", "2.2.0", 2),
    ]


@pytest.mark.asyncio
async def test_dependency_rule_uses_osv_advisory_and_reports_exact_location() -> None:
    async def osv_response(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.url.path == "/v1/querybatch"
            assert request.content
            return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-test-1234"}]}]})
        assert request.url.path == "/v1/vulns/GHSA-test-1234"
        return httpx.Response(
            200,
            json={
                "id": "GHSA-test-1234",
                "summary": "An affected release has a security issue.",
                "database_specific": {"severity": "CRITICAL"},
                "references": [{"url": "https://github.com/advisories/GHSA-test-1234"}],
            },
        )

    client = OsvAdvisoryClient(
        endpoint="https://osv.test/v1/querybatch",
        transport=httpx.MockTransport(osv_response),
    )
    rule = DependencyVulnerabilityRule(client)
    findings, incomplete, truncated = await rule.check_with_status(
        "requirements.txt", "# pinned dependency\nDjango==2.2.0\n"
    )

    assert incomplete is False
    assert truncated is False
    assert len(findings) == 1
    assert findings[0].rule_id == "DEP_VULNERABLE"
    assert findings[0].severity == "critical"
    assert findings[0].start_line == findings[0].end_line == 2
    assert findings[0].evidence == "Django==2.2.0"
    assert findings[0].references == ["https://github.com/advisories/GHSA-test-1234"]


@pytest.mark.asyncio
async def test_dependency_rule_handles_advisory_service_outage_without_failing_scan() -> None:
    async def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unavailable", request=request)

    client = OsvAdvisoryClient(
        endpoint="https://osv.test/v1/querybatch",
        transport=httpx.MockTransport(unavailable),
    )
    rule = DependencyVulnerabilityRule(client)
    findings, incomplete, truncated = await rule.check_with_status("requirements.txt", "requests==2.31.0\n")

    assert findings == []
    assert incomplete is True
    assert truncated is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "batch_result",
    [None, {"vulns": [{"id": 3}]}],
)
async def test_dependency_rule_marks_malformed_advisory_responses_incomplete(batch_result) -> None:
    async def malformed_response(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [batch_result]})

    client = OsvAdvisoryClient(
        endpoint="https://osv.test/v1/querybatch",
        transport=httpx.MockTransport(malformed_response),
    )
    findings, incomplete, truncated = await DependencyVulnerabilityRule(client).check_with_status(
        "requirements.txt", "requests==2.31.0\n"
    )

    assert findings == []
    assert incomplete is True
    assert truncated is False


@pytest.mark.asyncio
async def test_dependency_rule_rejects_mismatched_advisory_detail() -> None:
    async def mismatched_detail(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-expected"}]}]})
        return httpx.Response(200, json={"id": "GHSA-other", "summary": "wrong record"})

    client = OsvAdvisoryClient(
        endpoint="https://osv.test/v1/querybatch",
        transport=httpx.MockTransport(mismatched_detail),
    )
    findings, incomplete, truncated = await DependencyVulnerabilityRule(client).check_with_status(
        "requirements.txt", "requests==2.31.0\n"
    )

    assert findings == []
    assert incomplete is True
    assert truncated is False
