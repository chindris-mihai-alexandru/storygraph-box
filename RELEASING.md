# Releasing

1. Move the items under `## [Unreleased]` in `CHANGELOG.md` into a new `## [X.Y.Z] - date` section.
2. Commit that to `main` and wait for CI to pass.
3. Tag and push, with the leading `v`.

```
git tag vX.Y.Z
git push origin vX.Y.Z
```

The release workflow runs the tests, publishes the release from the changelog section and moves the floating `vX` tag. It stops with an error if the section is missing.

To try a build first, push a tag with a suffix such as `vX.Y.Z-rc1`. That creates a prerelease with generated notes and leaves `vX` where it is.
