import requests
import logging
from urllib.parse import urlparse
import mimetypes

def parse_repo_url(repo_url: str):
    """
    Parse the repository URL to extract the owner and repo name.
    Example: https://github.com/owner/repo -> ("owner", "repo")
    """
    path_parts = urlparse(repo_url).path.strip("/").split("/")
    if len(path_parts) < 2:
        raise ValueError("Invalid repository URL. It should be in the format 'https://github.com/owner/repo'")
    logging.info(f"Parsed owner: {path_parts[0]}, repo: {path_parts[1]}")
    return path_parts[0], path_parts[1]

def fetch_pr_files(repo_url: str, pr_number: int, github_token: str):
    """
    Fetch the list of files and their changes for a given PR from GitHub.
    """
    baseUrl = "https://api.github.com/repos"
    owner, repo = parse_repo_url(repo_url)
    headers = {"Authorization": f"token {github_token}"}
    url = f"{baseUrl}/{owner}/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=headers)

    if response.status_code == 404:
        raise Exception(f"Repository or PR not found. Please check the URL and PR number: {url}")
    elif response.status_code == 403:
        raise Exception("Access forbidden. Check if the GitHub token has the required permissions.")
    elif response.status_code != 200:
        raise Exception(f"Failed to fetch PR files: {response.status_code}, {response.text}")

    return response.json()

def fetch_file_content(raw_url, github_token=None):
    """
    Fetches the raw content of a file from GitHub using the raw URL.
    Includes error handling for invalid URLs or failed responses.
    """
    if not raw_url:
        raise ValueError("The raw_url must be provided to fetch file content.")
    # print("raw_url_new", raw_url)
    headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    try:
        response = requests.get(raw_url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch file content from {raw_url}: {str(e)}")
    
    return response.text

def fetch_pr_diff(repo_url: str, pr_number: int, github_token: str):
    """
    Fetches the diff of a pull request from GitHub.
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}.diff"

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print("response", response.text)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch PR diff: {str(e)}")

    return response.text


def process_pr_files(repo_url:str, pr_number:int, github_token:str):
    """
    Processes the files in a PR by fetching their details and content,
    analyzing only code files, and skipping others.
    """
    if not repo_url or not pr_number or not github_token:
        raise ValueError("All details must be provided.")
    #Fetch the PR diff
    diff = fetch_pr_diff(repo_url, pr_number, github_token)

    files = fetch_pr_files(repo_url, pr_number, github_token)
    file_contents = []

    for file_info in files:
        filename = file_info.get("filename")
        if not filename:
            print("Skipping a file with no filename information.")
            continue

        if is_code_file(filename):
            raw_url = file_info.get("raw_url")
            print("raw_url", raw_url)
            if raw_url:
                try:
                    content = fetch_file_content(raw_url, github_token)
                    # print(content,"content")
                    file_patch = extract_patch_for_file(diff, filename)
                    print("file_patch", file_patch)
                    file_contents.append({
                        "filename": filename, 
                        "content": content,
                        "patch": file_patch
                    })
                except Exception as e:
                    print(f"Error fetching content for {filename}: {str(e)}")
            else:
                print(f"Skipping file {filename} due to missing raw_url.")
        else:
            print(f"Skipping non-code file: {filename}")

    return file_contents


# utlity functions
def is_code_file(filename: str):
    """
    Determines if a file is a code file based on its extension or MIME type.
    """
    code_extensions = [
        '.py', '.js', '.java', '.go', '.cpp', '.c', '.cs', '.rb', '.php',
        '.html', '.css', '.ts', '.rs', '.kt', '.swift', '.json', '.xml', '.yml', '.yaml'
    ]
    # Guess MIME type
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        # Allow text-based files like JSON, XML, YAML, and plain text
        if mime_type.startswith("text/") or mime_type in ["application/json", "application/xml"]:
            return True

    # Fallback to extension-based validation
    return any(filename.endswith(ext) for ext in code_extensions)

def extract_patch_for_file(diff: str, filename: str):
    """
    Extracts the patch for a specific file from the full PR diff.
    Includes all metadata such as diff headers, index, and @@ lines.
    """
    file_patch = []
    lines = diff.splitlines()
    recording = False
    filename_pattern = f"a/{filename}"  # Match the file in the diff header

    for line in lines:
        # Start recording when the diff for the specified file begins
        if line.startswith("diff --git") and filename_pattern in line:
            recording = True
            file_patch.append(line)
        # Stop recording when the diff for another file begins
        elif recording and line.startswith("diff --git"):
            break
        # Record lines if we are within the patch for the specified file
        elif recording:
            file_patch.append(line)

    return "\n".join(file_patch) if file_patch else None
