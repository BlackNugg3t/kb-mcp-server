"""
Tests for src.kb_export: export/import bundle round-trip, merge/replace
semantics, and the import-time security guarantees (never trust a bundle's
own path or content_hash).
"""

import pytest

from src.kb_export import export_bundle, import_bundle
from src.storage.indexer import Indexer
from src.storage.models import IndexEntry, ItemType, Source


def _seed_entry(indexer: Indexer, entry_id: str, content: str, title: str = "Test") -> IndexEntry:
    entry = IndexEntry(
        id=entry_id, type=ItemType.KNOWLEDGE, source=Source.GITHUB,
        source_id=f"repo#{entry_id}", path="placeholder.md", title=title, tags=["bug"],
    )
    file_path = indexer.make_file_path(entry.id, entry.type)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    entry.path = str(file_path.relative_to(indexer.base_path))
    entry.content_hash = Indexer.compute_content_hash(content)
    indexer.add_or_update(entry)
    return entry


class TestExportImportRoundTrip:
    def test_round_trip_preserves_content(self, tmp_path):
        src_indexer = Indexer(base_path=tmp_path / "source")
        _seed_entry(src_indexer, "gh-issue-1", "# Hello\ncontent", title="Hello")
        src_indexer.save()

        bundle = export_bundle(src_indexer)
        assert bundle["format_version"] == 1
        assert len(bundle["entries"]) == 1

        dst_indexer = Indexer(base_path=tmp_path / "dest")
        summary = import_bundle(dst_indexer, bundle, mode="merge")
        dst_indexer.save()

        assert summary["added"] == 1
        entry = dst_indexer.get_entry("gh-issue-1")
        assert entry is not None
        assert entry.title == "Hello"
        content = (dst_indexer.base_path / entry.path).read_text()
        assert content == "# Hello\ncontent"

    def test_reimport_unchanged_content_is_skipped(self, tmp_path):
        src_indexer = Indexer(base_path=tmp_path / "source")
        _seed_entry(src_indexer, "gh-issue-1", "content", title="X")
        bundle = export_bundle(src_indexer)

        dst_indexer = Indexer(base_path=tmp_path / "dest")
        import_bundle(dst_indexer, bundle, mode="merge")
        summary2 = import_bundle(dst_indexer, bundle, mode="merge")

        assert summary2 == {"added": 0, "updated": 0, "unchanged": 1, "deleted": 0, "skipped_invalid": 0}

    def test_changed_content_is_updated(self, tmp_path):
        src_indexer = Indexer(base_path=tmp_path / "source")
        _seed_entry(src_indexer, "gh-issue-1", "v1", title="X")
        bundle = export_bundle(src_indexer)

        dst_indexer = Indexer(base_path=tmp_path / "dest")
        import_bundle(dst_indexer, bundle, mode="merge")

        # Simulate a newer export with changed content.
        bundle["entries"][0]["content"] = "v2"
        summary = import_bundle(dst_indexer, bundle, mode="merge")

        assert summary["updated"] == 1
        entry = dst_indexer.get_entry("gh-issue-1")
        content = (dst_indexer.base_path / entry.path).read_text()
        assert content == "v2"

    def test_replace_mode_deletes_absent_entries(self, tmp_path):
        dst_indexer = Indexer(base_path=tmp_path / "dest")
        _seed_entry(dst_indexer, "gh-issue-1", "keep", title="Keep")
        _seed_entry(dst_indexer, "gh-issue-2", "remove me", title="Remove")
        dst_indexer.save()

        bundle = {
            "format_version": 1,
            "entries": [{
                "entry": dst_indexer.get_entry("gh-issue-1").model_dump(mode="json"),
                "content": "keep",
            }],
        }

        summary = import_bundle(dst_indexer, bundle, mode="replace")

        assert summary["deleted"] == 1
        assert dst_indexer.get_entry("gh-issue-2") is None
        assert not (dst_indexer.base_path / "knowledge" / "gh-issue-2.md").exists()

    def test_invalid_mode_raises(self, tmp_path):
        indexer = Indexer(base_path=tmp_path / "kb")
        with pytest.raises(ValueError):
            import_bundle(indexer, {"entries": []}, mode="bogus")


class TestImportSecurity:
    def test_malicious_path_and_id_cannot_escape_base_path(self, tmp_path):
        indexer = Indexer(base_path=tmp_path / "kb")

        malicious_bundle = {
            "format_version": 1,
            "entries": [{
                "entry": {
                    "id": "../../../../etc/passwd-pwned",
                    "type": "knowledge",
                    "source": "github",
                    "source_id": "x",
                    "path": "/etc/passwd",
                    "title": "evil",
                    "tags": [],
                },
                "content": "PWNED",
            }],
        }

        summary = import_bundle(indexer, malicious_bundle, mode="merge")
        assert summary["added"] == 1

        entry = indexer.index.entries[0]
        written_path = (indexer.base_path / entry.path).resolve()
        assert str(written_path).startswith(str(indexer.base_path.resolve()))
        assert ".." not in entry.path

    def test_bogus_declared_hash_is_ignored(self, tmp_path):
        indexer = Indexer(base_path=tmp_path / "kb")

        bundle = {
            "format_version": 1,
            "entries": [{
                "entry": {
                    "id": "gh-issue-1", "type": "knowledge", "source": "github",
                    "source_id": "x", "path": "knowledge/gh-issue-1.md", "title": "t",
                    "tags": [], "content_hash": "not-the-real-hash",
                },
                "content": "actual content",
            }],
        }

        import_bundle(indexer, bundle, mode="merge")

        entry = indexer.get_entry("gh-issue-1")
        assert entry.content_hash == Indexer.compute_content_hash("actual content")
        assert entry.content_hash != "not-the-real-hash"

    def test_invalid_entry_is_skipped_not_raised(self, tmp_path):
        indexer = Indexer(base_path=tmp_path / "kb")
        bundle = {"format_version": 1, "entries": [{"entry": {"id": "x"}, "content": "y"}]}

        summary = import_bundle(indexer, bundle, mode="merge")

        assert summary["skipped_invalid"] == 1
        assert indexer.index.entries == []
