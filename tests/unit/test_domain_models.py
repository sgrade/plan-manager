"""Unit tests for domain models."""

from plan_manager.domain.models import Plan, Story, Task, Status


class TestPlanModel:
    """Test Plan domain model."""

    def test_plan_creation_minimal(self):
        """Test creating a plan with minimal required fields."""
        plan = Plan(id="test-plan", title="Test Plan")
        assert plan.id == "test-plan"
        assert plan.title == "Test Plan"
        assert plan.description is None
        assert plan.priority is None
        assert plan.status == Status.TODO
        assert len(plan.stories) == 0

    def test_plan_creation_full(self):
        """Test creating a plan with all fields."""
        plan = Plan(
            id="test-plan",
            title="Test Plan",
            description="A test plan",
            priority=1,
            status=Status.IN_PROGRESS
        )
        assert plan.id == "test-plan"
        assert plan.title == "Test Plan"
        assert plan.description == "A test plan"
        assert plan.priority == 1
        assert plan.status == Status.IN_PROGRESS

    def test_plan_status_enum(self):
        """Test that status must be a valid Status enum."""
        plan = Plan(id="test-plan", title="Test Plan", status=Status.DONE)
        assert plan.status == Status.DONE


class TestStoryModel:
    """Test Story domain model."""

    def test_story_creation_minimal(self):
        """Test creating a story with minimal required fields."""
        story = Story(id="test-story", title="Test Story")
        assert story.id == "test-story"
        assert story.title == "Test Story"
        assert story.description is None
        assert story.acceptance_criteria is None
        assert story.priority is None
        assert story.status == Status.TODO
        assert len(story.tasks) == 0
        assert story.depends_on == []

    def test_story_creation_full(self):
        """Test creating a story with all fields."""
        story = Story(
            id="test-story",
            title="Test Story",
            description="A test story",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            priority=2,
            status=Status.IN_PROGRESS,
            depends_on=["other-story"],
            file_path="stories/test-story.md"
        )
        assert story.id == "test-story"
        assert story.title == "Test Story"
        assert story.description == "A test story"
        assert story.acceptance_criteria == ["Criterion 1", "Criterion 2"]
        assert story.priority == 2
        assert story.status == Status.IN_PROGRESS
        assert story.depends_on == ["other-story"]
        assert story.file_path == "stories/test-story.md"


class TestTaskModel:
    """Test Task domain model."""

    def test_task_creation_minimal(self):
        """Test creating a task with minimal required fields."""
        task = Task(id="story-1:task-1", title="Test Task",
                    story_id="story-1", local_id="task-1")
        assert task.id == "story-1:task-1"
        assert task.title == "Test Task"
        assert task.story_id == "story-1"
        assert task.local_id == "task-1"
        assert task.description is None
        assert task.priority is None
        assert task.status == Status.TODO
        assert task.depends_on == []
        assert task.steps == []  # Default is empty list, not None
        assert task.execution_summary is None

    def test_task_creation_full(self):
        """Test creating a task with all fields."""
        from plan_manager.domain.models import Task

        task = Task(
            id="story-1:task-1",
            title="Test Task",
            story_id="story-1",
            local_id="task-1",
            description="A test task",
            priority=3,
            status=Status.IN_PROGRESS,
            depends_on=["task-2"],
            steps=[
                Task.Step(title="Step 1", description="First step"),
                Task.Step(title="Step 2")
            ],
            execution_summary="Completed successfully"
        )
        assert task.id == "story-1:task-1"
        assert task.title == "Test Task"
        assert task.description == "A test task"
        assert task.priority == 3
        assert task.status == Status.IN_PROGRESS
        assert task.depends_on == ["task-2"]
        assert len(task.steps) == 2
        assert task.steps[0].title == "Step 1"
        assert task.steps[0].description == "First step"
        assert task.steps[1].title == "Step 2"
        assert task.steps[1].description is None
        assert task.execution_summary == "Completed successfully"

    def test_task_step_creation(self):
        """Test creating task steps."""
        step1 = Task.Step(title="Implement feature")
        assert step1.title == "Implement feature"
        assert step1.description is None

        step2 = Task.Step(title="Add tests",
                          description="Write comprehensive tests")
        assert step2.title == "Add tests"
        assert step2.description == "Write comprehensive tests"


class TestStatusEnum:
    """Test Status enum values."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert Status.TODO == "TODO"
        assert Status.IN_PROGRESS == "IN_PROGRESS"
        assert Status.PENDING_REVIEW == "PENDING_REVIEW"
        assert Status.DONE == "DONE"
        assert Status.BLOCKED == "BLOCKED"
        assert Status.DEFERRED == "DEFERRED"

    def test_status_string_conversion(self):
        """Test string conversion of status enum."""
        assert str(Status.TODO) == "Status.TODO"
        assert Status.TODO.value == "TODO"


class TestModelValidation:
    """Test model validation rules."""

    def test_task_id_format(self):
        """Test that task ID format is accepted."""
        # This should work as long as the model accepts the ID format
        task = Task(id="story-1:task-1", title="Test",
                    story_id="story-1", local_id="task-1")
        assert task.id == "story-1:task-1"


class TestModelSerialization:
    """Test model serialization/deserialization."""

    def test_plan_model_dump(self):
        """Test that Plan can be serialized."""
        plan = Plan(id="test-plan", title="Test Plan",
                    description="A test plan")
        data = plan.model_dump()
        assert data["id"] == "test-plan"
        assert data["title"] == "Test Plan"
        assert data["description"] == "A test plan"
        assert data["status"] == "TODO"

    def test_story_model_dump(self):
        """Test that Story can be serialized."""
        story = Story(id="test-story", title="Test Story")
        data = story.model_dump()
        assert data["id"] == "test-story"
        assert data["title"] == "Test Story"
        assert data["status"] == "TODO"

    def test_task_model_dump(self):
        """Test that Task can be serialized."""
        task = Task(id="story-1:task-1", title="Test Task",
                    story_id="story-1", local_id="task-1")
        data = task.model_dump()
        assert data["id"] == "story-1:task-1"
        assert data["title"] == "Test Task"
        assert data["status"] == "TODO"
