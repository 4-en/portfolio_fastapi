from config import load_config
import sqlite3
import secrets
import os
import hashlib

from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
import markdown
import cachetools

# --- CONFIGURATION ---
settings = load_config()

# Ensure we have a secret key for sessions. 
# In production, this should be in your config file.
SECRET_KEY = getattr(settings, "secret_key", secrets.token_hex(32))

app = FastAPI(
    title=settings.site_name,
    description=settings.site_description,
    version="1.0.0",
    contact={
        "name": settings.author_name,
        "email": settings.legal_email,
    },
    license_info={
        "name": f"Copyright {settings.copyright_year} {settings.author_name}",
    },
    docs_url=None,  # Disable default docs
    redoc_url=None,
    openapi_url=None
)

# Add Session Middleware (Enables request.session)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory="templates")
templates.env.globals["config"] = settings

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- THEME SETUP ---
DEFAULT_THEME = "retro-console"
theme_path = os.path.join("static", "css", "themes", f"{settings.theme}.css")
if not os.path.exists(theme_path):
    print(f"[!] Theme '{settings.theme}' not found, falling back to default theme '{DEFAULT_THEME}'.")
    settings.theme = DEFAULT_THEME

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
        page = conn.execute("SELECT * FROM pages WHERE id = 0").fetchone()
        if not page:
            conn.execute("INSERT INTO pages (id, title, content, route, include_in_nav) VALUES (0, 'Intro', '', '/index', 0)")
        conn.commit()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- AUTHENTICATION LOGIC ---

class NotAuthenticatedException(Exception):
    pass

def check_admin_session(request: Request):
    """Dependency to check if user is logged in via session."""
    user = request.session.get("user")
    if not user or user != settings.admin_user:
        raise NotAuthenticatedException()
    return user

@app.exception_handler(NotAuthenticatedException)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    """Redirects unauthenticated users to the login page."""
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

def verify_password(plain_password, stored_hash, salt):
    """Helper to verify password against the stored config."""
    sha_input = plain_password + salt
    hashed_pass = "sha256$" + hashlib.sha256(sha_input.encode()).hexdigest()
    return secrets.compare_digest(hashed_pass, stored_hash)


# --- ERROR HANDLERS ---
def get_error_page(request: Request, code: int, message: str):
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "code": code, "message": message, "routes": top_level_routes}, 
        status_code=code
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return get_error_page(request, exc.status_code, exc.detail)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return get_error_page(request, 422, "Invalid input data provided.")

@app.exception_handler(Exception)
async def universal_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error: {exc}") 
    return get_error_page(request, 500, "Internal Server Error")


# --- STATIC PAGE LOADING (Existing logic) ---
RESERVED_ROUTES = ["/post", "/admin", "/login", "/logout", "/impressum", "/privacy"]
PAGES_DIR = "static/pages"
PAGES_FILETYPES = [".md", ".html", ".txt"]
intro_content = ""
pages_files = {}
top_level_routes = []

def create_pages_route(content, template):
    if template:
        async def template_route(request: Request):
            return templates.TemplateResponse("markdown.html", {"request": request, "content": content, "routes": top_level_routes, "theme": settings.theme})
        return template_route
    else:
        async def full_html_route(_: Request):
            return Response(content=content, media_type="text/html")
        return full_html_route

for root, dirs, files in os.walk(PAGES_DIR):
    for file in files:
        
        # check if in correct filetypes
        filetype = os.path.splitext(file)[1]
        if not filetype:
            # print(f"[!] Skipping file with no extension: {file}")
            continue
        filetype = filetype.lower()
        if filetype not in PAGES_FILETYPES:
            print(f"[!] Skipping unsupported file type: {file}")
            continue
        

        
        template = True
        content = ""
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(full_path, PAGES_DIR)
        route_path = "/" + rel_path.replace("\\", "/").replace(filetype, "")
        
        # TODO: add a better check. Too many false positives with this one. 
        if any([route_path.startswith(reserved) for reserved in RESERVED_ROUTES]):
            print(f"[!] Skipping file '{file}' because its route '{route_path}' conflicts with reserved routes.")
            continue
        
        if route_path in pages_files:
            print(f"[!] Skipping file '{file}' because its route '{route_path}' conflicts with an existing page.")
            continue
        
        match filetype:
            case ".md":
                with open(full_path, "r", encoding="utf-8") as f:
                    md_content = f.read()
                    content = markdown.markdown(md_content)
            case ".html":
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                template = "<body>" not in content.lower()  # If it has a body tag, serve as-is
            case ".txt":
                with open(full_path, "r", encoding="utf-8") as f:
                    content = "<pre>" + f.read() + "</pre>"
            case _:
                print(f"[!] Skipping unsupported file type: {file}")
                continue
        
        
    
        if route_path == "/index":
            if not template:
                print(f"[!] Skipping 'index' page because full HTML files cannot be used for the intro content.")
                continue
            intro_content = content
        else:
            pages_files[route_path] = True
            app.add_api_route(route_path, create_pages_route(content, template), methods=["GET"])
            
            if settings.show_routes_in_nav and route_path.count("/") == 1:
                top_level_routes.append({"name": route_path.strip("/"), "url": route_path.lower()})



# --- CACHING SETUP (Existing Logic) ---
MAX_STATIC_CACHE = 1000
MAX_STATIC_FILE_SIZE = 1024 * 1024 * 1 
MAX_PAGE_CACHE = 1000
static_cache = cachetools.LRUCache(maxsize=MAX_STATIC_CACHE)
page_cache = cachetools.LRUCache(maxsize=MAX_PAGE_CACHE)
no_cache = cachetools.LRUCache(maxsize=MAX_STATIC_CACHE * 10)

@app.middleware("http")
async def cache_middleware(request: Request, call_next):
    cache_key = request.url.path
    if (request.method != "GET" or 
        request.url.path.startswith("/admin") or
        request.url.path.startswith("/login") or # Don't cache login
        request.url.path.startswith("/logout") or # Don't cache logout
        request.url.query or
        request.url.path.startswith("/api") or
        cache_key in no_cache):
        return await call_next(request)
    
    is_static_request = cache_key.startswith("/static/")
    active_cache = static_cache if is_static_request else page_cache

    if cache_key in active_cache:
        cached_data = active_cache[cache_key]
        return Response(content=cached_data["content"], media_type=cached_data["media_type"], headers=cached_data["headers"])
    
    response = await call_next(request)
    
    if is_static_request and response.status_code == 200:
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_STATIC_FILE_SIZE:
            no_cache[cache_key] = True
            return response
    
    if response.status_code == 200:
        headers = dict(response.headers)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
            if len(body) > MAX_STATIC_FILE_SIZE and is_static_request:
                no_cache[cache_key] = True
                async def remaining_stream():
                    yield body
                    async for chunk in response.body_iterator:
                        yield chunk
                return StreamingResponse(remaining_stream(), media_type=response.media_type, headers=headers)
        
        if is_static_request and len(body) > MAX_STATIC_FILE_SIZE:
            return Response(content=body, media_type=response.media_type, headers=headers)

        active_cache[cache_key] = {"content": body, "headers": headers, "media_type": response.media_type}
        return Response(content=body, media_type=response.media_type, headers=headers)

    return response


# --- PUBLIC ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    with get_db_connection() as conn:
        posts = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return templates.TemplateResponse("index.html", {"request": request, "posts": posts, "intro_content": intro_content, "routes": top_level_routes, "theme": settings.theme})

@app.get("/post/{post_id}", response_class=HTMLResponse)
async def read_post(request: Request, post_id: int):
    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    html_content = markdown.markdown(post["content"])
    return templates.TemplateResponse("post.html", {"request": request, "post": post, "content": html_content, "routes": top_level_routes, "theme": settings.theme})

@app.get("/impressum", response_class=HTMLResponse)
async def impressum(request: Request):
    return templates.TemplateResponse("impressum.html", {"request": request, "routes": top_level_routes, "theme": settings.theme})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request, "routes": top_level_routes, "theme": settings.theme})

@app.get("/fastblog", response_class=HTMLResponse)
async def fastblog_info(request: Request):
    return templates.TemplateResponse("fastblog.html", {"request": request, "routes": top_level_routes, "theme": settings.theme})

# --- AUTH ROUTES (Login/Logout) ---

@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # If already logged in, redirect to admin
    if "user" in request.session:
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("admin_login.html", {"request": request, "theme": settings.theme, "error": None})

@app.post("/admin/login", response_class=HTMLResponse)
async def login_submit(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...)
):
    # Check Username
    is_user_ok = secrets.compare_digest(username, settings.admin_user)
    
    # Check Password
    is_pass_ok = verify_password(password, settings.admin_pass, settings.admin_salt)
    
    if is_user_ok and is_pass_ok:
        # Set Session
        request.session["user"] = username
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    
    # Login Failed
    return templates.TemplateResponse("admin_login.html", {
        "request": request, 
        "theme": settings.theme, 
        "error": "Invalid credentials"
    }, status_code=401)

@app.get("/admin/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)


# --- ADMIN ROUTES (Protected by Session) ---

# 1. Dashboard
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: str = Depends(check_admin_session)):
    with get_db_connection() as conn:
        posts = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "posts": posts, "theme": settings.theme, "user": user})

# 2. Editor (New Post)
@app.get("/admin/new", response_class=HTMLResponse)
async def new_post_form(request: Request, user: str = Depends(check_admin_session)):
    return templates.TemplateResponse("admin_editor.html", {"request": request, "post": None, "theme": settings.theme})

# 3. Editor (Edit Existing)
@app.get("/admin/edit/{post_id}", response_class=HTMLResponse)
async def edit_post_form(request: Request, post_id: int, user: str = Depends(check_admin_session)):
    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return templates.TemplateResponse("admin_editor.html", {"request": request, "post": post, "theme": settings.theme})

# 4. Save Action
@app.post("/admin/save")
async def save_post(
    request: Request,
    id: str = Form(""), 
    title: str = Form(...), 
    content: str = Form(...), 
    user: str = Depends(check_admin_session)
):
    with get_db_connection() as conn:
        if id: # Update existing
            conn.execute("UPDATE posts SET title = ?, content = ? WHERE id = ?", (title, content, id))
            # invalidate cache
            cache_key = f"/post/{id}"
            if cache_key in page_cache:
                del page_cache[cache_key]
        else: # Create new
            conn.execute("INSERT INTO posts (title, content) VALUES (?, ?)", (title, content))
        conn.commit()
        
    if "/" in page_cache:
        del page_cache["/"]
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

# 5. Delete Action
@app.post("/admin/delete/{post_id}")
async def delete_post(post_id: int, user: str = Depends(check_admin_session)):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,)).commit()
        
    cache_key = f"/post/{post_id}"
    if cache_key in page_cache:
        del page_cache[cache_key]
    if "/" in page_cache:
        del page_cache["/"]
        
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0", port=8000)