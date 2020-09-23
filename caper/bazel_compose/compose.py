import subprocess
from typing import Optional, List
from os.path import exists

import yaml
from functools import lru_cache
from pathlib import Path


class BazelComposeFile:
    def __init__(self, cwd: str = ".", base_file_name="docker-compose.yml", file_name="bazel-compose.yml", output_file_name="docker-compose-generated.yml"):
        self.cwd = cwd
        self.base_file_name = None

        path = Path(cwd)

        base_file_path = path / base_file_name
        if base_file_path.exists():
            self.base_file_name = str(base_file_path)

        self.output_file_name = str(path / output_file_name)
        file_name = str(path / file_name)

        self.data = self.__load(file_name)

        # This copy of the data is written to. We copy this structure to make it so we don't need to do anything fancy
        # in this class for remembering what depends on what. It's 2am now so that's probably why I think this is ok.
        # TODO(josh): Pre-calculate deps
        self.modified_copy = self.__load(file_name)

    @staticmethod
    def __load(file_name: str):
        with open(file_name) as i:
            # TODO(josh): Investigate https://pypi.org/project/ruamel.yaml/#description to preserve comments
            return yaml.full_load(i)

    @staticmethod
    def __is_bazel_image_tag(tag: str):
        return tag.startswith("//")

    @lru_cache
    def bazel_services(self) -> List[str]:
        """
        Identify all services that contain bazel image tags in the service's `image: ...` property.
        :return:
        """
        return [
            name
            for name, definition in self.data['services'].items()
            if 'image' in definition and self.__is_bazel_image_tag(definition['image'])
        ]

    @lru_cache
    def bazel_service_target(self, service: str) -> Optional[str]:
        if service not in self.data['services']:
            raise Exception("Unknown service requested. service=" + service)

        data = self.data['services'][service]

        if 'image' not in data:
            return None

        return data['image']

    @lru_cache
    def bazel_image_targets(self) -> List[str]:
        """
        List all of the targets being used as bazel images.
        :return:
        """
        return [
            self.data['services'][service_name]['image']
            for service_name in self.bazel_services()
        ]

    def update_image(self, service_name: str, image_tag: str):
        self.modified_copy['services'][service_name]['image'] = image_tag

    def save(self):
        with open(self.output_file_name, "w") as output:
            yaml.dump(self.modified_copy, output)


class DockerCompose:
    def __init__(self, compose_file: BazelComposeFile, command: str = "docker-compose"):
        self.command = command
        self.compose_file = compose_file

    def __call(self, *args, **kwargs):
        command = [self.command]

        if self.compose_file.base_file_name is not None:
            if exists(self.compose_file.base_file_name):
                command += ["-f", self.compose_file.base_file_name]

        if exists(self.compose_file.output_file_name):
            command += ['-f', self.compose_file.output_file_name]

        cmd = [*command, *args]
        return subprocess.Popen(cmd, cwd=self.compose_file.cwd, **kwargs)

    def __null(self, *args):
        """
        Route standard input/output into /dev/null
        :param args:
        :return:
        """
        return self.__call(
            *args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

    def logs(self, *args):
        """
        Tail all logs
        :return:
        """
        if self.__call("logs", "-f", "--tail=0", *args).wait() != 0:
            print("...failed to watch logs")

    def up(self, *services, output_logs=False):
        call = self.__null if not output_logs else self.__call

        if call("up", "-d", *services).wait() != 0:
            raise Exception("Failed to restart services:", services)
