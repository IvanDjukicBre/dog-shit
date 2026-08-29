# Project conventions

These rules are mandatory for all changes in this repository.

1. Use CommonJS (`module.exports` / `require`). Never ESM `import`/`export`.
2. Never add a dependency. This project has zero dependencies and must stay that way.
3. Every exported function must carry a JSDoc block with `@param` and `@returns`.
4. Two-space indentation, single quotes, semicolons.
