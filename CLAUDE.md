# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Read the requirement from `docs/requirements.md` and generate the app according to the structure below. 

## Project Overview

This is a **Clean Architecture** FastAPI + Vue.js + PrimeVue + Tailwind application with OAuth authentication. 
The project follows a clear separation of concerns with distinct layers for backend and frontend.

## Architecture Overview

```
/
├── src/
│   ├── backend/            # FastAPI Backend (Python)
│   │   ├── main.py         # Typer CLI and can also kick off the FastAPI application entry point
│   │   ├── api/            # API Controllers/Routes
│   │   │   └── routes.py   # API endpoints
│   │   ├── core/           # Core Services & Configuration
│   │   │   ├── config.py   # Application settings
│   │   │   ├── security.py # JWT, OAuth, and security utilities
│   │   │   └── auth.py     # OAuth authentication handlers
│   │   └── models/         # Data models (Pydantic)
│   │       └── user.py     # User models
│   ├── frontend/           # Vue.js Frontend (Vite)
│   │   ├── src/            # Vue components and views
│   │   │   ├── App.vue     # Main application component
│   │   │   ├── router/     # Vue Router configuration
│   │   │   ├── views/      # Page views (Home, Login, Private)
│   │   │   └── main.js     # Application entry point
│   │   ├── index.html      # HTML template
│   │   ├── vite.config.js  # Vite configuration
│   │   └── package.json    # Frontend dependencies
│   └── dist/               # Built frontend files (auto-generated)
├── tests/                  # Test files
│   ├── tests/api/          # Backend API tests
│   └── tests/frontend/     # Frontend tests
├── config.yaml             # Application configuration
├── credentials.yaml        # Sensitive credentials (gitignored)
├── pyproject.toml          # Python dependencies
└── dev.bat                 # Development startup script
```

## Key Features

1. **Clean Architecture**: Clear separation between backend and frontend
2. **OAuth Authentication**: Support for Google, GitHub, Facebook, Apple, LinkedIn, Microsoft
3. **JWT Security**: Secure HTTP-only cookies for authentication
4. **SPA Routing**: Vue.js frontend with FastAPI serving static files
5. **CORS Configuration**: Proper CORS setup for development
6. **DRY CSS**: Try to put as much common CSS styles in the src/assets/css/main/css file - those styles that will be used across many future pages - to keep a common theme and a single place to change them. Styles specific to the page can be put in a <style scoped> block.
7. **Shared Theme**: The src/assets/css/main/css and the common shared theme should use the Tailwind CSS library wherever possible and not to invent your own local styles.

## Development Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- npm or yarn
- uv (Python package manager)

### Initial Setup

1. **Backend Setup**:
   ```bash
   uv sync
   ```

2. **Frontend Setup**:
   ```bash
   cd src/frontend
   npm install
   ```

### Running the Application

Use the provided `dev.bat` file:
```bash
dev.bat
```

This will:
1. Start the Vite dev server in watch mode (builds to `dist/`)
2. Start the FastAPI server with auto-reload

**Important**: Run `dev.bat` from the project root directory, not from within the `src/backend` directory.

Alternatively, run manually:
```bash
# Terminal 1: Frontend (watch mode)
cd src/frontend
npm run build -- --watch

# Terminal 2: Backend (run from project root)
uvicorn src.main:app --reload
```

Or use the convenience script:
```bash
run_backend.bat
```

### Backend Commands

- **Run server**: `uvicorn main:app --reload`
- **Install dependencies**: `uv sync`
- **Add dependency**: `uv add <package>`
- **Run tests**: `pytest tests/` (if tests are configured)

### Frontend Commands

- **Build**: `npm run build`
- **Build (watch mode)**: `npm run build -- --watch`
- **Preview**: `npm run preview`

## Backend Structure

### FastAPI Configuration

- **Base URL**: `/api/` prefix for all API endpoints
- **Static Files**: Frontend served from `/` (SPA routing)
- **CORS**: Configured to allow all origins in development
- **Authentication**: JWT tokens stored in HTTP-only, Secure cookies

### API Endpoints

**Public Endpoints** (no authentication):
- `GET /api/public` - Public test endpoint
- `GET /` - Serves frontend index.html

**Authenticated Endpoints**:
- `GET /api/private` - Private endpoint (requires auth)
- `GET /api/auth/user` - Get current user info
- `POST /api/auth/logout` - Logout

**OAuth Endpoints**:
- `GET /api/auth/login/{provider}` - Redirect to OAuth provider
- `GET /api/auth/callback/{provider}` - OAuth callback handler

### Authentication Flow

1. User clicks "Sign In" on frontend
2. Frontend redirects to `/api/auth/login/{provider}`
3. User authenticates with OAuth provider
4. Provider redirects back to `/api/auth/callback/{provider}`
5. Backend creates JWT token and sets HTTP-only cookie
6. User is redirected to frontend with token
7. Frontend makes authenticated requests with credentials: 'include'

## Frontend Structure

### Vue.js Configuration

- **Router**: Vue Router with navigation guards
- **Views**:
  - `HomeView.vue` - Landing page
  - `LoginView.vue` - Social login page with provider icons
  - `PrivateView.vue` - Authenticated private area
- **Authentication**: Checks `/api/auth/user` endpoint on app load

## Testing

### Backend Testing

```bash
# Run pytest (if configured)
pytest tests/api/
```

### Frontend Testing

```bash
# From frontend directory
cd src/frontend
npm test
```

## Deployment

### Production

```bash
# Build frontend
cd src/frontend
npm run build

# Run backend
cd src/backend
uvicorn main:app --host 0.0.0.0 --port 80
```

### Environment Variables

For production, ensure:
- `config.yaml` has production settings
- `credentials.yaml` exists with real OAuth credentials
- JWT secret key is strong and unique
- Cookies are set with `Secure` flag

## Project Conventions

1. **Backend**:
   - All API routes prefixed with `/api/`
   - Pydantic models for request/response validation
   - Dependency injection for services

2. **Frontend**:
   - Vue 3 Composition API
   - Pinia for state management (if needed)
   - Vite for bundling

3. **Naming**:
   - Snake case for Python files/functions
   - PascalCase for Vue components
   - kebab-case for HTML/CSS

## Troubleshooting

### Common Issues

1. **Frontend not building**: Ensure Node.js is installed and `npm install` was run
2. **CORS errors**: Check that backend is running with proper CORS middleware
3. **OAuth not working**: Verify credentials.yaml exists with valid credentials
4. **Authentication failures**: Check browser cookies and network requests

### Debugging

- **Backend logs**: Check terminal where uvicorn is running
- **Frontend logs**: Check browser console (F12)
- **Network requests**: Use browser dev tools to inspect API calls

## Notes

- The `.gitignore` excludes `credentials.yaml` and `.venv/`
- Frontend builds to `dist/` which is served by FastAPI
- OAuth callbacks must be registered with providers
- For production, generate a strong secret key for JWT
