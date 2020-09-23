import subprocess
from collections import defaultdict
from typing import Optional, Generator, List, Dict
import json
from pprint import pprint

class BuildFinishedEvent:
    # {
    #   "type": "BUILD_DONE",
    #   "iteration": "1faceb0972d62d5d",
    #   "time": 1600578356346,
    #   "targets": ["//caper/platform/longbow:longbow_image.digest"],
    #   "elapsed":6393
    #   }
    def __init__(self, targets: List[str]):
        self.targets = targets


class Bazel:
    def __init__(self, ibazel: str = "ibazel", bazel: str = "bazel", cwd: str = "."):
        self.ibazel = ibazel
        self.bazel = bazel
        self.cwd = cwd

    def __call_ibazel(self, *args, **kwargs):
        return subprocess.Popen([self.ibazel, *args], cwd=self.cwd, **kwargs)

    def __call_bazel(self, *args, **kwargs):
        popen_args = {
            "stderr": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            **kwargs
        }
        return subprocess.Popen([self.bazel, *args], cwd=self.cwd, **popen_args)

    @staticmethod
    def target_normalize(target: str):
        """
        Turn a target like `//something:something.digest` into `//something`
        :param target:
        :return:
        """

        if ':' in target:
            folder, file = target.split(":")
        else:
            folder, file = target, target[target.rfind('/') + 1:]

        if file.endswith(".digest"):
            file = file.replace(".digest", "")

        if file == folder[folder.rfind('/') + 1:]:
            # This was a target in the form of //something:something which normalizes to //something
            return folder
        else:
            # This was a target in the form of //something:something_else
            return f"{folder}:{file}"

    @staticmethod
    def target_digest_target(target: str):
        """
        Find the bazel target for the provided image target's digest file. The digest file is a sha256 hash of the image
        when it is pushed into a remote registry. This allows you to "fingerprint" an image and identify when it has
        changed.
        :param target:
        :return:
        """

        # Normalize the target
        target = Bazel.target_normalize(target)

        if ':' in target:
            folder, file = target.split(":")
        else:
            folder, file = target, target[target.rfind('/') + 1:]

        if not file.endswith(".digest"):
            file += '.digest'

        return f"{folder}:{file}"

    def target_digest(self, target: str):
        # Find the real target digest for this.
        target = Bazel.target_digest_target(target)

        # Remove //
        # TODO(josh): Handle external containers from container_pull rules.
        target = target[2:]

        if ':' in target:
            folder, file = target.split(":")
        else:
            folder, file = target, target[target.rfind('/') + 1:]

        if not file.endswith(".digest"):
            file += '.digest'

        with open(f"{self.cwd}/bazel-bin/{folder}/{file}") as i:
            return i.read()

    def target_image_tag(self, target: str):
        """
        Find the image tag for a target. This causes the target to be run and loaded into the docker daemon of the host
        system. This call may be very slow.
        :param target: Bazel target to run.
        :return:
        """
        process = self.__call_bazel("run", target, "--", "--norun", stdout=subprocess.PIPE)
        if process.returncode is not None:
            raise Exception("Failed to tag image from target=" + target)

        # Tagging c....9 as bazel/caper/platform/longbow:longbow_image

        image_tag = None
        for line in map(lambda b: b.decode(), iter(process.stdout.readline, b'')):
            if not line.startswith("Tagging "):
                continue
            parts = line.strip().split()
            image_tag = parts[-1]

        if image_tag is None:
            raise Exception("Never tagged image during run of target=" + target)
        return image_tag

    def changed_digests(self, old_digests: Dict[str, str], targets: List[str]) -> dict:
        changed: Dict[str, str] = {}
        for target in targets:
            digest = self.target_digest(target)

            if old_digests[target] != digest:
                changed[target] = digest

        return changed

    def watch_build(self, targets: List[str]) -> Generator[BuildFinishedEvent, None, None]:
        """
        Tail all logs
        :return:
        """
        # Example of the kind of command we are attempting to build:
        #   ibazel -log_to_file /dev/null -profile_dev /dev/stdout build //caper/platform/longbow:longbow_image.digest
        process = self.__call_ibazel(
            # Turn off all logging from ibazel
            "-log_to_file", "/dev/null",

            # Pipe all of the logs for build events into standard output so we can read these while also making sure
            # the child process (ibazel) has not died.
            "-profile_dev", "/dev/stdout",

            # Which target we want to build
            "build", *[self.target_digest_target(target) for target in targets],

            # We want to read from stdout
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        if process.returncode is not None:
            raise Exception("Failed to start ibazel for targets=", targets)

        digests: Dict[str, str] = defaultdict(str)

        for line in iter(process.stdout.readline, b''):
            event = json.loads(line.decode())
            # pprint(event)

            if event['type'] != 'BUILD_DONE':
                continue

            targets = [
                self.target_normalize(target)
                for target in event['targets']
            ]

            changes = self.changed_digests(digests, targets)

            if not changes:
                # print("Nothing changed")
                continue

            digests.update(changes)

            yield BuildFinishedEvent(targets=list(changes.keys()))
