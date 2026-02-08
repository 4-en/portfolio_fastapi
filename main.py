
from config import load_config

settings = load_config()

import sqlite3
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Response
from fastapi.responses import StreamingResponse
import markdown
import secrets
import os
import hashlib

app = FastAPI()
security = HTTPBasic()

templates = Jinja2Templates(directory="templates")
templates.env.globals["config"] = settings

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- DATABASE SETUP ---
DB_NAME = "blog.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        # posts table: id, title, content, date
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # pages (also markdown, but not as posts and separately manageable)
        # id, title, content, route, date, include_in_nav
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                route TEXT NOT NULL UNIQUE,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                include_in_nav BOOLEAN DEFAULT 0
            )
        """)

# Initialize DB on startup
init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn


def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_ok = secrets.compare_digest(credentials.username, settings.admin_user)
    
    # Hash the provided password with the stored salt
    sha_input = credentials.password + settings.admin_salt
    hashed_pass = "sha256$" + hashlib.sha256(sha_input.encode()).hexdigest()
    
    is_pass_ok = secrets.compare_digest(hashed_pass, settings.admin_pass)
    
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return True


def get_error_page(request: Request, code: int, message: str):
    return templates.TemplateResponse("error.html", {"request": request, "code": code, "message": message}, status_code=code)

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
        return templates.TemplateResponse("markdown.html", {"request": request, "content": content, "routes": top_level_routes})
    app.add_api_route(route, markdown_route, response_class=HTMLResponse)
    
    if route.count("/") == 1: # top level route like /about, not /docs/guide
        top_level_routes.append({
            "name": route.strip("/"),
            "url": route.lower()
        })
        
        
# --- Caching SETUP ---
# middleware for caching
MAX_STATIC_CACHE = 1000
MAX_STATIC_FILE_SIZE = 1024 * 1024 * 1  # 1 MB -> max total cache size is 1 GB, but usually much less
MAX_PAGE_CACHE = 1000

import cachetools
static_cache = cachetools.LRUCache(maxsize=MAX_STATIC_CACHE)
page_cache = cachetools.LRUCache(maxsize=MAX_PAGE_CACHE)
no_cache = cachetools.LRUCache(maxsize=MAX_STATIC_CACHE * 10) # separate cache to track non-cacheable items and avoid repeated processing

@app.middleware("http")
async def cache_middleware(request: Request, call_next):
    
    cache_key = request.url.path
    
    # 1. Filter non-cacheable requests
    if (request.method != "GET" or 
        request.url.path.startswith("/admin") or
        request.url.query or
        request.url.path.startswith("/api") or
        cache_key in no_cache):
        return await call_next(request)
    
    
    is_static_request = cache_key.startswith("/static/")
    active_cache = static_cache if is_static_request else page_cache

    # 2. Check Cache
    if cache_key in active_cache:
        cached_data = active_cache[cache_key]
        print(f"[CACHE] Serving {cache_key} from cache")
        return Response(
            content=cached_data["content"], 
            media_type=cached_data["media_type"],
            headers=cached_data["headers"]
        )
    
    # 3. Get fresh response
    response = await call_next(request)
    
    # check content length for static files, if too large, don't cache and add to no_cache to avoid repeated processing
    if is_static_request:
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_STATIC_FILE_SIZE:
            print(f"[CACHE] Not caching {cache_key} due to size {content_length} bytes")
            no_cache[cache_key] = True
            return response
    
    # Only cache successful 200 OK responses
    if response.status_code == 200:
        
        headers = dict(response.headers)
        
        # consume the body to store it
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
            if len(body) > MAX_STATIC_FILE_SIZE and is_static_request:
                # bail out of caching if we exceed size limit while reading
                print(f"[CACHE] Not caching {cache_key} due to size exceeding limit while reading")
                no_cache[cache_key] = True
                
                async def remaining_stream():
                    yield body
                    async for chunk in response.body_iterator:
                        yield chunk
                return StreamingResponse(remaining_stream(), media_type=response.media_type, headers=headers)
        
        # Check size limits for static files
        if is_static_request and len(body) > MAX_STATIC_FILE_SIZE:
            return Response(content=body, media_type=response.media_type, headers=headers)

        # Store in cache
        active_cache[cache_key] = {
            "content": body,
            "headers": headers,
            "media_type": response.media_type
        }
        
        # Return a new response because we exhausted the original iterator
        return Response(content=body, media_type=response.media_type, headers=headers)

    return response
    
    

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
    return templates.TemplateResponse("post.html", {"request": request, "post": post, "content": html_content, "routes": top_level_routes})

@app.get("/impressum", response_class=HTMLResponse)
async def impressum(request: Request):
    return templates.TemplateResponse("impressum.html", {"request": request, "routes": top_level_routes})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request, "routes": top_level_routes})
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
            
            # invalidate cache for this post
            cache_key = f"/post/{id}"
            if cache_key in page_cache:
                del page_cache[cache_key]
            
        else: # Create new
            conn.execute("INSERT INTO posts (title, content) VALUES (?, ?)", (title, content))
        conn.commit()
        
    if "/" in page_cache:
        del page_cache["/"]  # Invalidate homepage cache to show new/updated post
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

# 5. Delete Action
@app.post("/admin/delete/{post_id}")
async def delete_post(post_id: int, auth: bool = Depends(authenticate)):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,)).commit()
        
    # invalidate cache for this post
    cache_key = f"/post/{post_id}"
    if cache_key in page_cache:
        del page_cache[cache_key]
        
    if "/" in page_cache:
        del page_cache["/"]  # Invalidate homepage cache to remove deleted post
        
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


# middleware for latency simulation (for testing loading states in the UI)
# @app.middleware("http")
# async def add_latency(request: Request, call_next):
#     await asyncio.sleep(0.5) # Simulate 500ms latency
#     response = await call_next(request)
#     return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0", port=8000)