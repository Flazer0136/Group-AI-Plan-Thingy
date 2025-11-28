## How to Set Up

1. **Install uv**
   - Windows: `irm https://astral.sh/uv/install.ps1 | iex`
   - Mac/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

2. **Clone the repo**
   ```bash
   git clone https://github.com/Flazer0136/Group-AI-Plan-Thingy.git

3. **How to Sync Dependencies**
    ```bash
    uv sync

4. **Run the Server**
    ```bash
    uv run python manage.py migrate
    uv run uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --reload

5. **Final Sanity Check**
    run this command to make sure your lockfile is perfectly up to date with your `pyproject.toml`:

    ```bash
    uv lock
