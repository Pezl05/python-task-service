from typing import Annotated
from fastapi import FastAPI, Request, Depends, HTTPException, Query, APIRouter
from sqlmodel import Session, select
from sqlalchemy import cast, Date
from fastapi.responses import JSONResponse
from datetime import datetime, date
from database import *
from models import *
import jwt

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
router = APIRouter(prefix="/api/v1")

SessionDep = Annotated[Session, Depends(get_session)]

@app.on_event("startup")
async def on_startup():
    await init_db()
    print("App started and database initialized.")
    
# Middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/assignments"):
        user = getattr(request.state, "user", None)
        if user is None or user.role != "admin":
            if request.method not in ["GET"]:
                return JSONResponse(status_code=403, content={"error": "Forbidden: Only GET allowed for non-admin users"})
    
    response = await call_next(request)
    return response

@app.middleware("http")
async def jwt_auth(request: Request, call_next):
    jwt_token = request.cookies.get("jwt")
    if jwt_token:
        try:
            payload = jwt.decode(jwt_token, JWT_KEY, algorithms=["HS256"])
            request.state.user = Jwt_Auth.parse_obj(payload)
        except jwt.ExpiredSignatureError:
            logger.error("JWT token has expired")
            return JSONResponse(status_code=401, content={"error": "JWT token has expired"})
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    else:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    response = await call_next(request)
    return response

# Tasks Modules
@router.post("/tasks/")
async def create_task(task: TasksCreate, session: SessionDep):
    task_data = Tasks.model_validate(task)
    session.add(task_data)
    await session.commit()
    await session.refresh(task_data)
    return {"status": "success", "message": "Task created successfully", "task": task_data}

@router.get("/tasks/", response_model=list[TasksPublic])
async def read_tasks(
    session: SessionDep,
    project_id: int | None = None,
    title: str | None = None,
    phase: str | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    today: bool = False,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    query = select(Tasks).filter(Tasks.deleted_at.is_(None))
    if project_id:
        query = query.filter(Tasks.project_id == project_id)
    if title:
        query = query.filter(Tasks.title.ilike(f"%{title}%"))
    if phase:
        query = query.filter(Tasks.phase.ilike(f"{phase}"))
    if status:
        query = query.filter(Tasks.status.ilike(f"{status}"))
    if today:
        today_date = date.today()
        query = query.filter(Tasks.start_date <= today_date)
        query = query.filter(Tasks.due_date >= today_date)
    else:
        if start_date:
            query = query.filter(Tasks.start_date >= start_date)
        if end_date:
            query = query.filter(Tasks.due_date <= end_date)
    result = await session.execute(query.offset(offset).limit(limit))
    tasks = result.scalars().all()
    return tasks

@router.get("/tasks/{task_id}", response_model=TasksPublic)
async def read_task(task_id: int, session: SessionDep):
    task_data = await session.get(Tasks, task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task_data

@router.patch("/tasks/{task_id}", response_model=TasksPublic)
async def update_tasks(task_id: int, task: TasksUpdate, session: SessionDep):
    task_data = await session.get(Tasks, task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found.")
    task_update = task.model_dump(exclude_unset=True)
    task_data.sqlmodel_update(task_update)
    session.add(task_data)
    await session.commit()
    await session.refresh(task_data)
    return task_data

@router.delete("/tasks/{task_id}")
async def delete_tasks(task_id: int, session: SessionDep):
    task_data = await session.get(Tasks, task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found.")
    task_data.deleted_at = datetime.utcnow()
    session.add(task_data)
    await session.commit()
    await session.refresh(task_data)
    return {"status": "success", "message": "Task deleted successfully."}

# Assignments Modules

@router.post("/assignments/")
async def create_assignment(assign: AssignmentsCreate, session: SessionDep):
    existing_assignment = await session.execute(
        select(Assignments).filter(
            Assignments.task_id == assign.task_id,
            Assignments.user_id == assign.user_id,
        )
    )
    if existing_assignment.scalar():
        raise HTTPException(status_code=400, detail="This user is already assigned to this task.")

    assign_data = Assignments.model_validate(assign)
    session.add(assign_data)
    await session.commit()
    await session.refresh(assign_data)
    return {"status": "success", "message": "Assignment created successfully", "asssignment": assign_data}

@router.get("/assignments/", response_model=list[AssignmentsPublic])
async def read_assignments(
    session: SessionDep,
    task_id: int | None = None,
    user_id: int | None = None,
    assigned_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    today: bool = False,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    query = select(Assignments)
    if task_id:
        query = query.filter(Assignments.task_id == task_id)
    if user_id:
        query = query.filter(Assignments.user_id == user_id)
    if assigned_id:
        query = query.filter(Assignments.assigned_id == assigned_id)
    if today:
        today_date = date.today()
        logger.error(today_date)
        query = query.filter(Assignments.assigned_at.cast(Date) == today_date)
    else:
        if start_date:
            query = query.filter(Assignments.assigned_at >= start_date)
        if end_date:
            query = query.filter(Assignments.assigned_at <= end_date)
    result = await session.execute(query.offset(offset).limit(limit))
    tasks = result.scalars().all()
    return tasks

@router.get("/assignments/{assigned_id}", response_model=TasksPublic)
async def read_assignment(assigned_id: int, session: SessionDep):
    assign_data = await session.get(Assignments, assigned_id)
    if not assign_data:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return assign_data

@router.delete("/assignments/{assigned_id}")
async def delete_assignment(assigned_id: int, session: SessionDep):
    assign_data = await session.get(Assignments, assigned_id)
    if not assign_data:
        raise HTTPException(status_code=404, detail="Assignment not found")
    session.delete(assign_data)
    await session.commit()
    return {"status": "success", "message": "Assignment deleted successfully"}

app.include_router(router)

@app.get("/")
async def root():
    api_routes = []
    for route in app.routes:
        if hasattr(route, "path") and route.path.startswith("/api/v1"):
            methods = ",".join(route.methods)
            api_routes.append(f"{methods} {route.path}")
    return JSONResponse(content={"api_routes": api_routes})