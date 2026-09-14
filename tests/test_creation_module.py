"""Focused integration tests for Creation Module V1 with real Memory storage."""

import json
import tempfile
import unittest
from pathlib import Path

from creation_module import CreationModule, FieldOrigin, MetadataLayer, OllamaCreationGenerator
from creation_module.errors import ApprovalError, SourceChangedError, ValidationError
from creation_module.models import CategorizationProposal, MemoryBrickProposal, SourceCategorization
from memory_module import MemoryKnowledgeSourceAdapter, MemoryProposalAdapter, MemoryService


class FakeGenerator:
    def generate_metadata(self, source, layers):
        return {layer: f"Generated {layer.value} for {source.raw_source[:16]}" for layer in layers}

    def categorize_source(self, source):
        return CategorizationProposal(source.source_id, source.source_hash, SourceCategorization.create(domains=("project",), kinds=(source.source_type,), categories=("requirements",)), 0.8)

    def propose_memory_bricks(self, source):
        return [MemoryBrickProposal.create(source_id=source.source_id, source_hash=source.source_hash, content="Creation requires explicit approval.", domains=("project",), kinds=("decision",), categories=("safety",), scope="global", evidence="Registered source sentence.", importance=0.8, confidence=0.9)]

    def generate_workspace_fields(self, kind, request, fields):
        return {field: f"{kind.title()} proposal" for field in fields}


class FakeWorkspaceOwner:
    def __init__(self):
        self.created = []

    def create_sheet(self, proposal):
        self.created.append(proposal)
        return type("Sheet", (), {"sheet_id": "sheet-1"})()

    def create_comment(self, proposal):
        self.created.append(proposal)
        return type("Comment", (), {"comment_id": "comment-1"})()

    def create_memory(self, proposal):
        self.created.append(proposal)
        return type("Memory", (), {"memory_id": "memory-1"})()


class FakeOllama:
    def __init__(self, response):
        self.response = response

    def generate(self, prompt, system_prompt=None):
        return self.response


class CreationModuleTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.memory = MemoryService(Path(self.temporary_directory.name))
        self.registered = self.memory.register_knowledge_source(source_type="development-note", owner_module="test", title="Manual title", raw_locator="test-source", raw_content="Creation must preserve raw source. Memory proposals require explicit approval.")
        self.sources = MemoryKnowledgeSourceAdapter(self.memory)
        self.module = CreationModule(source_service=self.sources, memory_service=MemoryProposalAdapter(self.memory), generator=FakeGenerator())

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_missing_metadata_preserves_manual_field_and_is_idempotent(self):
        self.sources.update_metadata(source_id=self.registered.source_id, expected_source_hash=self.sources.get_source(self.registered.source_id).source_hash, updates={MetadataLayer.TITLE: "Manual project title"}, generated=False)
        first = self.module.generate_missing_metadata(self.registered.source_id)
        updated = self.sources.get_source(self.registered.source_id)
        second = self.module.generate_missing_metadata(self.registered.source_id)

        self.assertIn("title", first.preserved_fields)
        self.assertEqual("Manual project title", updated.title.value)
        self.assertEqual(FieldOrigin.MANUAL, updated.title.origin)
        self.assertTrue(updated.description.value)
        self.assertEqual(updated.source_hash, updated.description.generated_from_hash)
        self.assertEqual((), second.changed_fields)

    def test_manual_metadata_requires_explicit_replacement_and_raw_content_is_unchanged(self):
        source = self.sources.get_source(self.registered.source_id)
        before = source.raw_source
        protected = self.module.regenerate_selected_metadata(self.registered.source_id, [MetadataLayer.TITLE])
        forced = self.module.regenerate_selected_metadata(self.registered.source_id, [MetadataLayer.TITLE], replace_manual=True)
        categorization = self.module.categorize_source(self.registered.source_id, apply_changes=True)

        updated = self.sources.get_source(self.registered.source_id)
        self.assertEqual((), protected.changed_fields)
        self.assertEqual(("title",), protected.preserved_fields)
        self.assertEqual(("title",), forced.changed_fields)
        self.assertEqual(FieldOrigin.GENERATED, updated.title.origin)
        self.assertEqual(before, updated.raw_source)
        self.assertEqual(categorization.categorization, updated.categorization)

    def test_proposals_remain_temporary_and_only_approved_ids_persist(self):
        proposals = self.module.propose_memory_bricks(self.registered.source_id)
        self.assertEqual([], self.memory.search_memory_bricks())

        result = self.module.create_approved_memory_bricks(self.registered.source_id, proposals, {proposals[0].proposal_id})
        self.assertEqual(1, len(result.created_memory_ids))
        self.assertEqual(1, len(self.memory.list_global_memory()))
        brick = self.memory.get_memory_brick(result.created_memory_ids[0])
        self.assertEqual("approved_creation_proposal", brick.creation_source)
        self.assertEqual(self.registered.source_id, brick.evidence["source_id"])

    def test_unknown_or_stale_approval_is_rejected(self):
        proposals = self.module.propose_memory_bricks(self.registered.source_id)
        with self.assertRaises(ApprovalError):
            self.module.create_approved_memory_bricks(self.registered.source_id, proposals, {"unknown"})
        with self.assertRaises(ValidationError):
            self.module.create_approved_memory_bricks(
                self.registered.source_id, proposals + proposals, {proposals[0].proposal_id}
            )
        self.memory.register_knowledge_source(source_type="development-note", owner_module="test", title="Manual title", raw_locator="test-source", source_id=self.registered.source_id, raw_content="Changed content after proposal generation.")
        with self.assertRaises(SourceChangedError):
            self.module.create_approved_memory_bricks(self.registered.source_id, proposals, {proposals[0].proposal_id})

    def test_generated_metadata_refreshes_after_explicit_source_update(self):
        self.module.generate_missing_metadata(self.registered.source_id)
        old = self.sources.get_source(self.registered.source_id).description.value
        self.memory.register_knowledge_source(source_type="development-note", owner_module="test", title="Manual title", raw_locator="test-source", source_id=self.registered.source_id, raw_content="Creation metadata has new source content.")
        result = self.module.refresh_generated_metadata(self.registered.source_id)
        updated = self.sources.get_source(self.registered.source_id)
        self.assertIn("description", result.changed_fields)
        self.assertNotEqual(old, updated.description.value)
        self.assertEqual(updated.source_hash, updated.description.generated_from_hash)

    def test_ollama_adapter_rejects_non_json_and_validates_typed_json(self):
        source = self.sources.get_source(self.registered.source_id)
        with self.assertRaises(ValidationError):
            OllamaCreationGenerator(FakeOllama("not json")).generate_metadata(source, [MetadataLayer.TITLE])
        response = json.dumps({"metadata": {"title": "Typed title"}})
        self.assertEqual({MetadataLayer.TITLE: "Typed title"}, OllamaCreationGenerator(FakeOllama(response)).generate_metadata(source, [MetadataLayer.TITLE]))

    def test_workspace_creation_is_immediate_and_defaults_to_global_scope(self):
        owner = FakeWorkspaceOwner()
        module = CreationModule(source_service=self.sources, memory_service=MemoryProposalAdapter(self.memory), generator=FakeGenerator(), workspace_service=owner)

        result = module.create_workspace_object("memory", "Remember this", chat_id="chat-1")

        self.assertEqual(("memory-1",), result.created_ids)
        self.assertEqual(("global", None), (owner.created[0].scope, owner.created[0].chat_id))


if __name__ == "__main__":
    unittest.main()
