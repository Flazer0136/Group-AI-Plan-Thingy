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


# App Screenshots

## Login Page
<img width="776" height="306" alt="Screenshot 2025-11-30 221714" src="https://github.com/user-attachments/assets/4826cc26-d6bd-419e-a9f4-7207f72853ed" />

## Home Page
<img width="796" height="459" alt="Screenshot 2025-11-30 215518" src="https://github.com/user-attachments/assets/922161e2-10c8-4857-bc3e-298496382ca0" />


## Main Chat example
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/e17db8ab-2679-4c1c-b8a3-92e20e5d961c" />

