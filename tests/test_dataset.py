from periop_core.dataset import load_requirements
from periop_core.enums import RequirementClass
from periop_core.source_authority import load_source_authority_matrix


def test_loads_all_343_atomic_concepts():
    requirements = load_requirements()
    assert len(requirements) == 343


def test_known_universal_mandatory_concept():
    requirements = load_requirements()
    assert requirements["CTX-001"].requiredness == RequirementClass.M0
    assert requirements["CTX-001"].activation_rule == "All patients"


def test_source_authority_matrix_loads_and_flags_allergy_as_no_auto_resolution():
    matrix = load_source_authority_matrix()
    assert "Allergy label" in matrix
    assert matrix["Allergy label"].allows_auto_resolution is False
