# A/B Choice Tool

A web tool for iterative option selection using LLM-generated options and user voting.

## Overview

This tool presents users with pairs of options and iteratively finds the most preferred option through a two-step process:

1. **Step 1 (Generation)**: Users are shown LLM-generated options based on configured criteria. Selected options inform future generations using an exploitation/exploration balance. Users can also submit their own options.

2. **Step 2 (Selection)**: Users select from options that were chosen at least once in Step 1. All eligible options are compared against each other. Results are tracked by longest streak and final winner.

## Setup

### 1. Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

### 2. Install dependencies

```bash
pip install -Ur requirements
```

### 3. Create PostgreSQL database

```sql
CREATE USER abselect WITH PASSWORD 'abselect';
CREATE DATABASE abselect OWNER abselect;
```

### 4. Configure local settings

```bash
cp ab_choice/local_settings.py.example ab_choice/local_settings.py
```

Edit `ab_choice/local_settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'abselect',
        'USER': 'abselect',
        'PASSWORD': 'abselect',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

OPENAI_API_KEY = 'your-openai-api-key-here'
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Create admin user

```bash
python manage.py createsuperuser
```

### 7. Run the server

```bash
python manage.py runserver
```

## Configuration

### Admin Panel

Access the admin panel at `http://localhost:8000/admin/`

#### Setting up AdminConfig

1. Go to **Admin configs** and click **Add**
2. Configure:
   - **Prompt**: Define the domain and criteria for option generation. Example:
     ```
     Domain: mascot names for a tech company.
     Criteria: playful, memorable, tech-related, could be a character name.
     The company works in cloud computing and AI.
     ```
   - **Current step**:
     - `0` = Disabled (users see "process disabled" message)
     - `1` = Generation phase (LLM generates options)
     - `2` = Selection phase (users vote on Step 1 winners)
   - **Rounds count**: Number of pairs shown to each user in Step 1

### Workflow

1. Set `current_step = 1` and configure the prompt
2. Share the URL with users for Step 1 voting
3. When ready, set `current_step = 2` for final selection
4. View results in admin results pages

## User Interface

- **Main page** (`/`): Shows two options as full-height buttons (50/50 split)
- **Step 1**: Includes manual input field at bottom for user submissions
- **Disabled** (`/disabled/`): Shown when `current_step = 0`
- **Complete** (`/complete/`): Shown when user finishes all rounds

## Admin Results

Access results at:
- `/admin/selector/option/results/step1/` - Step 1 popularity (selection count)
- `/admin/selector/option/results/step2-streak/` - Step 2 longest winning streaks
- `/admin/selector/option/results/step2-final/` - Step 2 final winners (last comparison winner)

All results pages support IP filtering to exclude anomalous users.

## API / LLM Adapter

The tool uses an adapter pattern for LLM integration. Currently implements OpenAI, but can be extended:

```python
from selector.llm import LLMAdapter

class MyCustomAdapter(LLMAdapter):
    def generate_options(self, prompt: str, history: list) -> tuple[str, str]:
        # Your implementation
        return option_a, option_b
```

## Running Tests

```bash
python manage.py test
```

## License

MIT
