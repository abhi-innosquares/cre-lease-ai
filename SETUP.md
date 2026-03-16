# SETUP.md

## Installation

### Backend
1. Ensure Python 3.9+ is installed.
2. Navigate to `backend` directory:
   ```sh
   cd backend
   ```
3. (Optional) Create and activate a virtual environment:
   ```sh
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```
4. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

### Frontend
1. Ensure Node.js (v16+) and npm are installed.
2. Navigate to `frontend` directory:
   ```sh
   cd frontend
   ```
3. Install dependencies:
   ```sh
   npm install
   ```

## Configuration

### Backend
- Update any environment variables in `.env` (create if missing).
- Database config: Ensure `leases.db` exists or is created on first run.

### Frontend
- Update API endpoint in `src/api.js` if backend URL changes.

## Running

### Backend
- Start FastAPI server:
   ```sh
   python -m uvicorn src.api.server:app --reload
   ```

### Frontend
- Start Vite dev server:
   ```sh
   npm run dev
   ```

## Additional Notes
- Logs are stored in `backend/logs`.
- Input/output data in `backend/data/input` and `backend/data/output`.
- For production, set up proper environment variables and use production build commands.

## Troubleshooting
- If issues occur, check logs and ensure dependencies are installed.
- For Python errors, verify virtual environment and package versions.
- For Node errors, delete `node_modules` and run `npm install` again.

---
For further help, see `backend/README.md` and `frontend/README.md`.
