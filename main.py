
from config import load_config

settings = load_config()

import sqlite3
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import markdown
import secrets
import os

app = FastAPI()
security = HTTPBasic()

templates = Jinja2Templates(directory="templates")
templates.env.globals["config"] = settings

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- DATABASE SETUP ---
DB_NAME = "blog.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

# Initialize DB on startup
init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

# --- AUTH ---
ADMIN_USER = "admin"
ADMIN_PASS = "raspberry" 

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_ok = secrets.compare_digest(credentials.username, settings.admin_user)
    is_pass_ok = secrets.compare_digest(credentials.password, settings.admin_pass)
    
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return True

# load markdown files from static/markdown and create routes for them
blacklist_routes = ["/", "/post", "/admin"] 
markdown_dir = "static/markdown"
intro_content = ""
markdown_files = []
# load markdown files and routes recursively
for root, dirs, files in os.walk(markdown_dir):
    for file in files:
        if file.endswith(".md"):
            filepath = os.path.join(root, file)
            route_path = "/" + os.path.relpath(filepath, markdown_dir).replace("\\", "/").replace(".md", "")
            with open(filepath, "r", encoding="utf-8") as f:
                md_content = f.read()
                html_content = markdown.markdown(md_content)
                if route_path == "/index":
                    intro_content = html_content
                else:
                    markdown_files.append((route_path, html_content))
                    
top_level_routes = []
for route, content in markdown_files:
    
    if route in blacklist_routes:
        print(f"[!] Route '{route}' is blacklisted and will not be created for {filepath}.")
        continue
    
    async def markdown_route(request: Request, content=content):
        return templates.TemplateResponse("markdown.html", {"request": request, "content": content})
    app.add_api_route(route, markdown_route, response_class=HTMLResponse)
    
    if route.count("/") == 1: # top level route like /about, not /docs/guide
        top_level_routes.append(route)

# --- PUBLIC ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    with get_db_connection() as conn:
        posts = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return templates.TemplateResponse("index.html", {"request": request, "posts": posts, "intro_content": intro_content, "routes": top_level_routes})

@app.get("/post/{post_id}", response_class=HTMLResponse)
async def read_post(request: Request, post_id: int):
    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    html_content = markdown.markdown(post["content"])
    return templates.TemplateResponse("post.html", {"request": request, "post": post, "content": html_content})

@app.get("/impressum", response_class=HTMLResponse)
async def impressum(request: Request):
    return templates.TemplateResponse("impressum.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

# --- ADMIN ROUTES ---

# 1. Dashboard (List all posts)
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, auth: bool = Depends(authenticate)):
    with get_db_connection() as conn:
        posts = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "posts": posts})

# 2. Editor (New Post)
@app.get("/admin/new", response_class=HTMLResponse)
async def new_post_form(request: Request, auth: bool = Depends(authenticate)):
    return templates.TemplateResponse("admin_editor.html", {"request": request, "post": None})

# 3. Editor (Edit Existing)
@app.get("/admin/edit/{post_id}", response_class=HTMLResponse)
async def edit_post_form(request: Request, post_id: int, auth: bool = Depends(authenticate)):
    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return templates.TemplateResponse("admin_editor.html", {"request": request, "post": post})

# 4. Save Action (Handle both Create and Update)
@app.post("/admin/save")
async def save_post(
    request: Request,
    id: str = Form(""), # Optional ID
    title: str = Form(...), 
    content: str = Form(...), 
    auth: bool = Depends(authenticate)
):
    with get_db_connection() as conn:
        if id: # Update existing
            conn.execute("UPDATE posts SET title = ?, content = ? WHERE id = ?", (title, content, id))
        else: # Create new
            conn.execute("INSERT INTO posts (title, content) VALUES (?, ?)", (title, content))
        conn.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

# 5. Delete Action
@app.post("/admin/delete/{post_id}")
async def delete_post(post_id: int, auth: bool = Depends(authenticate)):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,)).commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0", port=8000)