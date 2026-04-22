from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.future import select

from app.models.projects import Project
from app.services.database import get_async_session
from app.routers.conversations import decode_email_from_token, get_user_id_from_email

router = APIRouter()

PROJECT_CONTEXT_COLUMNS = ("context", "goals", "decisions", "preferences")


class ProjectContextUpdate(BaseModel):
    context: Optional[str] = None
    goals: Optional[str] = None
    decisions: Optional[str] = None
    preferences: Optional[str] = None


class ProjectToolConfig(BaseModel):
    tool_name: str
    tool_config: Optional[str] = None
    is_enabled: bool = True


class ProjectContextResponse(BaseModel):
    context: Optional[str] = None
    goals: Optional[str] = None
    decisions: Optional[str] = None
    preferences: Optional[str] = None


async def _require_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    email = decode_email_from_token(token)
    return await get_user_id_from_email(email)


async def _get_owned_project(session, project_id: str, user_id: str) -> Project:
    result = await session.execute(
        select(Project)
        .where(Project.project_id == project_id)
        .where(Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _existing_project_context_columns(session) -> set[str]:
    result = await session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'projects'
              AND column_name IN ('context', 'goals', 'decisions', 'preferences')
            """
        )
    )
    return {row[0] for row in result.fetchall()}


async def _ensure_project_context_columns(session) -> None:
    for column_name in PROJECT_CONTEXT_COLUMNS:
        await session.execute(
            text(f"ALTER TABLE projects ADD COLUMN IF NOT EXISTS {column_name} TEXT")
        )
    await session.commit()


async def _read_project_context(session, project_id: str) -> ProjectContextResponse:
    existing_columns = await _existing_project_context_columns(session)
    if not set(PROJECT_CONTEXT_COLUMNS).issubset(existing_columns):
        return ProjectContextResponse()

    result = await session.execute(
        text(
            """
            SELECT context, goals, decisions, preferences
            FROM projects
            WHERE project_id = CAST(:project_id AS uuid)
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectContextResponse(
        context=row["context"],
        goals=row["goals"],
        decisions=row["decisions"],
        preferences=row["preferences"],
    )


async def _project_tools_table_exists(session) -> bool:
    result = await session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'project_tools'
            )
            """
        )
    )
    return bool(result.scalar())


async def _ensure_project_tools_table(session) -> None:
    await session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS project_tools (
                tool_id UUID PRIMARY KEY,
                project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                tool_name TEXT NOT NULL,
                tool_config TEXT,
                is_enabled TEXT NOT NULL DEFAULT 'true',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(project_id, tool_name)
            )
            """
        )
    )
    await session.commit()


@router.get("/projects/{project_id}/context", response_model=ProjectContextResponse)
async def get_project_context(request: Request, project_id: str):
    """Get project context fields for the authenticated project owner."""
    user_id = await _require_user_id(request)

    async for session in get_async_session():
        await _get_owned_project(session, project_id, user_id)
        return await _read_project_context(session, project_id)


@router.put("/projects/{project_id}/context", response_model=ProjectContextResponse)
async def update_project_context(
    request: Request,
    project_id: str,
    context_update: ProjectContextUpdate,
):
    """Update project context fields for the authenticated project owner."""
    user_id = await _require_user_id(request)

    async for session in get_async_session():
        await _get_owned_project(session, project_id, user_id)
        await _ensure_project_context_columns(session)

        update_values = {
            column_name: getattr(context_update, column_name)
            for column_name in PROJECT_CONTEXT_COLUMNS
            if getattr(context_update, column_name) is not None
        }

        if update_values:
            update_values["updated_at"] = datetime.utcnow()
            update_values["project_id"] = project_id
            set_clause = ", ".join(
                f"{column_name} = :{column_name}" for column_name in update_values if column_name != "project_id"
            )
            await session.execute(
                text(
                    f"""
                    UPDATE projects
                    SET {set_clause}
                    WHERE project_id = CAST(:project_id AS uuid)
                    """
                ),
                update_values,
            )
            await session.commit()

        return await _read_project_context(session, project_id)


@router.post("/projects/{project_id}/tools")
async def configure_project_tool(
    request: Request,
    project_id: str,
    tool_config: ProjectToolConfig,
):
    """Create or update a tool configuration for the authenticated project owner."""
    user_id = await _require_user_id(request)

    async for session in get_async_session():
        await _get_owned_project(session, project_id, user_id)
        await _ensure_project_tools_table(session)

        await session.execute(
            text(
                """
                INSERT INTO project_tools (
                    tool_id, project_id, tool_name, tool_config, is_enabled, updated_at
                )
                VALUES (
                    CAST(:tool_id AS uuid),
                    CAST(:project_id AS uuid),
                    :tool_name,
                    :tool_config,
                    :is_enabled,
                    :updated_at
                )
                ON CONFLICT (project_id, tool_name)
                DO UPDATE SET
                    tool_config = EXCLUDED.tool_config,
                    is_enabled = EXCLUDED.is_enabled,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "tool_id": str(uuid.uuid4()),
                "project_id": project_id,
                "tool_name": tool_config.tool_name,
                "tool_config": tool_config.tool_config,
                "is_enabled": "true" if tool_config.is_enabled else "false",
                "updated_at": datetime.utcnow(),
            },
        )
        await session.commit()
        return {"message": f"Tool {tool_config.tool_name} configured successfully"}


@router.get("/projects/{project_id}/tools", response_model=List[ProjectToolConfig])
async def get_project_tools(request: Request, project_id: str):
    """Get project tool configurations for the authenticated project owner."""
    user_id = await _require_user_id(request)

    async for session in get_async_session():
        await _get_owned_project(session, project_id, user_id)
        if not await _project_tools_table_exists(session):
            return []

        result = await session.execute(
            text(
                """
                SELECT tool_name, tool_config, is_enabled
                FROM project_tools
                WHERE project_id = CAST(:project_id AS uuid)
                ORDER BY tool_name
                """
            ),
            {"project_id": project_id},
        )
        return [
            ProjectToolConfig(
                tool_name=row["tool_name"],
                tool_config=row["tool_config"],
                is_enabled=row["is_enabled"] == "true",
            )
            for row in result.mappings().all()
        ]
