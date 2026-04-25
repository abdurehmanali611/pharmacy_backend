# Apex Django Backend Plan

This frontend already talks to a REST API from [`lib/actions.ts`](c:\Users\abdur\Documents\Projects\apex\lib\actions.ts), so the cleanest move is to build a Django REST API that preserves the same resources:

- `POST /auth/login`
- `GET/PATCH /heroFooter`
- `GET/POST/PUT/DELETE /services`
- `GET/POST/PUT/DELETE /portfolio`
- `GET/POST/PUT/DELETE /blogs`
- `GET/POST/PUT/DELETE /teams`
- `GET/POST/PUT/DELETE /partners`
- `GET/POST/DELETE /contacts`
- `GET/POST/PUT/DELETE /testimonials`

## 1. Recommended stack

- Django: main backend framework
- Django REST Framework: API endpoints
- MySQL: production-style relational database
- `django-cors-headers`: allow your Next.js frontend to call the API
- `simplejwt`: token-based admin login

## 2. Suggested backend structure

```text
BackEnd/
  manage.py
  requirements.txt
  .env
  config/
    settings.py
    urls.py
  apps/
    accounts/
    hero/
    services/
    portfolio/
    blogs/
    teams/
    partners/
    contacts/
    testimonials/
```

## 3. Create the project

From `BackEnd/`:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
django-admin startproject config .
python manage.py startapp accounts
python manage.py startapp hero
python manage.py startapp services
python manage.py startapp portfolio
python manage.py startapp blogs
python manage.py startapp teams
python manage.py startapp partners
python manage.py startapp contacts
python manage.py startapp testimonials
```

## 4. Configure MySQL

Create the database in MySQL:

```sql
CREATE DATABASE apex_portfolio CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Then copy `.env.example` to `.env` and wire it in `settings.py`.

Example database config:

```python
from decouple import config

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", default="3306"),
    }
}
```

## 5. Core Django settings

Install these apps:

```python
INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "accounts",
    "hero",
    "services",
    "portfolio",
    "blogs",
    "teams",
    "partners",
    "contacts",
    "testimonials",
]
```

Middleware:

```python
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    # keep this near the top
]
```

CORS:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]
```

REST auth:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}
```

## 6. Match your current frontend API

Your frontend stores a token in `localStorage` and sends:

```text
Authorization: Bearer <token>
```

That means Django should expose a login endpoint that returns:

```json
{
  "token": "..."
}
```

The easiest path is:

- create an admin user with Django
- expose `POST /auth/login`
- validate username/email + password
- return JWT access token as `token`

## 7. Suggested models

These should reflect the forms your admin UI is already using.

### `hero`
- `name`
- `amount`

### `services`
- `title`
- `description`
- `icon` or `image`

### `portfolio`
- `title`
- `description`
- `image`
- `category`
- `project_url`

### `blogs`
- `title`
- `description`
- `image`
- `author`
- `published_at`

### `teams`
- `name`
- `role`
- `image`
- `bio`

### `partners`
- `title`
- `image`
- `website`

### `contacts`
- `name`
- `email`
- `subject`
- `message`
- `created_at`

### `testimonials`
- `name`
- `role`
- `company`
- `image`
- `message`

## 8. URL design that fits `actions.ts`

Use a shared `/api` prefix in Django and point the frontend to it with:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api
```

Then Django routes should be:

```text
/api/auth/login
/api/heroFooter
/api/heroFooter/<name>
/api/services
/api/services/<id>
/api/portfolio
/api/portfolio/<id>
/api/blogs
/api/blogs/<id>
/api/teams
/api/teams/<id>
/api/partners
/api/partners/<id>
/api/contacts
/api/contacts/<id>
/api/testimonials
/api/testimonials/<id>
```

## 9. Recommended implementation style

- Use `ModelViewSet` for the CRUD resources
- Use serializers for validation
- Use a custom API view for `auth/login`
- Protect create/update/delete routes with JWT auth
- Leave public `GET` routes open if you want the portfolio site visible without login

## 10. Practical build order

Build in this order so you get value quickly:

1. MySQL connection
2. Django project setup
3. JWT login
4. `services`, `portfolio`, `blogs`
5. `teams`, `partners`, `testimonials`
6. `contacts`
7. `heroFooter`
8. Admin panel cleanup and permissions

## 11. Frontend integration

`lib/actions.ts` now supports:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api
```

So once Django is running, you only need to add that variable to your frontend `.env.local` and restart Next.js.

## 12. Next step I recommend

If you want the fastest path, the next concrete move is for us to scaffold the actual Django project in `BackEnd/` and create the first working endpoints:

1. login
2. services
3. portfolio

Once those are live, the rest of the resources follow the same pattern.
