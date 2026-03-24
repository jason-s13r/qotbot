import logging
from fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from qotbot.database.database import get_session
from qotbot.database.models.todo import TodoList, TodoListItem, EditorMode
from qotbot.database.models.chat import ChatMember

logger = logging.getLogger(__name__)

todo_tools = FastMCP("Todo Lists")


@todo_tools.tool
async def create_todo_list(
    name: str,
    chat_id: int,
    owner_id: int,
    description: str = None,
    list_type: str = None,
    editor_mode: str = "list_owner",
) -> str:
    """
    Create a new todo list for a chat.

    Args:
        name: Name of the list (e.g., "Shopping List", "Tasks")
        chat_id: Telegram chat ID where the list belongs
        owner_id: Telegram user ID of the list owner
        description: Optional description of the list
        list_type: Optional type (e.g., "shopping", "todo", "wishlist")
        editor_mode: Who can edit - "list_owner", "chat_admin", or "chat_participants"

    Returns:
        Confirmation message with the created list details
    """
    editor_mode_enum = EditorMode(editor_mode)

    async with get_session() as session:
        todo_list = TodoList(
            name=name,
            chat_id=chat_id,
            owner_id=owner_id,
            description=description,
            list_type=list_type,
            editor_mode=editor_mode_enum,
        )
        session.add(todo_list)
        await session.commit()
        await session.refresh(todo_list)

        return f"Created list '{name}' (ID: {todo_list.id}) with editor mode: {editor_mode}"


@todo_tools.tool
async def get_todo_lists(chat_id: int, owner_id: int = None) -> str:
    """
    Get all todo lists for a chat, optionally filtered by owner.

    Args:
        chat_id: Telegram chat ID
        owner_id: Optional Telegram user ID to filter lists by owner

    Returns:
        Formatted text string with list details
    """
    async with get_session() as session:
        query = select(TodoList).where(
            TodoList.chat_id == chat_id,
            TodoList.is_active == True,
        )

        if owner_id:
            query = query.where(TodoList.owner_id == owner_id)

        query = query.order_by(TodoList.created_at.desc()).options(
            selectinload(TodoList.items)
        )
        result = await session.execute(query)
        lists = result.scalars().all()

        if not lists:
            raise ValueError("No todo lists found for this chat")

        output = []
        for lst in lists:
            output.append(
                f"ID: {lst.id}, Name: {lst.name}, Type: {lst.list_type or 'N/A'}, "
                f"Editor Mode: {lst.editor_mode.value}, Items: {len(lst.items)}"
            )

        return "\n".join(output)


@todo_tools.tool
async def get_todo_list(list_id: int) -> str:
    """
    Get a specific todo list with all its items.

    Args:
        list_id: The ID of the todo list

    Returns:
        Formatted text string with list and item details
    """
    async with get_session() as session:
        result = await session.execute(
            select(TodoList)
            .options(selectinload(TodoList.items))
            .where(TodoList.id == list_id)
        )
        todo_list = result.scalar_one_or_none()

        if not todo_list:
            raise ValueError(f"List with ID {list_id} not found")

        items_output = []
        for item in sorted(todo_list.items, key=lambda x: x.position):
            status = "✓" if item.is_completed else "○"
            items_output.append(
                f"{status} {item.id}: {item.content}"
                + (f" (completed at {item.completed_at})" if item.completed_at else "")
            )

        return (
            f"List: {todo_list.name} (ID: {todo_list.id})\n"
            f"Description: {todo_list.description or 'N/A'}\n"
            f"Type: {todo_list.list_type or 'N/A'}\n"
            f"Editor Mode: {todo_list.editor_mode.value}\n"
            f"Items ({len(items_output)}):\n" + "\n".join(items_output)
        )


@todo_tools.tool
async def update_todo_list(
    list_id: int,
    name: str = None,
    description: str = None,
    list_type: str = None,
    editor_mode: str = None,
) -> str:
    """
    Update a todo list's properties.

    Args:
        list_id: The ID of the todo list to update
        name: New name for the list
        description: New description
        list_type: New type
        editor_mode: New editor mode - "list_owner", "chat_admin", or "chat_participants"

    Returns:
        Confirmation message with updated details
    """
    async with get_session() as session:
        result = await session.execute(select(TodoList).where(TodoList.id == list_id))
        todo_list = result.scalar_one_or_none()

        if not todo_list:
            raise ValueError(f"List with ID {list_id} not found")

        if name is not None:
            todo_list.name = name
        if description is not None:
            todo_list.description = description
        if list_type is not None:
            todo_list.list_type = list_type
        if editor_mode is not None:
            todo_list.editor_mode = EditorMode(editor_mode)

        todo_list.updated_at = datetime.utcnow()
        await session.commit()

        return f"Updated list '{todo_list.name}' (ID: {todo_list.id})"


@todo_tools.tool
async def delete_todo_list(list_id: int) -> str:
    """
    Delete a todo list and all its items.

    Args:
        list_id: The ID of the todo list to delete

    Returns:
        Confirmation message
    """
    async with get_session() as session:
        result = await session.execute(select(TodoList).where(TodoList.id == list_id))
        todo_list = result.scalar_one_or_none()

        if not todo_list:
            raise ValueError(f"List with ID {list_id} not found")

        name = todo_list.name
        await session.delete(todo_list)
        await session.commit()

        return f"Deleted list '{name}' (ID: {list_id}) and all its items"


@todo_tools.tool
async def add_todo_item(
    list_id: int,
    content: str,
    created_by: int,
    position: int = None,
) -> str:
    """
    Add a new item to a todo list.

    Args:
        list_id: The ID of the todo list
        content: The item content (e.g., "milk")
        created_by: Telegram user ID who created the item
        position: Optional position in the list (auto-assigned if not provided)

    Returns:
        Confirmation message with the created item details
    """
    async with get_session() as session:
        todo_list = await session.get(TodoList, list_id)

        if not todo_list:
            raise ValueError(f"List with ID {list_id} not found")

        if position is None:
            max_pos_result = await session.execute(
                select(TodoListItem.position)
                .where(TodoListItem.list_id == list_id)
                .order_by(TodoListItem.position.desc())
                .limit(1)
                .with_for_update()
            )
            max_pos = max_pos_result.scalar_one_or_none()
            position = (max_pos or 0) + 1

        item = TodoListItem(
            list_id=list_id,
            content=content,
            created_by=created_by,
            position=position,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)

        return f"Added '{content}' to list '{todo_list.name}' (Item ID: {item.id}, Position: {position})"


@todo_tools.tool
async def get_todo_item(item_id: int) -> str:
    """
    Get a specific todo item.

    Args:
        item_id: The ID of the todo item

    Returns:
        Formatted text string with item details
    """
    async with get_session() as session:
        item = await session.get(TodoListItem, item_id)

        if not item:
            raise ValueError(f"Item with ID {item_id} not found")

        status = "completed" if item.is_completed else "pending"
        return (
            f"Item ID: {item.id}\n"
            f"List ID: {item.list_id}\n"
            f"Content: {item.content}\n"
            f"Status: {status}\n"
            f"Position: {item.position}\n"
            f"Created by: {item.created_by}\n"
            f"Created at: {item.created_at}"
        )


@todo_tools.tool
async def update_todo_item(
    item_id: int,
    content: str = None,
    is_completed: bool = None,
    position: int = None,
) -> str:
    """
    Update a todo item's properties.

    Args:
        item_id: The ID of the todo item to update
        content: New content text
        is_completed: Mark as completed (True) or not (False)
        position: New position in the list

    Returns:
        Confirmation message with updated details
    """
    async with get_session() as session:
        item = await session.get(TodoListItem, item_id)

        if not item:
            raise ValueError(f"Item with ID {item_id} not found")

        if content is not None:
            item.content = content
        if is_completed is not None:
            item.is_completed = is_completed
            if is_completed and not item.completed_at:
                item.completed_at = datetime.utcnow()
            elif not is_completed:
                item.completed_at = None
        if position is not None:
            item.position = position

        item.updated_at = datetime.utcnow()
        await session.commit()

        status = "completed" if item.is_completed else "pending"
        return f"Updated item (ID: {item.id}) - Status: {status}"


@todo_tools.tool
async def complete_todo_item(item_id: int) -> str:
    """
    Mark a todo item as completed.

    Args:
        item_id: The ID of the todo item to complete

    Returns:
        Confirmation message
    """
    async with get_session() as session:
        item = await session.get(TodoListItem, item_id)

        if not item:
            raise ValueError(f"Item with ID {item_id} not found")

        item.is_completed = True
        item.completed_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()
        await session.commit()

        return f"Marked item '{item.content}' (ID: {item_id}) as completed"


@todo_tools.tool
async def delete_todo_item(item_id: int) -> str:
    """
    Delete a todo item from its list.

    Args:
        item_id: The ID of the todo item to delete

    Returns:
        Confirmation message
    """
    async with get_session() as session:
        item = await session.get(TodoListItem, item_id)

        if not item:
            raise ValueError(f"Item with ID {item_id} not found")

        content = item.content
        await session.delete(item)
        await session.commit()

        return f"Deleted item '{content}' (ID: {item_id})"


@todo_tools.tool
async def check_edit_permission(
    list_id: int,
    user_id: int,
) -> str:
    """
    Check if a user has permission to edit a todo list.

    Args:
        list_id: The ID of the todo list
        user_id: The Telegram user ID to check permissions for

    Returns:
        Permission status and reason
    """
    async with get_session() as session:
        todo_list = await session.get(TodoList, list_id)

        if not todo_list:
            raise ValueError(f"List with ID {list_id} not found")

        if todo_list.editor_mode == EditorMode.LIST_OWNER:
            if user_id == todo_list.owner_id:
                return f"Allowed: User is the list owner"
            raise PermissionError("List is only editable by owner")

        elif todo_list.editor_mode == EditorMode.CHAT_ADMIN:
            result = await session.execute(
                select(ChatMember).where(
                    ChatMember.chat_id == todo_list.chat_id,
                    ChatMember.user_id == user_id,
                    ChatMember.is_admin == True,
                )
            )
            chat_member = result.scalar_one_or_none()

            if not chat_member:
                raise PermissionError("User is not a chat admin")
            return f"Allowed: User is a chat admin"

        elif todo_list.editor_mode == EditorMode.CHAT_PARTICIPANTS:
            result = await session.execute(
                select(ChatMember).where(
                    ChatMember.chat_id == todo_list.chat_id,
                    ChatMember.user_id == user_id,
                )
            )
            chat_member = result.scalar_one_or_none()

            if not chat_member:
                raise PermissionError("User is not a chat member")
            return f"Allowed: List is editable by all chat participants"

        raise ValueError("Unknown editor mode")


if __name__ == "__main__":
    todo_tools.run()
