from quality.versioning import get_version_manifest


def test_version_manifest_is_stable_complete_and_secret_free():
    first = get_version_manifest(model="gpt-5.4-mini", engine="openai")
    second = get_version_manifest(model="gpt-5.4-mini", engine="openai")

    assert first == second
    assert first["quality_schema_version"] == "quality-v1"
    assert first["agent_build_version"]
    assert first["prompt_version"].startswith("sha256:")
    assert first["tool_contract_version"].startswith("sha256:")
    assert first["guard_policy_version"].startswith("guard-policy-v1+")
    assert first["model_provider"] == "openai"
    serialized = str(first).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized
