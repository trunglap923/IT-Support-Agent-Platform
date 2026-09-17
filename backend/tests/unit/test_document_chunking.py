from uuid import UUID, uuid4

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


def test_preserves_multiline_command_with_its_vietnamese_instruction() -> None:
    text = """# Cài VPN

Trên Ubuntu, chạy lệnh sau rồi kiểm tra trạng thái:

```bash
sudo apt-get update
sudo apt-get install company-vpn
systemctl --user status company-vpn
```

# Verify

Open the client and sign in with company SSO.
"""
    chunks = chunk_blocks(
        version_id=uuid4(),
        blocks=[SourceBlock(text, 1, "VPN setup", "vpn-setup.md")],
        config=ChunkingConfig(target_tokens=16, overlap_tokens=3, hard_cap_tokens=28),
    )

    command_chunk = next(chunk for chunk in chunks if "sudo apt-get update" in chunk.content)
    assert "Trên Ubuntu, chạy lệnh sau" in command_chunk.content
    assert "sudo apt-get update\nsudo apt-get install company-vpn" in command_chunk.content
    assert command_chunk.page_number == 1
    assert command_chunk.section == "VPN setup"
    assert all(chunk.token_count <= 28 for chunk in chunks)


def test_heading_and_paragraph_boundaries_are_deterministic() -> None:
    text = """# Registry

Use a short-lived token for Docker Registry.

# GitLab

Đăng nhập GitLab bằng SSO của công ty.
"""
    block = SourceBlock(text, None, "Access", "access.md")
    config = ChunkingConfig(target_tokens=10, overlap_tokens=2, hard_cap_tokens=12)

    first = chunk_blocks(version_id=UUID(int=1), blocks=[block], config=config)
    second = chunk_blocks(version_id=UUID(int=1), blocks=[block], config=config)

    assert [(chunk.id, chunk.content) for chunk in first] == [
        (chunk.id, chunk.content) for chunk in second
    ]
    assert "# Registry" in first[0].content
    assert any("# GitLab" in chunk.content for chunk in first)
