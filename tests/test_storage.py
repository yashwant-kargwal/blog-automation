"""Non-destructive project storage tests."""

from bloggen.storage.exceptions import ArtifactExistsError
from bloggen.storage.project import ProjectStore


def test_project_store_creates_timestamped_isolated_artifacts(tmp_path) -> None:
    project = ProjectStore.create(tmp_path, "My Article")
    project.save_json("research", "research.json", {"facts": []})
    project.save_markdown("article.md", "# Article")
    project.save_html("article.html", "# Article", title="Article")
    project.finalize()

    assert project.path is not None
    assert project.path.name.endswith("-my-article")
    assert (project.path / "metadata" / "project.json").is_file()


def test_project_store_refuses_overwrite(tmp_path) -> None:
    project = ProjectStore.create(tmp_path, "Article")
    project.save_json("research", "research.json", {})

    try:
        project.save_json("research", "research.json", {})
    except ArtifactExistsError:
        pass
    else:
        raise AssertionError("Expected artifact overwrite to fail")
