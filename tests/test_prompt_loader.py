"""Prompt loader tests."""

from bloggen.prompts.loader import PromptError, PromptLoader


def test_prompt_loader_injects_variables(tmp_path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "example.md").write_text("Hello $name", encoding="utf-8")

    assert PromptLoader(prompt_dir).render("example.md", name="Bloggen") == "Hello Bloggen"


def test_prompt_loader_rejects_missing_variables(tmp_path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "example.md").write_text("Hello $name", encoding="utf-8")

    try:
        PromptLoader(prompt_dir).render("example.md")
    except PromptError:
        pass
    else:
        raise AssertionError("Expected missing prompt variable to fail")
