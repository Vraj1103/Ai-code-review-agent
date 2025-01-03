import os
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from app.tasks import analyze_pr_task
from app.agent import analyze_code_with_openai
from celery.result import AsyncResult
from app.github_utils import process_pr_files
from app.github_utils import process_pr_files
import hmac
import hashlib
import logging
from app.config import settings

app = FastAPI()

class AnalyzePRRequest(BaseModel):
    repo_url: str
    pr_number: int
    github_token: str

WEBHOOK_SECRET = settings.WEBHOOK_SECRET
GITHUB_TOKEN = settings.GITHUB_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.get("/")
def root():
    return {"message": "Welcome to the AI Code Review system"}

@app.post("/analyze-pr")
async def analyze_pr(request: AnalyzePRRequest):
    if not request.github_token:
        try:
            request.github_token = GITHUB_TOKEN
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

@app.post("/webhook")
async def github_webhook(request: Request):
    """
    Handles incoming GitHub webhook events for pull requests.
    """
    try:
        # Verify the webhook signature
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_signature(await request.body(), signature, WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Invalid signature")

        # Parse the event type
        event = request.headers.get("X-GitHub-Event")
        if event != "pull_request":
            return {"message": "Event not handled"}

        payload = await request.json()
        action = payload.get("action")
        logger.info(f"Received pull_request event: {action}")

        # Handle PR actions (e.g., opened, reopened, or synchronized)
        if action in ["opened", "synchronize", "reopened"]:
            repo_url = payload["repository"]["html_url"]
            pr_number = payload["number"]

            # Trigger Celery task
            analyze_pr_task.delay(repo_url, pr_number, GITHUB_TOKEN)
            return {"message": f"PR analysis triggered for PR #{pr_number} in {repo_url}"}

        return {"message": f"No action taken for PR action: {action}"}

    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verifies the HMAC signature of the webhook payload.
    """
    if not signature:
        return False

    # Compute HMAC SHA-256 signature
    computed_signature = "sha256=" + hmac.new(
        key=secret.encode(), msg=payload, digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_signature, signature)
