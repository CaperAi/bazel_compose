from threading import Thread
from typing import List, Dict

from caper.bazel_compose.bazel import Bazel, BuildFinishedEvent
from caper.bazel_compose.compose import BazelComposeFile, DockerCompose


class BuildWatcher(Thread):
    def __init__(self, bazel: Bazel, compose_file: BazelComposeFile, compose: DockerCompose):
        super().__init__(name="BuildWatcher")
        self.bazel = bazel
        self.compose_file = compose_file
        self.compose = compose

    def services_with_target(self, target: str) -> List[str]:
        target_normalized = self.bazel.target_normalize(target)
        return [
            service
            for service in self.compose_file.bazel_services()
            if target_normalized == self.bazel.target_normalize(self.compose_file.bazel_service_target(service))
        ]

    def run(self) -> None:
        for build_event in self.bazel.watch_build(self.compose_file.bazel_image_targets()):
            # Tag all of the before restarting everything
            try:
                tags = {
                    target: self.bazel.target_image_tag(target)
                    for target in build_event.targets
                }
            except Exception as e:
                print("failed to tag image:", e)
                continue

            service_image_changes = {}

            for service_name in self.compose_file.bazel_services():
                target = self.compose_file.bazel_service_target(service_name)
                if target in tags:
                    service_image_changes[service_name] = tags[target]

            for service_name, image_tag in service_image_changes.items():
                self.compose_file.update_image(service_name, image_tag)

            # Restart all of the services
            try:
                self.compose_file.save()
                self.compose.up(*service_image_changes.keys())
            except Exception as e:
                print("failed to restart services:", e)
                continue
