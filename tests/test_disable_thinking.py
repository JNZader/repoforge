"""Optional --no-thinking sends enable_thinking=false and stays off by default."""

from click.testing import CliRunner

from repoforge.cli import main
from repoforge.llm import build_llm


def test_build_llm_leaves_thinking_alone_by_default():
    llm = build_llm(model="nvidia_nim/nvidia/nemotron-3.5-lightning-30b-a3b", api_key="k")

    assert "extra_body" not in llm.extra_kwargs


def test_build_llm_disables_thinking_when_asked():
    llm = build_llm(
        model="nvidia_nim/nvidia/nemotron-3.5-lightning-30b-a3b",
        api_key="k",
        disable_thinking=True,
    )

    assert llm.extra_kwargs["extra_body"]["chat_template_kwargs"] == {
        "enable_thinking": False,
    }


def test_disable_thinking_keeps_the_gateway_project_header():
    llm = build_llm(
        model="gateway/some-model",
        api_key="k",
        disable_thinking=True,
    )

    assert llm.extra_kwargs["extra_headers"] == {"X-Project": "repoforge"}
    assert llm.extra_kwargs["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_no_thinking_flag_is_on_skills_help():
    result = CliRunner().invoke(main, ["skills", "--help"])

    assert result.exit_code == 0
    assert "--no-thinking" in result.output
