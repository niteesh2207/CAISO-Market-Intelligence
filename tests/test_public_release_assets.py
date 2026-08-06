from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATE = "August 6, 2026"
PUBLIC_VERSION = "V4.0.0"


class DocumentAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.local_assets: set[str] = set()
        self.title_depth = 0
        self.title = ""

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if tag in {"link", "script", "img"}:
            reference = values.get("href") or values.get("src")
            if reference and not reference.startswith(("http://", "https://", "/")):
                self.local_assets.add(reference.removeprefix("./"))
        if tag == "title":
            self.title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title += data


def parse_document(path: Path) -> tuple[str, DocumentAudit]:
    content = path.read_text(encoding="utf-8")
    parser = DocumentAudit()
    parser.feed(content)
    parser.close()
    return content, parser


def test_pages_preview_has_current_public_contract() -> None:
    content, document = parse_document(ROOT / "index.html")

    assert PUBLIC_VERSION in document.title
    assert PUBLIC_VERSION in content
    assert PUBLIC_DATE in content
    assert "Public engineering alpha" in content
    assert "Not a live trading forecast" in content
    assert "No licensed premium datasets are bundled" in content
    assert "Premium means entitled—not scraped" in content
    assert "production-ready" not in content.lower()
    assert "live forecasts" not in content.lower()

    for asset in document.local_assets:
        assert (ROOT / asset).is_file(), asset


def test_application_ui_has_current_public_contract() -> None:
    content, document = parse_document(ROOT / "static" / "index.html")

    assert PUBLIC_VERSION in document.title
    assert PUBLIC_VERSION in content
    assert PUBLIC_DATE in content
    assert "Public engineering alpha" in content
    assert "not live trading" in content.lower()
    assert "Implemented coverage" in content


def test_pages_workflow_is_curated_and_supply_chain_pinned() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "path: _site" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "cp index.html _site/index.html" in workflow
    assert "uses: actions/configure-pages@45bfe019" in workflow
    assert "uses: actions/upload-pages-artifact@fc324d35" in workflow
    assert "uses: actions/deploy-pages@cd2ce8fc" in workflow


def test_codeql_workflow_is_pinned_and_least_privileged() -> None:
    workflow = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(
        encoding="utf-8"
    )

    assert "security-events: write" in workflow
    assert workflow.count("github/codeql-action/") == 2
    assert workflow.count("@5595ccaf912efad79be6eef63a5619ff05969be3") == 2


def test_social_preview_meets_github_size_limit() -> None:
    image = ROOT / "assets" / "social-preview.jpg"
    assert image.is_file()
    assert image.stat().st_size <= 1_000_000
