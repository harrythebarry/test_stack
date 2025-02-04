from pydantic import BaseModel, computed_field
import hashlib

class StackPack(BaseModel):
    title: str
    description: str
    from_registry: str
    sandbox_init_cmd: str
    sandbox_start_cmd: str
    prompt: str
    setup_time_seconds: int

    @computed_field
    def pack_hash(self) -> str:
        """Generate a unique hash for this pack based on init command and registry."""
        content = f"{self.sandbox_init_cmd}{self.from_registry}".encode()
        return hashlib.sha256(content).hexdigest()[:12]

_SETUP_COMMON_CMD = """
# Ensure that the frontend directory exists
if [ ! -d 'frontend' ]; then 
    cp -r /frontend .;
fi

# Verify that package.json is present and log the directory contents
if [ -f /frontend/package.json ]; then
    cat /frontend/package.json
    ls -l /frontend
fi

# Change to the frontend directory
cd /frontend

# Git setup (if it's not already done)
git config --global user.email 'bot@sparkstack.app'
git config --global user.name 'Spark Stack Bot'
git config --global init.defaultBranch main
if [ ! -d ".git" ]; then
    git init
    git config --global init.defaultBranch main
    git add -A
    git commit -m 'Initial commit'
fi

# Create a .gitignore file to avoid unnecessary files in the git repo
cat > .gitignore << 'EOF'
node_modules/
.config/
.env
.next/
.cache/
.netlify/
*.log
dist/
build/
tmp/
EOF

# Ensure .env file exists in frontend
if [ ! -f '/frontend/.env' ]; then
    touch /frontend/.env
fi

# Append backend URL if not already set
if ! grep -q "^NEXT_PUBLIC_BACKEND_URL=" /frontend/.env; then
    echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:3000" >> /frontend/.env
fi

# Debug output for .env existence check
echo "Checking if .env exists: /frontend/.env"
ls -l /frontend/.env

# Source the .env file to load environment variables
set -a
[ -f /frontend/.env ] && . /frontend/.env
set +a

# If the .env file cannot be sourced, log an error and exit
if [ $? -ne 0 ]; then
    echo "Error: Failed to source the .env file."
    exit 1
fi
""".strip()



_START_NEXT_JS_CMD = f"""
{_SETUP_COMMON_CMD}
cd /frontend
npm run dev
""".strip()

_START_ANGULAR_CMD = f"""
{_SETUP_COMMON_CMD}
cd /frontend
npm run start -- --host 0.0.0.0 --port 3000
""".strip()



_SETUP_COMMON_CMD_BACKEND = """
cd /app

git config --global user.email 'bot@sparkstack.app'
git config --global user.name 'Spark Stack Bot'
git config --global init.defaultBranch main
if [ ! -d ".git" ]; then
    git init
    git add -A
    git commit -m 'Initial commit'
fi

cat > .gitignore << 'EOF'
# Python specific
__pycache__/
*.pyc
.env  # Sensitive information - DO NOT commit!
.venv/  # Or venv/ or env/ - Your virtual environment directory
.mypy_cache/

# General
.config/
node_modules/  # If you have any frontend stuff
dist/
build/
tmp/
*.log
.DS_Store  # macOS specific
Thumbs.db  # Windows specific
.idea/     # JetBrains IDEs
.vscode/   # VS Code
.pytest_cache/ # pytest cache

# Fast API Specific (if applicable)
alembic.ini # if you use alembic
alembic/versions/* # except for the __init__.py file in the versions/ directory.
!alembic/versions/__init__.py

# Docker related (if applicable)
.dockerignore

# OS related
.swap

# Other common files/folders
.envrc # direnv
.direnv/ # direnv
EOF

if [ ! -f '/app/.env' ]; then
    touch /app/.env
fi
if ! grep -q "^IS_SPARK_STACK=" /app/.env; then
    echo "IS_SPARK_STACK=true\n" >> /app/.env
fi

set -a
[ -f /app/.env ] && . /app/.env
set +a
""".strip()




_START_FASTAPI_CMD = f"""
{_SETUP_COMMON_CMD_BACKEND}
cd /app
uvicorn main:app --host 0.0.0.0 --port 3000
""".strip()

_START_EXPRESS_CMD = f"""
{_SETUP_COMMON_CMD_BACKEND}
cd /app
npm run start
""".strip()


PACKS = [
    # EXISTING STACKPACKS (Next.js, Angular, p5, etc.)
    StackPack(
        title="Next.js",
        description="A simple Next.js app. Best for starting from scratch with minimal components.",
        from_registry="ghcr.io/sshh12/spark-stack-pack-nextjs-vanilla:latest",
        sandbox_init_cmd=_SETUP_COMMON_CMD,
        sandbox_start_cmd=_START_NEXT_JS_CMD,
        prompt="""
You are building a Next.js app.

The user chose to use a "vanilla" app so avoid adding any additional dependencies unless they are explicitly asked for.

Already included:
- Next.js v15 (app already created)
- tailwindcss
- `npm install` done
- /frontend/.env, /frontend/.git

Style Tips:
- Use inline tailwind classes over custom css
- Use tailwind colors over custom colors
- Assume the user want's a nice look UI out of the box (so add styles as you create components and assume layouts based on what the user is building)
- Remove Next.js boilerplate text from the index page

Structure Tips:
- Always use Next.js app router for new pages, creating /src/<page>/page.js
- Always ensure new pages are somehow accessible from the main index page
- Always include "use client" unless otherwise specified
- NEVER modify layout.js and use page.js files for layouts

Code Tips:
- NEVER put a <a> in a <Link> tag (Link already uses a <a> tag)

3rd Party Tips:
- If you need to build a map, use react-leaflet
    1. $ npm install react-leaflet leaflet
    2. `import { MapContainer, TileLayer, useMap } from 'react-leaflet'` (you do not need css imports)
- If you need placeholder images, use https://prompt-stack.sshh.io/api/mocks/images[?orientation=landscape&query=topic] (this will redirect to a rand image)
""".strip(),
        setup_time_seconds=60,
    ),
    StackPack(
        title="Next.js Shadcn",
        description="A Next.js app with Shadcn. Best for building a modern web app with a clean UI.",
        from_registry="ghcr.io/sshh12/spark-stack-pack-nextjs-shadcn@sha256:243aeb37ac9f4a243a2dce849c73997c8ced1ca0363e16a124f7364b0f985242",
        sandbox_init_cmd=_SETUP_COMMON_CMD,
        sandbox_start_cmd=_START_NEXT_JS_CMD,
        prompt="""
You are building a Next.js app with Shadcn.

The user chose to use a Next.js app with Shadcn so avoid adding any additional dependencies unless they are explicitly asked for.

Already included:
- Next.js v15 (app already created)
- lucide-react v0.460
- axios v1.7
- recharts v2.13
- All shadcn components (import them like `@/components/ui/button`)
- `npm install` done
- /frontend/.env, /frontend/.git

Style Tips:
- Use inline tailwind classes over custom css
- Use tailwind colors over custom colors
- Prefer shadcn components as much as possible over custom components
- Assume the user wants a nice looking UI out of the box (so add styles as you create components and assume layouts based on what the user is building)
- Remove Next.js boilerplate text from the index page

Structure Tips:
- Always use Next.js app router for new pages, creating /src/frontend/<page>/page.js
- Always ensure new pages are somehow accessible from the main index page
- Prefer "use client" unless otherwise specified
- NEVER modify layout.js and use page.js files for layouts

Code Tips:
- NEVER put a <a> in a <Link> tag (Link already uses a <a> tag)

3rd Party Tips:
- If you need to build a map, use react-leaflet
    1. $ npm install react-leaflet leaflet
    2. `import { MapContainer, TileLayer, useMap } from 'react-leaflet'` (you do not need css imports)
- If you need placeholder images, use https://sparkstack.app/api/mocks/images[?orientation=landscape&query=topic] (this will redirect to a rand image)
""".strip(),
        setup_time_seconds=60,
    ),
    StackPack(
        title="p5.js",
        description="A simple app with p5.js. Best for generative art, games, and simulations.",
        from_registry="ghcr.io/sshh12/spark-stack-pack-nextjs-p5:latest",
        sandbox_init_cmd=_SETUP_COMMON_CMD,
        sandbox_start_cmd=_START_NEXT_JS_CMD,
        prompt="""
You are building a p5.js sketch within a Next.js app.

The user ONLY wants to build a p5.js sketch, do not attempt to use any Next.js features or other React features.

Already included:
- Next.js v15 (app already created)
- p5.js v1.11.2
- Addons: p5.sound.min.js, p5.collide2d
- /frontend/.env, /frontend/.git

Style Tips:
- Keep your code clean and readable
- Use p5.js best practices

Structure Tips:
- ALL changes and features should be in /frontend/public/{sketch,helpers,objects}.js
- Organize "objects" (balls, items, etc) into objects.js
- Organize "utils" (utility functions, etc) into helpers.js
- At all times, sketch.js should include setup() windowResized() and draw() functions
- If the user wants to add a p5.js addon, edit layout.js to add a new <Script> (following existing scripts in that files)
""".strip(),
        setup_time_seconds=60,
    ),
    StackPack(
        title="Pixi.js",
        description="An app with Pixi.js. Best for games and animations.",
        from_registry="ghcr.io/sshh12/spark-stack-pack-nextjs-pixi:latest",
        sandbox_init_cmd=_SETUP_COMMON_CMD,
        sandbox_start_cmd=_START_NEXT_JS_CMD,
        prompt="""
You are building a Pixi.js app within a Next.js app.

The user ONLY wants to build a Pixi.js app, do not attempt to use any Next.js features or other React features.

Already included:
- Next.js v15 (app already created)
- Pixi.js v8.6.6
- Addons: @pixi/mesh-extras
- /frontend/.env, /frontend/.git

Style Tips:
- Keep your code clean and readable
- Use Pixi.js best practices

Structure Tips:
- ALL changes and features should be in /frontend/app/src/pixi/*.js
- At all times, /frontend/app/src/pixi/app.js should include "new Application()" and "await app.init(...)"
""".strip(),
        setup_time_seconds=60,
    ),
    StackPack(
        title="Angular",
        description="A simple Angular app. Best for starting from scratch with Angular and minimal components.",
        from_registry="ghcr.io/sshh12/spark-stack-pack-angular-vanilla:latest",
        sandbox_init_cmd=_SETUP_COMMON_CMD,
        sandbox_start_cmd=_START_ANGULAR_CMD,
        prompt="""
You are building an Angular app.

The user chose to use a "vanilla" app so avoid adding any additional dependencies unless they are explicitly asked for.

Already included:
- Angular v19 (app already created)
- `npm install` done
- /frontend/.env, /frontend/.git

Style Tips:
- Assume the user wants a nice looking UI out of the box (so add styles as you create components and assume layouts based on what the user is building)
- Remove Angular boilerplate text from the index page if possible

Structure Tips:
- Always use Angular's CLI to generate new components, services, etc.
- Always ensure new components/pages are accessible from the main app component
- NEVER modify main.ts; put your logic in app.component.ts

Code Tips:
- NEVER put a <a> in a <routerLink> tag (routerLink already uses a <a> tag)
- If you need a map, use @angular/google-maps
- If you need placeholder images, use https://prompt-stack.sshh.io/api/mocks/images
""".strip(),
        setup_time_seconds=60,
    ),

    # === NEW BACKEND STACKS ===
    StackPack(
        title="FastAPI",
        description="A Python backend using FastAPI. Best for simple REST APIs or microservices.",
        from_registry="tiangolo/uvicorn-gunicorn-fastapi:latest",
        sandbox_init_cmd=_SETUP_COMMON_CMD_BACKEND,
        sandbox_start_cmd=_START_FASTAPI_CMD,
        prompt="""
You are building a FastAPI Python backend.

Already included:
- Python 3 + FastAPI
- `pip install -r requirements.txt`
- /app/.env, /app/.git

Tips:
- Put your main API code in /app or /app/backend
- Use 'uvicorn main:app --host 0.0.0.0 --port 3000' to run
- You can add new endpoints by editing main.py or creating separate routers.
- If you need placeholder images or external calls, you can do so with 'requests' or 'httpx'.
""".strip(),
        setup_time_seconds=30,
    ),
    StackPack(
        title="Express",
        description="A Node.js backend using Express. Ideal for REST APIs and server-side logic.",
        from_registry="bitnami/express:latest",
        sandbox_init_cmd=_SETUP_COMMON_CMD_BACKEND,
        sandbox_start_cmd=_START_EXPRESS_CMD,
        prompt="""
You are building an Express.js backend in Node.js.

Already included:
- Node 20 + Express
- `npm install` done
- /app/.env, /app/.git

Tips:
- Put your main server code in /app, typically in server.js or index.js.
- Use 'npm run start' or 'node server.js' to run on port 3000.
- You can create routes by doing 'app.get(...)', etc.

If you need external libraries, run 'npm install <lib>'.
For placeholder images, you can do 'fetch("https://prompt-stack.sshh.io/api/mocks/images")'.
""".strip(),
        setup_time_seconds=30,
    ),
]
