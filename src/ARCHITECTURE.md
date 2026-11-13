# Giant Wiki Architecture

## Error Handling Patterns

Giant Wiki uses a layered error handling approach based on the context:

### 1. Service/Library Layer (Raise)

Services and libraries raise custom exceptions for error conditions:

```python
# wiki/services/git_storage.py
def commit_and_push(message):
    if not valid:
        raise GitOperationError("...")
    # ... perform operation
```

**When to use**: In reusable services and library code that may be called from multiple contexts.

**Why**: Allows callers to decide how to handle the error based on their context.

### 2. Celery Task Layer (Catch, Log, Re-raise)

Celery tasks catch exceptions, log to the Task model, and re-raise:

```python
# wiki/tasks.py
@shared_task(bind=True)
def sync_task(self, task_id):
    task = Task.objects.get(id=task_id)
    task.start()

    try:
        service.commit_and_push()
        task.complete(success=True)
    except GitOperationError as e:
        task.complete(success=False, logs=str(e))
        raise  # Let Celery handle retry
```

**When to use**: In Celery task wrappers.

**Why**: Provides visibility into task failures in the database and UI, while still allowing Celery's retry mechanism to work.

### 3. View Layer (Catch, Message, Redirect)

Django views catch exceptions, show user-friendly messages, and redirect:

```python
# wiki/views.py
def edit_view(request):
    try:
        service.save_page()
        return redirect(...)
    except InvalidPathError:
        messages.error(request, "Invalid path")
        return redirect(...)
```

**When to use**: In Django views that interact with users.

**Why**: Provides user-friendly error messages and graceful degradation instead of 500 errors.

## Custom Exceptions

- `InvalidPathError(ValueError)`: Page path validation errors
- `GitOperationError(Exception)`: Git command failures

These inherit from base exceptions but provide semantic meaning through their names.

## Validation Strategy

Input validation occurs at trust boundaries:

- **User input**: Views validate form data
- **External data**: Services validate git repository data
- **Internal calls**: Minimal validation (trust internal code)

This avoids redundant validation deep in the call stack while ensuring security at entry points.
