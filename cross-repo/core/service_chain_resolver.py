from __future__ import annotations

import re


_SPRING_FIELD = re.compile(
    r'(?:private|protected|public)\s+(?:final\s+)?([A-Z][A-Za-z0-9]+(?:Service|Repository|Repo|Client|Manager|Helper|Dao|Gateway))\s+\w+',
)
_SPRING_AUTOWIRED = re.compile(
    r'@(?:Autowired|Inject)\s+(?:(?:private|protected|public)\s+)?(?:final\s+)?([A-Z][A-Za-z0-9]+)\s+\w+\s*;',
    re.DOTALL,
)
_ANGULAR_CONSTRUCTOR = re.compile(
    r'constructor\s*\(([^)]+)\)',
    re.DOTALL,
)
_ANGULAR_PARAM_TYPE = re.compile(
    r'(?:private|public|protected|readonly)\s+\w+\s*:\s*([A-Z][A-Za-z0-9]+(?:Service|Client|Repository|Store|Facade|Http))',
)
_CLASS_LAYER = {
    'controller': re.compile(r'@(?:RestController|Controller)\b|Controller\s*\{', re.IGNORECASE),
    'service': re.compile(r'@Service\b|@Injectable\b', re.IGNORECASE),
    'repository': re.compile(r'@Repository\b|extends\s+(?:Jpa|Crud)Repository', re.IGNORECASE),
    'component': re.compile(r'@Component\s*\(\s*\{', re.IGNORECASE),
}


def resolve_class_kind(text: str, class_name: str, language: str) -> str:
    """Determine the architectural layer of a class: controller, service, repository, component, unknown."""
    snippet = text[:4000]
    if language == 'java':
        for kind, pattern in _CLASS_LAYER.items():
            if pattern.search(snippet):
                return kind
        name_lower = class_name.lower()
        for kind in ('controller', 'service', 'repository'):
            if kind in name_lower:
                return kind
    elif language in ('typescript', 'javascript'):
        if _CLASS_LAYER['component'].search(snippet):
            return 'component'
        if _CLASS_LAYER['service'].search(snippet):
            return 'service'
        if 'component' in class_name.lower():
            return 'component'
        if 'service' in class_name.lower():
            return 'service'
    return 'unknown'


def extract_dependencies(text: str, language: str) -> list[str]:
    """
    Extract injected service/class dependency names from source code.

    Returns a list of class names that appear to be injected as dependencies.
    """
    deps: list[str] = []

    if language == 'java':
        deps.extend(_SPRING_FIELD.findall(text))
        deps.extend(_SPRING_AUTOWIRED.findall(text))

    elif language in ('typescript', 'javascript'):
        for constructor_match in _ANGULAR_CONSTRUCTOR.finditer(text):
            param_block = constructor_match.group(1)
            deps.extend(_ANGULAR_PARAM_TYPE.findall(param_block))

    # Deduplicate preserving order
    seen: set[str] = set()
    result = []
    for dep in deps:
        if dep not in seen:
            seen.add(dep)
            result.append(dep)
    return result
