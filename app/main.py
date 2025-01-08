from typing import Annotated, List
from fastapi import FastAPI, Request, Depends, HTTPException, Query, APIRouter
from sqlmodel import Session, select
from sqlalchemy import Date
from fastapi.responses import JSONResponse
from datetime import datetime, date
from database import *
from models import *
import jwt

app = FastAPI()
router = APIRouter(prefix="/api/v1")

SessionDep = Annotated[Session, Depends(get_session)]

@app.on_event("startup")
async def on_startup():
    await init_db()
    logger.info("App started and database initialized.")
    
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
async def create_task(task: TasksCreate, session: SessionDep, request: Request):
    try:
        task_mock = Tasks(**task.dict())
        task_mock.created_by = request.state.user.user_id
        task_data = Tasks.model_validate(task_mock)
        if not task_data:
            logger.error("Failed to validate task data")
            return {"status": "error", "message": "Failed to validate task data"}

        session.add(task_data)
        await session.commit()
        await session.refresh(task_data)

        logger.info(f"Task created successfully: {task_data.title} by user {request.state.user.user_id}")
        return {"status": "success", "message": "Task created successfully", "task": task_data}
    except Exception as e:
        logger.error(f"Error creating task: {str(e)} \nStack trace: {e.__traceback__}", exc_info=True)
        return {"status": "error", "message": f"Failed to create task: {str(e)}"}

@router.get("/tasks/", response_model=list[TasksPublic])
async def read_tasks(
    session: SessionDep,
    project_id: List[int] = Query(None),
    title: str | None = None,
    phase: str | None = None,
    status: str | None = None,
    start_date: date | None = None,
    due_date: date | None = None,
    today: bool = False,
    offset: int = 0,
    limit: Annotated[int | None, Query(le=100)] = None,
    ):
    try:
        query = select(Tasks).filter(Tasks.deleted_at.is_(None))
        if project_id:
            query = query.filter(Tasks.project_id.in_(project_id))
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
            if start_date and due_date:
                query = query.filter(
                    (Tasks.start_date <= due_date) & (Tasks.due_date >= start_date)
                )
            if start_date:
                query = query.filter(Tasks.start_date <= start_date)
            if due_date:
                query = query.filter(Tasks.due_date >= due_date)

        if limit is not None:
            query = query.offset(offset).limit(limit)
        else:
            query = query.offset(offset)

        result = await session.execute(query)
        tasks = result.scalars().all()
        return tasks
    except Exception as e:
        logger.error(f"Error occurred while fetching tasks: {str(e)} \nStack trace: {e.__traceback__}", exc_info=True)
        return {"status": "error", "message": f"An error occurred: {str(e)}"}

@router.get("/tasks/{task_id}", response_model=TasksPublic)
async def read_task(task_id: int, session: SessionDep):
    try:
        task_data = await session.get(Tasks, task_id)
        if not task_data:
            logger.warning(f"Task with task id {task_id} not found")
            raise HTTPException(status_code=404, detail="Task not found.")
        return task_data
    except HTTPException as e:
        raise e 
    except Exception as e:
        logger.error(f"Error occurred while fetching task with task id {task_id}: {str(e)} \nStack trace: {e.__traceback__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.patch("/tasks/{task_id}", response_model=TasksPublic)
async def update_tasks(task_id: int, task: TasksUpdate, session: SessionDep):
    try:
        task_data = await session.get(Tasks, task_id)
        if not task_data:
            logger.warning(f"Task with task id {task_id} not found")
            raise HTTPException(status_code=404, detail="Task not found.")
        task_update = task.model_dump(exclude_unset=True)
        task_update["updated_at"] = datetime.utcnow()
        task_data.sqlmodel_update(task_update)
        session.add(task_data)
        await session.commit()
        await session.refresh(task_data)

        logger.info(f"Task updated successfully: {task_data.task_id} {task_data.title}")
        return task_data
    except HTTPException as e:
        raise e 
    except Exception as e:
        logger.error(f"Error occurred while updating task with task id {task_id}: {str(e)} \nStack trace: {e.__traceback__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/tasks/{task_id}")
async def delete_tasks(task_id: int, session: SessionDep):
    try:
        task_data = await session.get(Tasks, task_id)
        if not task_data:
            logger.warning(f"Task with task_id={task_id} not found")
            raise HTTPException(status_code=404, detail="Task not found.")
        task_data.deleted_at = datetime.utcnow()
        session.add(task_data)
        await session.commit()
        await session.refresh(task_data)

        logger.info(f"Task deleted successfully: {task_data.task_id} {task_data.title}")
        return {"status": "success", "message": "Task deleted successfully."}
    except HTTPException as e:
        raise e 
    except Exception as e:
        logger.error(f"Error occurred while deleting task with task id {task_id}: {str(e)} \nStack trace: {e.__traceback__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Assignments Modules
@router.post("/assignments/")
async def create_assignment(assign: AssignmentsCreate, session: SessionDep, request: Request):
    try:
        existing_assignment = await session.execute(
            select(Assignments).filter(
                Assignments.task_id == assign.task_id,
                Assignments.user_id == assign.user_id,
            )
        )
        if existing_assignment.scalar():
            logger.warning(f"User {assign.user_id} is already assigned to task {assign.task_id}")
            raise HTTPException(status_code=400, detail="This user is already assigned to this task.")

        assign_mock = Assignments(**assign.dict())
        assign_mock.assigned_by = request.state.user.user_id
        assign_data = Assignments.model_validate(assign_mock)
        session.add(assign_data)
        await session.commit()
        await session.refresh(assign_data)

        logger.info(f"Assignment created successfully for task id {assign_data.task_id} and user id {assign.user_id}")
        return {"status": "success", "message": "Assignment created successfully", "asssignment": assign_data}
    except Exception as e:
        logger.error(f"Error occurred while creating assignment for task id {assign.task_id} and user id: {assign.user_id}: {str(e)}\nStack trace: {e.__traceback__}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

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
    limit: Annotated[int | None, Query(le=100)] = None,
    ):
    try:
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

        if limit is not None:
            query = query.offset(offset).limit(limit)
        else:
            query = query.offset(offset)
        result = await session.execute(query)
        tasks = result.scalars().all()
        return tasks
    except Exception as e:
        logger.error(f"Error occurred while reading assignments: {str(e)}\nStack trace: {e.__traceback__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")        

@router.get("/assignments/{assigned_id}", response_model=AssignmentsPublic)
async def read_assignment(assigned_id: int, session: SessionDep):
    try:
        assign_data = await session.get(Assignments, assigned_id)
        if not assign_data:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        
        return assign_data
    except HTTPException as e:
        raise e 
    except Exception as e:
        logger.error(f"Error occurred while reading assignment with assigned id {assigned_id}: {str(e)}\nStack trace: {e.__traceback__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/assignments/{assigned_id}")
async def delete_assignment(assigned_id: int, session: SessionDep):
    try:
        assign_data = await session.get(Assignments, assigned_id)
        if not assign_data:
            logger.warning(f"Assignment with assigned id {assigned_id} not found.")
            raise HTTPException(status_code=404, detail="Assignment not found")
        session.delete(assign_data)
        await session.commit()

        logger.info(f"Assignment with assigned id {assigned_id} deleted successfully.")
        return {"status": "success", "message": "Assignment deleted successfully"}
    except HTTPException as e:
        raise e 
    except Exception as e:
        logger.error(f"Error occurred while deleting assignment with assigned_id={assigned_id}: {str(e)}\nStack trace: {e.__traceback__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

app.include_router(router)

@app.get("/")
async def root():
    api_routes = []
    for route in app.routes:
        if hasattr(route, "path") and route.path.startswith("/api/v1"):
            methods = ",".join(route.methods)
            api_routes.append(f"{methods} {route.path}")
    return JSONResponse(content={"api_routes": api_routes})