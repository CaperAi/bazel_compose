from caper.bazel_compose.watcher import BuildWatcher
from caper.bazel_compose.compose import DockerCompose, BazelComposeFile
from caper.bazel_compose.bazel import Bazel
import time
from argparse import ArgumentParser
from pathlib import Path


def main(args):
    cwd = Path(args.cwd).absolute()

    compose_file = BazelComposeFile(cwd=str(cwd))
    compose = DockerCompose(compose_file)

    if args.everything:
        print("Attempting to start up all services....")
        compose.up(output_logs=True)

    # Start watching and starting up all of our services
    watcher = BuildWatcher(Bazel(cwd=str(cwd)), compose_file, compose)
    watcher.start()

    services_to_watch = args.follow if args.follow is not None else []

    while True:
        print("attempting to tail logs....")
        compose.logs(*services_to_watch)
        time.sleep(1)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("cwd", help="Current working directory for all subcommands", default=".")
    parser.add_argument("--everything", help="Current working directory for all subcommands", default=True, type=bool)
    parser.add_argument("--follow", help="Tail the logs of a specific subset of containers", nargs='*')
    main(parser.parse_args())
