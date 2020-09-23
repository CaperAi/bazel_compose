# Bazel Compose

`bazel_compose` is `docker-compose` for `bazel`. It allows you to use a `docker-compose.yml`-like file to describe how
to start and run many container images. 

## Usage

Define a `bazel-compose.yml` with contents similar to the following:

```yaml
version: '2.0'
services:
  test:
    image: //something
```

Now run the following command:

```shell script
bazel run //caper/bazel_compose -- $PWD
bazel run //caper/bazel_compose -- $PWD --follow <container> # Only tails logs of specific container
```

After a few moments you will see the logs from your container. Your container (`//something`) has just been built &
tagged (`bazel run //something -- --norun`) and then it was started (`docker-compose up -d test`). Now, whenever you
edit the files that go into producing `//something` your container will automatically be rebuilt and restarted.

**Note**: When you have many containers startup time might be more than a few moments. If you have started & connected
your IDE to bazel, though, this should not be a problem as the IDE makes the same calls we make to the bazel daemon.

## Installation 

1. Install `ibazel`

   ```shell script
   wget -O ibazel https://github.com/bazelbuild/bazel-watcher/releases/download/v0.13.2/ibazel_linux_amd64
   chmod +x ibazel
   sudo mv ibazel /usr/local/bin/ibazel
   ```

2. ???
3. Profit

## Implementation

This code is really a wrapper around:

1. [bazel](https://bazel.build/)
2. [ibazel](https://github.com/bazelbuild/bazel-watcher/)
3. [docker-compose](https://github.com/docker/compose)

On startup we read in the `bazel-compose.yml` from the `cwd`. We then parse this file and look for anything that looks
like a bazel targets. We then give those targets to `ibazel` and ask `ibazel` to build these targets whenever files they
depend on change. Once we see a change we check the `.digest` file from the [container image](https://github.com/bazelbuild/rules_docker/blob/f4822f3921f0c343dd9e5ae65c760d0fb70be1b3/container/image.bzl#L603)
to make sure that the contents of the container has actually changed. Once we are sure there has been a change we tell
bazel to tag the image on the host system using `bazel run //something -- --norun`. We then tell `docker-compose` to
restart your image.
