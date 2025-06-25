from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json, os
import logging

# ----------------------------- Logging initialization -----------------------------

logging.basicConfig(
    filename="tracker.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s -%(message)s"
)
logger = logging.getLogger(__name__)

# ----------------------------- FastAPI Initialization -----------------------------
app = FastAPI(
    title="Project-Based Issue Tracker",                      
    description="Track issues per project with nested structure",  
    version="1.0.0"                                  
)

# ----------------------------- Pydantic Models -----------------------------

class Issue(BaseModel):
    id: int                       
    project_id: str               
    title: str                    
    description: str              
    priority: str                 
    status: str                   


class Project(BaseModel):
    project_id: str               
    name: str                     
    status: str                   
    issues: list[Issue] = []     

ISSUE_FILE = "issues.json"       
# --------------------------- Helper Methods ---------------------------
def load_data():
    """
    Load data from the JSON file. If file not found or corrupted, return empty list.
    """
    try:
        if not os.path.exists(ISSUE_FILE):
            return []
        with open(ISSUE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error("Error occurred while loading issues")
        return []

def save_data(projects):
    """
    Save the list of projects (including issues) to the JSON file.
    """
    with open(ISSUE_FILE, "w") as f:
        json.dump(projects, f, indent=2)

# ----------------------------- Routes -----------------------------

# Root endpoint to verify API is up
@app.get("/")
async def root():
    return {"message": "Issue Tracker API is running."}

# ----------------------------- Project APIs -----------------------------

@app.post("/projects")
async def create_project(project: Project):
    """
    Create a new project. Project ID must be unique.
    """
    projects = load_data() 

    # Check if a project with the same project_id already exists

    if any(p["project_id"] == project.project_id for p in projects):
        logger.error(f"Project with ID {project.project_id} already exists")  
        raise HTTPException(status_code=400, detail="Project ID already exists") 

    # If the project ID is unique, add the new project and save the updated list

    projects.append(project.dict()) 
    save_data(projects)              

    logger.info(f"Project created: {project.project_id}")  
    return {"message": "Project created"}  


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """
    Retrieve a single project by ID.
    """
    projects = load_data()  

    # Search for the project with the given project_id
    for p in projects:
        if p["project_id"] == project_id:
            return p 

    # Log and raise error if project is not found
    logger.error(f"Project not found: {project_id}")
    raise HTTPException(status_code=404, detail="Project not found")

@app.get("/projects")
async def get_all_projects():
    """
    Retrieve and return all projects.
    """
    projects = load_data()

    if not projects:
        logger.warning("No projects found")
        return {"total_projects": 0, "projects": []}

    logger.info(f"Fetched {len(projects)} projects")
    return {"total_projects": len(projects), "projects": projects}


# ----------------------------- Issue APIs -----------------------------

@app.post("/add-issue")
async def add_issue(issue: Issue):
    """
    Add a new issue to a specific project. Auto-creates project if not found.
    """
    projects = load_data()
    project_found = False

    for project in projects:
        if project["project_id"] == issue.project_id:
            project_found = True
            # Check if issue ID already exists within this project

            for existing_issue in project["issues"]:
                if existing_issue["id"] == issue.id:
                    logger.error(f"Issue ID {issue.id} already exists in Project {issue.project_id}")
                    raise HTTPException(status_code=400, detail="Issue ID already exists in the project")
                
            # Add the issue to the project
            project["issues"].append(issue.dict())
            logger.info(f"Issue ID {issue.id} added to project {issue.project_id}")
            break

    if not project_found:

        # Auto-create a new project with the issue
        new_project = {
            "project_id": issue.project_id,
            "name": f"Auto-created project {issue.project_id}",
            "status": "Active",
            "issues": [issue.dict()]
        }
        projects.append(new_project)
        logger.info(f"Auto-created project {issue.project_id} and added issue ID {issue.id}")

    save_data(projects)
    return {"status_code": 200, "message": f"Issue added to project {issue.project_id}"}

from fastapi import Request

@app.post("/get-all-issues")
async def get_all_issues(request: Request):
    """
    Retrieve issues by status_type 
    """
    body = await request.json()
    status_type = body.get("status_type", None)
    projects = load_data()
    result = {}

    for project in projects:
        filtered_issues = []  

        for issue in project.get("issues", []):
            if not status_type or issue["status"].lower() == status_type.lower():
                filtered_issues.append({
                    "title": issue["title"],
                    "description": issue["description"]
                })

        if filtered_issues:
            result[project["name"]] = [{
                "count": len(filtered_issues),
                "issues": filtered_issues
            }]

    logger.info(f"Issues filtered by status: {status_type or 'All'}")
    return result

@app.get("/projects/{project_id}/issues")
def get_issues_by_project(project_id: str):
    """
    Retrieve all issues for a specific project.
    """
    projects = load_data()

    for project in projects:
        if project["project_id"] == project_id:
            logger.info(f"Issues fetched for project: {project_id}")
            return {
                "project_id": project_id,
                "total_issues": len(project["issues"]),
                "issues": project["issues"]
            }

    logger.error(f"Project not found: {project_id}")
    raise HTTPException(status_code=404, detail="Project not found")


from fastapi import Request

@app.put("/update-issue-status")
async def update_issue_status(request: Request):
    """
    Update the status of a specific issue in a project.
    Expects JSON body with: project_id, issue_id, status
    """
    data = await request.json()
    project_id = data.get("project_id")
    issue_id = data.get("issue_id")
    new_status = data.get("status")

    # Validate presence of required fields
    if not all([project_id, issue_id, new_status]):
        raise HTTPException(status_code=400, detail="project_id, issue_id, and status are required")

    projects = load_data()

    for project in projects:
        if project["project_id"] == project_id:
            for issue in project["issues"]:
                if issue["id"] == issue_id:
                    issue["status"] = new_status
                    save_data(projects)
                    logger.info(f"Issue {issue_id} in project {project_id} updated to status '{new_status}'")
                    return {"detail": "Status updated successfully"}

            logger.error(f"Issue not found: {issue_id} in project {project_id}")
            raise HTTPException(status_code=404, detail="Issue not found")

    logger.error(f"Project not found: {project_id}")
    raise HTTPException(status_code=404, detail="Project not found")
from fastapi import Request

@app.delete("/delete-issue")
async def delete_issue(request: Request):
    """
    Delete an issue from a project using project_id and issue_id.
    """
    data = await request.json()
    project_id = data.get("project_id")
    issue_id = data.get("issue_id")

    # Validate input
    if not all([project_id, issue_id]):
        raise HTTPException(status_code=400, detail="project_id and issue_id are required")

    projects = load_data()
    project_found = False
    issue_found = False

    for project in projects:
        if project["project_id"] == project_id:
            project_found = True
            for issue in project["issues"]:
                if issue["id"] == issue_id:
                    issue_found = True
                    project["issues"].remove(issue)
                    save_data(projects)
                    logger.info(f"Issue {issue_id} deleted from project {project_id}")
                    return {"status_code":200,"detail": "Issue deleted successfully"}

    if not project_found:
        logger.error(f"Project not found: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")

    if not issue_found:
        logger.error(f"Issue ID {issue_id} not found in project {project_id}")
        raise HTTPException(status_code=404, detail="Issue not found")

