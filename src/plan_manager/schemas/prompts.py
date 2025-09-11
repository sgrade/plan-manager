"""Pydantic schemas for MCP prompt inputs and outputs."""
from typing import List, Optional
from pydantic import BaseModel, Field


# Schemas for proposing Stories for a Plan
class StoryProposal(BaseModel):
    """A single story proposal."""
    title: str = Field(..., description="The concise title of the story.")
    description: str = Field(
        ..., description="A brief description of what the story entails (the 'what' and 'why').")


class ProposeStoriesIn(BaseModel):
    """Input schema for the propose_stories_for_plan prompt."""
    plan_id: Optional[str] = Field(
        default=None,
        description="ID of the plan to decompose. If omitted, the current plan is used.",
    )
    additional_context: Optional[str] = Field(
        default=None, description="Additional context to guide the generation of stories."
    )


class ProposeStoriesOut(BaseModel):
    """Output schema for the propose_stories_for_plan prompt."""
    stories: List[StoryProposal] = Field(
        ..., description="A list of proposed stories to implement the plan.")


# Schemas for proposing Tasks for a Story
class TaskProposal(BaseModel):
    """A single task proposal."""
    title: str = Field(..., description="The concise title of the task.")
    description: str = Field(...,
                             description="A brief description of what the task entails.")


class ProposeTasksIn(BaseModel):
    """Input schema for the propose_tasks_for_story prompt."""
    story_id: Optional[str] = Field(
        default=None,
        description="ID of the story to decompose. If omitted, the current story is used.",
    )
    additional_context: Optional[str] = Field(
        default=None, description="Additional context to guide the generation of tasks."
    )


class ProposeTasksOut(BaseModel):
    """Output schema for the propose_tasks_for_story prompt."""
    tasks: List[TaskProposal] = Field(
        ..., description="A list of proposed tasks to implement the story.")
