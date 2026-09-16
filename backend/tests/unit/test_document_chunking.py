from uuid import uuid4

import pytest

from app.rag.chunking.splitter import ChunkingConfig, SourceBlock, chunk_blocks


def test_chunk_boundaries_overlap_and_source_metadata() -> None:
    version_id = uuid4()
    words = [f"word-{index}" for index in range(18)]
    chunks = chunk_blocks(
        version_id=version_id,
        blocks=[
            SourceBlock(
                text=" ".join(words),
                page_number=2,
                section="Certificate setup",
                source_path="vpn.pdf",
            )
        ],
        config=ChunkingConfig(target_tokens=8, overlap_tokens=2, hard_cap_tokens=10),
    )

    assert [chunk.token_count for chunk in chunks] == [8, 8, 6]
    assert chunks[0].content.split()[-2:] == chunks[1].content.split()[:2]
    assert chunks[1].content.split()[-2:] == chunks[2].content.split()[:2]
    assert {chunk.page_number for chunk in chunks} == {2}
    assert {chunk.section for chunk in chunks} == {"Certificate setup"}
    assert [chunk.ordinal for chunk in chunks] == [0, 1, 2]


def test_ids_are_deterministic_and_config_sensitive() -> None:
    version_id = uuid4()
    blocks = [SourceBlock("one two three four", 1, "Test", "test.pdf")]

    first = chunk_blocks(version_id=version_id, blocks=blocks)
    second = chunk_blocks(version_id=version_id, blocks=blocks)
    changed = chunk_blocks(
        version_id=version_id,
        blocks=blocks,
        config=ChunkingConfig(version="word-window-v2"),
    )

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert first[0].id != changed[0].id
    assert first[0].content_hash == changed[0].content_hash


def test_empty_blocks_do_not_emit_chunks() -> None:
    assert (
        chunk_blocks(
            version_id=uuid4(),
            blocks=[SourceBlock("  \n\n ", None, None, "empty.md")],
        )
        == []
    )


@pytest.mark.parametrize(
    "config",
    [
        ChunkingConfig(target_tokens=10, overlap_tokens=9, hard_cap_tokens=10),
        ChunkingConfig(target_tokens=10, overlap_tokens=0, hard_cap_tokens=10),
    ],
)
def test_valid_boundary_configs(config: ChunkingConfig) -> None:
    chunks = chunk_blocks(
        version_id=uuid4(),
        blocks=[SourceBlock("one two", None, None, "test.md")],
        config=config,
    )
    assert len(chunks) == 1


def test_rejects_overlap_equal_to_target() -> None:
    with pytest.raises(ValueError, match="overlap"):
        ChunkingConfig(target_tokens=10, overlap_tokens=10)
