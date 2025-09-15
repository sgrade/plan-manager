"""Pydantic schemas for MCP prompt inputs and outputs."""
from typing import List
from pydantic import BaseModel, Field


# Schemas for proposing Stories for a Plan
class StoryProposal(BaseModel):
    """A single story proposal."""
    title: str = Field(..., description="The concise title of the story.")
    description: str = Field(
        ..., description="A brief description of what the story entails (the 'what' and 'why').")


class ProposeStoriesOut(BaseModel):
    """Output schema for the create_stories prompt."""
    stories: List[StoryProposal] = Field(
        ..., description="A list of proposed stories to implement the plan.")


# Schemas for proposing Tasks for a Story
class TaskProposal(BaseModel):
    """A single task proposal."""
    title: str = Field(..., description="The concise title of the task.")
    description: str = Field(...,
                             description="A brief description of what the task entails.")


class ProposeTasksOut(BaseModel):
    """Output schema for the create_tasks prompt."""
    tasks: List[TaskProposal] = Field(
        ..., description="A list of proposed tasks to implement the story.")
