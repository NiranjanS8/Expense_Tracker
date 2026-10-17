from __future__ import annotations

from app.conversations.repository import ASSISTANT_ROLE, USER_ROLE, ConversationRepository


async def test_created_conversation_is_owned_and_active(repository: ConversationRepository) -> None:
    conversation = await repository.create(owner_id=1, title="This month")

    assert conversation.owner_id == 1
    assert conversation.status == "active"
    assert await repository.get_for_owner(1, conversation.id) == conversation


async def test_conversations_are_listed_per_owner(repository: ConversationRepository) -> None:
    await repository.create(owner_id=1, title="Mine")
    await repository.create(owner_id=2, title="Theirs")

    assert [c.title for c in await repository.list_for_owner(1, limit=10)] == ["Mine"]
    assert [c.title for c in await repository.list_for_owner(2, limit=10)] == ["Theirs"]


async def test_another_owners_conversation_is_invisible(repository: ConversationRepository) -> None:
    conversation = await repository.create(owner_id=1, title="Mine")

    assert await repository.get_for_owner(2, conversation.id) is None
    assert await repository.get_messages(2, conversation.id, limit=10) is None
    assert await repository.recent_messages(2, conversation.id, limit=10) is None
    assert await repository.count_messages(2, conversation.id) is None
    assert await repository.append_message(2, conversation.id, role=USER_ROLE, content="hi") is None


async def test_messages_preserve_order_and_are_bounded_for_the_model(
    repository: ConversationRepository,
) -> None:
    conversation = await repository.create(owner_id=1, title="Mine")
    for index in range(5):
        await repository.append_message(1, conversation.id, role=USER_ROLE, content=f"m{index}")

    everything = await repository.get_messages(1, conversation.id, limit=10)
    assert everything is not None
    assert [message.content for message in everything] == ["m0", "m1", "m2", "m3", "m4"]

    recent = await repository.recent_messages(1, conversation.id, limit=2)
    assert recent is not None
    # The context window is the newest messages, but still oldest-first.
    assert [message.content for message in recent] == ["m3", "m4"]
    assert await repository.count_messages(1, conversation.id) == 5


async def test_roles_round_trip(repository: ConversationRepository) -> None:
    conversation = await repository.create(owner_id=1, title="Mine")
    await repository.append_message(1, conversation.id, role=USER_ROLE, content="q")
    await repository.append_message(1, conversation.id, role=ASSISTANT_ROLE, content="a")

    messages = await repository.get_messages(1, conversation.id, limit=10)
    assert messages is not None
    assert [(message.role, message.content) for message in messages] == [
        (USER_ROLE, "q"),
        (ASSISTANT_ROLE, "a"),
    ]


async def test_delete_is_owner_scoped_and_idempotent(repository: ConversationRepository) -> None:
    conversation = await repository.create(owner_id=1, title="Mine")
    await repository.append_message(1, conversation.id, role=USER_ROLE, content="hi")

    assert await repository.delete(2, conversation.id) is False
    assert await repository.delete(1, conversation.id) is True
    assert await repository.get_for_owner(1, conversation.id) is None
    assert await repository.delete(1, conversation.id) is False


async def test_delete_all_for_owner_removes_only_that_owners_data(
    repository: ConversationRepository,
) -> None:
    for index in range(3):
        conversation = await repository.create(owner_id=1, title=f"Mine {index}")
        await repository.append_message(1, conversation.id, role=USER_ROLE, content="hi")
    await repository.create(owner_id=2, title="Theirs")

    assert await repository.delete_all_for_owner(1) == 3
    assert await repository.list_for_owner(1, limit=10) == []
    assert len(await repository.list_for_owner(2, limit=10)) == 1
