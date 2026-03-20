# GEMINI Project Instructions

## Project Overview

This project is a **gamified quiz web application** built using **Python Flask** with server-rendered HTML templates.

Users should be able to:

- Register and login
- Play multiple choice quizzes
- Earn XP points
- Level up
- View their profile and quiz history
- Compete on a leaderboard

This project **must remain a Flask application**.
Do NOT convert it to React, Vue, or other frontend frameworks.

---

# Architecture

Backend: Python Flask
Frontend: HTML templates with Jinja
Database: SQLite
Static Assets: CSS, JavaScript, Images

The backend handles:

- authentication
- routing
- quiz logic
- leaderboard
- gamification
- database interaction

---

# Actual Project Folder Structure

quiz-app/

backend/

- app.py
- routes.py
- auth.py
- quiz_engine.py
- leaderboard.py
- gamification.py
- database.py
- models.py

config/

- settings.py

database/

- schema.sql

templates/

- dashboard.html
- home.html
- leaderboard.html
- login.html
- profile.html
- quiz.html
- register.html
- result.html

static/
css/

- style.css

js/

- leaderboard.js
- quiz.js
- timer.js

images/

requirements.txt
GEMINI.md

---

# Backend Responsibilities

## app.py

Main Flask entry point.
Initializes the Flask app, loads configuration from `config/settings.py`, connects the database, and registers routes.

## routes.py

Contains all Flask routes such as:

- /
- /login
- /register
- /dashboard
- /quiz
- /result
- /leaderboard
- /profile

Routes should render templates using `render_template`.

---

## auth.py

Handles authentication logic:

- user registration
- login
- logout
- password hashing
- session handling

Use `werkzeug.security` for password hashing.

---

## quiz_engine.py

Handles quiz logic:

- fetch quiz questions
- randomize question order
- validate answers
- calculate quiz score
- store quiz results

---

## leaderboard.py

Handles leaderboard functionality:

- ranking users
- fetching top players
- updating leaderboard after quiz

---

## gamification.py

Handles gamification features:

- XP calculation
- level system
- streaks
- achievements or badges

---

## database.py

Handles SQLite database connection and query helpers.

The database should be initialized using `database/schema.sql`.

---

## models.py

Defines Python models or helper structures representing:

- Users
- Questions
- Quiz results
- Leaderboard entries

---

# Database Tables

The schema should contain tables like:

users

- id
- username
- email
- password_hash
- xp
- level
- created_at

questions

- id
- question_text
- option_a
- option_b
- option_c
- option_d
- correct_answer

quiz_results

- id
- user_id
- score
- total_questions
- date

leaderboard

- id
- user_id
- score
- rank

---

# Frontend Templates

Templates are located in `templates/`.

Use Jinja templating to render dynamic data.

Example variables:

{{ username }}
{{ score }}
{{ questions }}

---

# Static Assets

Located in `static/`.

css/
Contains styling files.

js/
Contains JavaScript for:

- quiz logic
- countdown timer
- leaderboard updates

images/
Contains UI assets.

---

# Core Features

Authentication:

- register
- login
- logout

Quiz System:

- multiple choice questions
- random question order
- score calculation
- quiz results page

Gamification:

- XP system
- user levels
- streak tracking

Leaderboard:

- ranking system
- top players

Dashboard:

- quiz history
- user XP and level

---

# Coding Rules

- Keep logic modular
- Routes should only handle request/response
- Business logic belongs in quiz_engine.py or other modules
- Database queries should go through database.py
- Avoid mixing frontend and backend logic

---

# Goal

Create a clean, modular Flask web application for a gamified quiz platform that is easy to maintain, extend, and understand.
