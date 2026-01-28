* [ ] See if all tests pass
* [ ] Get the release pull request approved
* [ ] Squash merge the release pull request with message "`Release <VERSION>`"
* [ ] Tag with X.Y.Z, push tag on urllib3/urllib3 (not on your fork, update `<REMOTE>` accordingly)
  * Notice that the `<VERSION>` shouldn't have a `v` prefix (Use `2.0.0` instead of `v2.0.0`)
  * ```
    # Ensure the release commit is the latest in the main branch.
    export VERSION=<X.Y.Z>
    export REMOTE=origin
    git checkout main
    git pull $REMOTE main
    git tag -s -a "$VERSION" -m "Release: $VERSION"
    git push $REMOTE --tags
    ```
* [ ] The tag will trigger the `release` GitHub workflow. This requires a review from a maintainer.
* [ ] Create a GitHub release with the changelog
* [ ] Announce on social media and internally
