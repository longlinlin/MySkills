import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parent


class SkillPackageTests(unittest.TestCase):
    def test_package_has_one_skill_entry(self):
        entries = [
            path.relative_to(SKILL_ROOT).as_posix()
            for path in SKILL_ROOT.rglob("SKILL.md")
            if "output" not in path.relative_to(SKILL_ROOT).parts
        ]
        self.assertEqual(entries, ["SKILL.md"])

    def test_local_document_links_resolve(self):
        documents = []
        repository_readme = REPOSITORY_ROOT / "README.md"
        if (REPOSITORY_ROOT / ".git").exists() and repository_readme.is_file():
            documents.append(repository_readme)
        documents.extend(
            path for path in SKILL_ROOT.rglob("*.md")
            if "output" not in path.relative_to(SKILL_ROOT).parts
        )
        checked = 0
        for document in documents:
            inside_fence = False
            for line in document.read_text(encoding="utf-8-sig").splitlines():
                if re.match(r"^\s*(```|~~~)", line):
                    inside_fence = not inside_fence
                    continue
                if inside_fence:
                    continue
                for match in re.finditer(r"\[[^\]]+\]\(([^\s)]+)\)", line):
                    target = urlsplit(match.group(1))
                    if target.scheme or target.netloc or not target.path:
                        continue
                    checked += 1
                    destination = document.parent / unquote(target.path)
                    with self.subTest(document=document, target=target.path):
                        self.assertTrue(destination.exists(), str(destination))
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
