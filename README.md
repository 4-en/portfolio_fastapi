# FastBlog

A self-hosted, lightweight blogging and portfolio platform built with FastAPI, SQLite, and Jinja2. This project is designed for simplicity and performance, utilizing client and server-side caching and Markdown rendering for dynamic content management.

## Key Features

* **FastAPI Framework:** High-performance asynchronous web framework.
* **SQLite Database:** Zero-configuration database for storing posts and pages.
* **Markdown Support:** Write content in Markdown; the engine renders it to HTML.
* **Admin Interface:** Built-in dashboard to create, edit, and delete posts securely.
* **Session Authentication:** Secure login system with hashed passwords and session management.
* **Caching Strategy:** Implements server-side caching for static files and pages to optimize load times and client-side preloading.
* **CLI Configuration:** Includes a command-line utility for easy initial setup.

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd <repository-name>

```


2. **Set up a virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

```


3. **Install dependencies**
Ensure you have the required packages installed (FastAPI, Uvicorn, Jinja2, Markdown, Cachetools, Colorama, Python-Multipart).
```bash
pip install -r requirements.txt

```



## Configuration

Before running the application, you must generate the configuration file. This handles site metadata, admin credentials, and legal information.

Run the interactive setup script:

```bash
python setup.py

```

Alternatively, you can run it non-interactively by passing arguments:

```bash
python setup.py --yes --admin-user "admin" --admin-pass "securepassword" --title "My Blog"

```

## Usage

### Starting the Server

To start the application, run the main entry point. The server will host on `0.0.0.0:8000` by default.

```bash
python main.py
# OR
uvicorn main:app --host HOST --port PORT

```

### Accessing the Admin Panel

1. Navigate to `http://localhost:8000/admin`.
2. Log in using the credentials defined during the `setup.py` process.
3. From the dashboard, you can manage blog posts and view site content.

## Directory Structure

* `main.py`: The core application entry point and logic.
* `setup.py`: Configuration generation script.
* `templates/`: Jinja2 HTML templates.
* `static/`: CSS, JavaScript, images, and Markdown files.
* `static/markdown/`: Place `.md` files here for static pages.
* `static/css/themes/`: CSS theme files.


* `blog.db`: SQLite database file (generated automatically upon first run).

## License

Apache 2.0
