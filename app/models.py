from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel
from datetime import datetime, date

class Users(SQLModel, table=True):
    user_id: int = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, nullable=False)
    email: str = Field(max_length=100, nullable=False)
    password: str = Field(max_length=255, nullable=False)
    full_name: str | None = Field(default=None, max_length=100)
    role: str = Field(default="member", max_length=50)
    created_at: datetime = Field(default=datetime.utcnow)
    updated_at: datetime = Field(default=datetime.utcnow)
    deleted_at: datetime | None = Field(default=None)

class ProjectPublic(SQLModel):
    project_id: int = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, nullable=False) 
    # created_by: int = Field(index=True, foreign_key="users.user_id")
    start_date: date | None = Field(default=None) 
    end_date: date | None = Field(default=None)

class Projects(ProjectPublic, table=True):    
    description: str | None = Field(default=None)  
    status: str = Field(default="active", max_length=50) 
    created_at: datetime = Field(default=datetime.utcnow)
    updated_at: datetime = Field(default=datetime.utcnow)
    deleted_at: datetime | None = Field(default=None) 

class TasksBase(SQLModel):
    title: str = Field(..., max_length=100)
    description: str | None = None
    status: str = Field(default="Pending", max_length=50, index=True)
    phase: str = Field(default="Implement", max_length=50, index=True)
    start_date: date | None = None
    due_date: date | None = None

class Tasks(TasksBase, table=True):
    task_id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="projects.project_id")
    created_by: int = Field(index=True, foreign_key="users.user_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

class TasksCreate(TasksBase):
    project_id: int

class TasksUpdate(TasksBase):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    phase: str | None = None
    start_date: date | None = None
    due_date: date | None = None

class TasksPublic(TasksBase):
    task_id: int
    project_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

class AssignmentsBase(SQLModel):
    task_id: int | None = Field(index=True, foreign_key="tasks.task_id")
    user_id: int = Field(index=True, foreign_key="users.user_id")
    assigned_at: datetime | None = Field(default_factory=datetime.utcnow)

class Assignments(AssignmentsBase, table=True):
    assigned_id: int | None = Field(default=None, primary_key=True)
    assigned_by: int | None = Field(index=True, foreign_key="users.user_id")

class AssignmentsCreate(AssignmentsBase):
    pass

class AssignmentsPublic(AssignmentsBase):
    assigned_id: int
    assigned_by: int

class Jwt_Auth(BaseModel):
    user_id: int
    role: str
    username: str
    full_name: str