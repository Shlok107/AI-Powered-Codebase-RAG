import re
import yaml
from pathlib import Path
from typing import Optional

from app.services.security_rules import SecurityRule, Finding, registry


class DockerRootUserRule(SecurityRule):
    """Detect Docker containers running as root."""

    @property
    def rule_id(self) -> str:
        return "DOCKER_ROOT_USER"

    @property
    def title(self) -> str:
        return "Container Running as Root"

    @property
    def category(self) -> str:
        return "infrastructure"

    @property
    def severity(self) -> str:
        return "medium"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        filename = Path(file_path).name.lower()

        if filename not in ('dockerfile', 'dockerfile.prod', 'dockerfile.dev') and not filename.startswith('dockerfile'):
            return findings

        lines = content.splitlines()
        has_user = False

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            # Check for USER instruction
            if re.match(r'(?i)^USER\s+', stripped):
                user = stripped.split()[1] if len(stripped.split()) > 1 else ''
                if user == 'root' or user == '0':
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="Container explicitly runs as root user. This violates the principle of least privilege.",
                        remediation="Create a non-root user in the Dockerfile and switch to it: RUN useradd -m appuser && USER appuser",
                        references=[
                            "https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user",
                        ],
                    ))
                has_user = True

        # If no USER instruction found, container runs as root by default
        if not has_user:
            # Check if there's a USER in the base image (hard to detect statically)
            # Flag as info
            findings.append(self._create_finding(
                file_path=file_path,
                start_line=1,
                end_line=1,
                evidence="Dockerfile has no USER instruction",
                explanation="No USER instruction found. Container will run as root by default.",
                remediation="Add a non-root user and USER instruction to the Dockerfile.",
                references=[
                    "https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user",
                ],
            ))

        return findings


class DockerFloatingTagRule(SecurityRule):
    """Detect floating base image tags."""

    @property
    def rule_id(self) -> str:
        return "DOCKER_FLOATING_TAG"

    @property
    def title(self) -> str:
        return "Floating Base Image Tag"

    @property
    def category(self) -> str:
        return "infrastructure"

    @property
    def severity(self) -> str:
        return "low"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        filename = Path(file_path).name.lower()

        if filename not in ('dockerfile', 'dockerfile.prod', 'dockerfile.dev') and not filename.startswith('dockerfile'):
            return findings

        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            # Check FROM instruction with floating tag
            match = re.match(r'(?i)^FROM\s+([^\s:]+)(?::([^\s]+))?', stripped)
            if match:
                image = match.group(1)
                tag = match.group(2)

                if not tag or tag in ('latest', 'stable', 'main', 'master', 'edge'):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation=f"Base image '{image}' uses floating tag '{tag or 'latest'}'. This makes builds non-reproducible and can introduce unexpected changes.",
                        remediation="Pin to a specific version tag or digest: FROM python:3.11.9-slim or FROM python@sha256:...",
                        references=[
                            "https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#from",
                        ],
                    ))

        return findings


class DockerSecretInBuildRule(SecurityRule):
    """Detect secrets in Docker build args or ENV."""

    @property
    def rule_id(self) -> str:
        return "DOCKER_SECRET_IN_BUILD"

    @property
    def title(self) -> str:
        return "Secret in Docker Build Argument or ENV"

    @property
    def category(self) -> str:
        return "configuration"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "medium"

    SECRET_PATTERNS = [
        (r'(?i)(password|secret|token|api[_-]?key|access[_-]?key)', "Potential Secret"),
    ]

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        filename = Path(file_path).name.lower()

        if filename not in ('dockerfile', 'dockerfile.prod', 'dockerfile.dev') and not filename.startswith('dockerfile'):
            return findings

        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            # Check ARG and ENV for secrets
            if re.match(r'(?i)^(ARG|ENV)\s+', stripped):
                for pattern, secret_type in self.SECRET_PATTERNS:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        # Check if it's a default value
                        if '=' in stripped:
                            findings.append(self._create_finding(
                                file_path=file_path,
                                start_line=line_num,
                                end_line=line_num,
                                evidence=line.strip()[:200],
                                explanation=f"Docker {secret_type} found in {stripped.split()[0]} instruction. Build args and ENV vars are visible in image history.",
                                remediation="Use Docker BuildKit secrets (--secret) or runtime environment variables instead of baking secrets into the image.",
                                references=[
                                    "https://docs.docker.com/build/building/secrets/",
                                ],
                            ))

        return findings


class K8sPrivilegedContainerRule(SecurityRule):
    """Detect privileged containers in Kubernetes."""

    @property
    def rule_id(self) -> str:
        return "K8S_PRIVILEGED_CONTAINER"

    @property
    def title(self) -> str:
        return "Privileged Container"

    @property
    def category(self) -> str:
        return "infrastructure"

    @property
    def severity(self) -> str:
        return "high"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        filename = Path(file_path).name.lower()

        if not (filename.endswith('.yaml') or filename.endswith('.yml')):
            return findings

        # Check if it's a Kubernetes manifest
        if not self._is_k8s_manifest(content):
            return findings

        try:
            docs = list(yaml.safe_load_all(content))
        except Exception:
            return findings

        for doc in docs:
            if not doc or doc.get('kind') not in ('Pod', 'Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob'):
                continue

            # Find containers
            containers = self._extract_containers(doc)
            for container in containers:
                self._check_container_privileged(file_path, container, findings)

        return findings

    def _is_k8s_manifest(self, content: str) -> bool:
        return 'apiVersion:' in content and 'kind:' in content

    def _extract_containers(self, doc: dict) -> list[dict]:
        containers = []
        spec = doc.get('spec', {})

        # Direct pods
        if 'containers' in spec:
            containers.extend(spec['containers'])
        if 'initContainers' in spec:
            containers.extend(spec['initContainers'])

        # Deployments, etc. have template.spec
        if 'template' in spec and isinstance(spec['template'], dict):
            template_spec = spec['template'].get('spec', {})
            if 'containers' in template_spec:
                containers.extend(template_spec['containers'])
            if 'initContainers' in template_spec:
                containers.extend(template_spec['initContainers'])

        return containers

    def _check_container_privileged(self, file_path: str, container: dict, findings: list):
        name = container.get('name', 'unknown')
        security_context = container.get('securityContext', {})

        if security_context.get('privileged') is True:
            findings.append(self._create_finding(
                file_path=file_path,
                start_line=1,
                end_line=1,
                evidence=f"Container '{name}' has privileged: true",
                explanation=f"Container '{name}' runs in privileged mode, giving it full access to the host system.",
                remediation="Remove privileged: true. Use specific capabilities if needed: securityContext.capabilities.add: [\"CAP_NET_BIND_SERVICE\"]",
                references=[
                    "https://kubernetes.io/docs/concepts/security/pod-security-standards/",
                ],
            ))

        # Check for host namespace access
        for ns in ['hostNetwork', 'hostPID', 'hostIPC']:
            if container.get(ns) is True:
                findings.append(self._create_finding(
                    file_path=file_path,
                    start_line=1,
                    end_line=1,
                    evidence=f"Container '{name}' has {ns}: true",
                    explanation=f"Container '{name}' shares host {ns.lower()}, reducing isolation.",
                    remediation=f"Remove {ns}: true unless absolutely necessary.",
                ))


class K8sMissingResourcesRule(SecurityRule):
    """Detect missing resource limits in Kubernetes."""

    @property
    def rule_id(self) -> str:
        return "K8S_MISSING_RESOURCES"

    @property
    def title(self) -> str:
        return "Missing Resource Limits"

    @property
    def category(self) -> str:
        return "configuration"

    @property
    def severity(self) -> str:
        return "medium"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        filename = Path(file_path).name.lower()

        if not (filename.endswith('.yaml') or filename.endswith('.yml')):
            return findings

        if not self._is_k8s_manifest(content):
            return findings

        try:
            docs = list(yaml.safe_load_all(content))
        except Exception:
            return findings

        for doc in docs:
            if not doc or doc.get('kind') not in ('Pod', 'Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob'):
                continue

            containers = self._extract_containers(doc)
            for container in containers:
                self._check_resources(file_path, container, findings)

        return findings

    def _is_k8s_manifest(self, content: str) -> bool:
        return 'apiVersion:' in content and 'kind:' in content

    def _extract_containers(self, doc: dict) -> list[dict]:
        containers = []
        spec = doc.get('spec', {})
        if 'containers' in spec:
            containers.extend(spec['containers'])
        if 'template' in spec and isinstance(spec['template'], dict):
            template_spec = spec['template'].get('spec', {})
            if 'containers' in template_spec:
                containers.extend(template_spec['containers'])
        return containers

    def _check_resources(self, file_path: str, container: dict, findings: list):
        name = container.get('name', 'unknown')
        resources = container.get('resources', {})

        if not resources.get('limits') and not resources.get('requests'):
            findings.append(self._create_finding(
                file_path=file_path,
                start_line=1,
                end_line=1,
                evidence=f"Container '{name}' has no resource limits or requests",
                explanation=f"Container '{name}' has no CPU/memory limits or requests. This can cause resource exhaustion and noisy neighbor problems.",
                remediation="Add resource limits and requests: resources: {limits: {cpu: '500m', memory: '512Mi'}, requests: {cpu: '250m', memory: '256Mi'}}",
                references=[
                    "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/",
                ],
            ))


class DebugModeRule(SecurityRule):
    """Detect debug mode enabled in config files."""

    @property
    def rule_id(self) -> str:
        return "CONFIG_DEBUG_MODE"

    @property
    def title(self) -> str:
        return "Debug Mode Enabled"

    @property
    def category(self) -> str:
        return "configuration"

    @property
    def severity(self) -> str:
        return "medium"

    @property
    def confidence(self) -> str:
        return "high"

    def check(self, file_path: str, content: str, language: str) -> list[Finding]:
        findings = []
        lines = content.splitlines()

        debug_patterns = {
            "python": [
                r'(?i)DEBUG\s*=\s*True',
                r'(?i)app\.debug\s*=\s*True',
                r'(?i)FLASK_DEBUG\s*=\s*1',
            ],
            "javascript": [
                r'(?i)debug\s*:\s*true',
                r'(?i)NODE_ENV\s*=\s*["\']development["\']',
            ],
            "yaml": [
                r'(?i)debug\s*:\s*true',
            ],
        }

        patterns = debug_patterns.get(language, [])
        if filename := Path(file_path).name.lower():
            if filename in ('config.yaml', 'config.yml', 'settings.yaml', 'settings.yml'):
                patterns.extend(debug_patterns.get("yaml", []))

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            for pattern in patterns:
                if re.search(pattern, stripped) and not self._is_comment(stripped, language):
                    findings.append(self._create_finding(
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence=line.strip()[:200],
                        explanation="Debug mode is enabled in configuration. This can expose sensitive information and reduce performance.",
                        remediation="Disable debug mode in production: DEBUG=False, NODE_ENV=production",
                        references=[
                            "https://cwe.mitre.org/data/definitions/489.html",
                        ],
                    ))

        return findings

    def _is_comment(self, line: str, language: str) -> bool:
        stripped = line.strip()
        if language == "python":
            return stripped.startswith("#")
        elif language in ("javascript", "typescript", "java", "c", "cpp", "go"):
            return stripped.startswith("//") or stripped.startswith("/*")
        elif language == "yaml":
            return stripped.startswith("#")
        return False


# Register infrastructure/config rules
registry.register(DockerRootUserRule())
registry.register(DockerFloatingTagRule())
registry.register(DockerSecretInBuildRule())
registry.register(K8sPrivilegedContainerRule())
registry.register(K8sMissingResourcesRule())
registry.register(DebugModeRule())