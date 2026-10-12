from app.memory.episodes import episode_context_content


def test_unverified_episode_does_not_repeat_the_prior_assistant_outcome() -> None:
    content = episode_context_content(
        summary=(
            "Request: Để giữ cho server an toàn, cần làm gì. "
            "Outcome: Không tìm thấy hướng dẫn nội bộ."
        ),
        verified=False,
    )

    assert "Request: Để giữ cho server an toàn, cần làm gì" in content
    assert "outcome unverified" in content
    assert "Không tìm thấy hướng dẫn nội bộ" not in content


def test_verified_episode_keeps_its_documented_outcome() -> None:
    content = episode_context_content(
        summary="Request: VPN timeout. Outcome: Reconnected after renewing the profile.",
        verified=True,
    )

    assert "Prior verified support episode" in content
    assert "Reconnected after renewing the profile" in content
