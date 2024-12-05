import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.tasks import analyze_pr_task
from celery.result import AsyncResult

app = FastAPI()

class AnalyzePRRequest(BaseModel):
    repo_url: str
    pr_number: int
    github_token: str


@app.get("/")
def root():
    return {"message": "Welcome to the AI Code Review system"}

@app.post("/analyze-pr")
async def analyze_pr(request: AnalyzePRRequest):
    if not request.github_token:
        try:
            request.github_token = os.environ["GITHUB_TOKEN"]
        except KeyError:
            raise HTTPException(status_code=400, detail="GitHub token is missing in the request")
    if not request.github_token or not request.repo_url:
        raise HTTPException(status_code=400, detail="Information missing in the request")
    task = analyze_pr_task.delay(request.repo_url, request.pr_number, request.github_token)
    return {"task_id": task.id, "status": task.status}


@app.get("/status/{task_id}")
async def check_status(task_id: str):
    task = AsyncResult(task_id)
    return {"task_id": task_id, "status": task.status}

@app.get("/results/{task_id}")
async def get_results(task_id: str):
    task = AsyncResult(task_id)
    if task.status == "SUCCESS":
        return {"task_id": task_id, "result": task.result}
    elif task.status == "FAILURE":
        return {"task_id": task_id, "error": str(task.result)}
    else:
        return {"task_id": task_id, "status": task.status}
