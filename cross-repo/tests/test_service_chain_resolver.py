from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.service_chain_resolver import extract_dependencies, resolve_class_kind


SPRING_CONTROLLER = """
@RestController
@RequestMapping("/api/beneficiary")
public class BeneficiaryController {

    private final BeneficiaryService beneficiaryService;
    private final AuditService auditService;

    public BeneficiaryController(BeneficiaryService beneficiaryService, AuditService auditService) {
        this.beneficiaryService = beneficiaryService;
        this.auditService = auditService;
    }
}
"""

SPRING_SERVICE = """
@Service
public class BeneficiaryServiceImpl implements BeneficiaryService {
    private final BeneficiaryRepository beneficiaryRepository;
    private final CacheManager cacheManager;
}
"""

ANGULAR_COMPONENT = """
@Component({
  selector: 'app-registration',
  templateUrl: './registration.component.html',
})
export class RegistrationComponent {
  constructor(
    private beneficiaryService: BeneficiaryService,
    private router: Router,
    private authService: AuthService,
  ) {}
}
"""


def test_spring_controller_kind():
    kind = resolve_class_kind(SPRING_CONTROLLER, 'BeneficiaryController', 'java')
    assert kind == 'controller'


def test_spring_service_kind():
    kind = resolve_class_kind(SPRING_SERVICE, 'BeneficiaryServiceImpl', 'java')
    assert kind == 'service'


def test_angular_component_kind():
    kind = resolve_class_kind(ANGULAR_COMPONENT, 'RegistrationComponent', 'typescript')
    assert kind == 'component'


def test_spring_dependency_extraction():
    deps = extract_dependencies(SPRING_CONTROLLER, 'java')
    assert 'BeneficiaryService' in deps
    assert 'AuditService' in deps


def test_spring_service_deps():
    deps = extract_dependencies(SPRING_SERVICE, 'java')
    assert 'BeneficiaryRepository' in deps


def test_angular_dependency_extraction():
    deps = extract_dependencies(ANGULAR_COMPONENT, 'typescript')
    assert 'BeneficiaryService' in deps
    assert 'AuthService' in deps


def test_unknown_kind():
    kind = resolve_class_kind('public class Foo {}', 'Foo', 'java')
    assert kind == 'unknown'


def test_empty_deps():
    deps = extract_dependencies('', 'java')
    assert deps == []
