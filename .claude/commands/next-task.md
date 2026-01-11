# Next Task

Find and start the next task from Task Master.

## Steps

1. **Get Next Task**: Use Task Master to find the next available task based on:
   - Dependencies (all deps must be done)
   - Priority
   - Status (pending tasks only)

2. **Show Task Details**: Display:
   - Task ID and title
   - Description
   - Acceptance criteria
   - Dependencies (if any)
   - Subtasks (if any)

3. **Confirm Start**: Ask if ready to begin this task

4. **Mark In-Progress**: Update task status to in-progress

5. **Begin Work**: Start implementing based on task requirements

## If No Tasks Available
- Check if all tasks are complete
- Check if tasks are blocked by dependencies
- Suggest reviewing the task list with `task-master get tasks`
