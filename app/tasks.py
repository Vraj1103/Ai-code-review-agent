from celery import Celery
import logging
from app.config import settings
from app.github_utils import process_pr_files
from app.agent import analyze_code_with_openai

celery_app = Celery(
    "tasks",
    broker=settings.BROKER_URL,
    backend=settings.RESULT_BACKEND
)
celery_app.conf.update(
    task_reject_on_worker_lost=True,
    worker_shutdown_timeout=60,
    worker_max_tasks_per_child=100,
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instantiate the AI agent
# ai_agent = AIAgent(api_key=settings.OPENAI_API_KEY)


@celery_app.task
def analyze_pr_task(repo_url: str, pr_number: int, github_token: str):
    try:
        # Fetch the PR files from GitHub, we will get the list of files and their changes with their original content.
        pr_files = process_pr_files(repo_url, pr_number, github_token)
        logger.info(f"Processing PR files for {repo_url} - files {pr_files}")
        # Placeholder for AI analysis logic
        analysis_results = []
        for file in pr_files:
            # print("##file", file)
            try:
                file_analysis = analyze_code_with_openai(
                    filename=file["filename"],
                    content=file["content"],
                    patch=file["patch"],
                )
                analysis_results.append(
                    {
                        "name": file["filename"],
                        "issues": file_analysis.get("issues", [])
                    }
                )
            except Exception as ai_error:
                logger.error(f"AI analysis failed for {file['filename']}: {str(ai_error)}")
                analysis_results.append({
                    "name": file["filename"],
                    "issues": [{"type": "error", "description": f"AI analysis failed: {str(ai_error)}"}]
                })

        return {
            "repo_url": repo_url,
            "pr_number": pr_number,
            "analysis": analysis_results,
        }
    except Exception as e:
        raise Exception(f"Error analyzing PR: {str(e)}")
