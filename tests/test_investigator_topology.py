import pytest

from investigator import load_model_config


@pytest.mark.parametrize("mode", ["local", "stub", "anthropic"])
@pytest.mark.parametrize("classification", ["", "customer", "synthetic"])
def test_egress_override_requires_synthetic_anthropic(mode, classification):
    env = {
        "INVESTIGATOR_EGRESS": "enabled",
        "LLM_MODE": mode,
        "DATA_CLASSIFICATION": classification,
        "LLM_MODEL": "fixture",
        "LOCAL_LLM_URL": "http://llm:11434",
    }
    if mode == "anthropic" and classification == "synthetic":
        config = load_model_config(env, lambda _: "fixture")
        assert config.llm_mode == "anthropic"
    else:
        with pytest.raises(SystemExit):
            load_model_config(env, lambda _: pytest.fail("unexpected secret read"))


def test_internal_local_mode_accepts_default_classification():
    config = load_model_config({
        "LLM_MODE": "local",
        "LLM_MODEL": "fixture",
        "LOCAL_LLM_URL": "http://llm:11434",
    })
    assert config.data_classification == "customer"
    assert config.local_url == "http://llm:11434"
