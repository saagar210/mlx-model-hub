# Ship Changes

Commit, push, and optionally create a PR for current changes.

## Steps

1. **Check Status**: Run `git status` and `git diff --stat` to see what changed
2. **Review Changes**: Summarize what will be committed
3. **Commit**: Create a commit with conventional commit format:
   - `feat:` new feature
   - `fix:` bug fix
   - `refactor:` code restructuring
   - `docs:` documentation
   - `test:` adding tests
   - `chore:` maintenance
4. **Push**: Push to the remote branch
5. **PR Decision**: Ask if a pull request is needed
   - If yes, create PR with summary and test plan
   - If no, confirm push completed

## Commit Message Format
```
type(scope): short description

- Bullet points for details if needed

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Safety Checks
- Never force push to main/master
- Warn about uncommitted sensitive files (.env, credentials)
- Verify branch is up to date before pushing
