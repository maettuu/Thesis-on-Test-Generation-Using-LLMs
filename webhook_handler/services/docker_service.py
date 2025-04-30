import docker
import sys
import tempfile
import io
import tarfile
import re
import os

from docker.errors import ImageNotFound, APIError, BuildError
from pathlib import Path

from webhook_handler.core.config import Config
from webhook_handler.data_models.pr_data import PullRequestData


class DockerService:
    def __init__(self, config: Config, pr_data: PullRequestData, logger, dockerfile_path: str = None):
        self.config = config
        self.pr_data = pr_data
        self.logger = logger
        self.dockerfile_path = self._get_dockerfile(dockerfile_path)
        self.client = docker.from_env()

    def _get_dockerfile(self, dockerfile_path: str) -> str:
        if dockerfile_path:
            return dockerfile_path
        if (self.pr_data.owner, self.pr_data.repo, self.pr_data.number) == ("kitsiosk", "bugbug", 5):
            return Path("dockerfiles", "Dockerfile_bugbug_old1").as_posix()
        return Path("dockerfiles", f"Dockerfile_{self.pr_data.repo}").as_posix()

    def build(self):
        """Builds a Docker image using the Python Docker SDK."""

        # # Read the modified Dockerfile content
        # dockerfile_content = read_dockerfile(commit_hash, dockerfile_path)

        # # Write a temporary Dockerfile (this avoids modifying the original file)
        # temp_dockerfile = "Dockerfile.temp"
        # with open(temp_dockerfile, "w", encoding="utf-8") as f:
        #     f.write(dockerfile_content)

        image_tag = self.pr_data.image_tag

        # Check whether the image is already built
        try:
            self.client.images.get(f"{image_tag}:latest")
            self.logger.info(f"[+] Docker image '{image_tag}' already exists – skipped")
            return
        except ImageNotFound:
            # image not found locally, proceed with build
            self.logger.info(f"[!] No existing image '{image_tag}' found.")
        except APIError as e:
            self.logger.error(f"[!] Docker API error when checking for existing image: {e}")

        self.logger.info(f"[*] Building from scratch based on commit {self.pr_data.base_commit}")

        # Build the Docker image
        build_args = {"commit_hash": self.pr_data.base_commit}
        try:
            image, build_logs = self.client.images.build(
                path=self.config.project_root.as_posix(),
                tag=self.pr_data.image_tag,
                dockerfile=self.dockerfile_path,
                buildargs=build_args,
                network_mode="host",
                rm=True
            )

            # # Print build logs
            # for log in build_logs:
            #     if "stream" in log:
            #         print(log["stream"].strip())
            self.logger.info(f"[+] Docker image '{self.pr_data.image_tag}' built successfully.")
        except BuildError as e:
            # Print every line from the build logs to stdout/stderr
            for chunk in e.build_log:
                if 'stream' in chunk:
                    print(chunk['stream'].rstrip())
            self.logger.info(f"[!] Build failed: {e}")
            sys.exit(1)
        # except BuildError as e:
        #     self.logger.info(f"[!] Build failed: {e}")
        #     sys.exit(1)
        except APIError as e:
            self.logger.info(f"[!] Docker API error: {e}")
            sys.exit(1)

    def run_test_in_container(self, model_test_patch, tests_to_run, golden_code_patch=None):
        """Creates a container, applies the patch, runs the test, and returns the result."""

        # Create a temporary patch file
        with tempfile.NamedTemporaryFile(delete=False, mode="w", newline='\n') as patch_file:
            patch_file.write(model_test_patch)
            patch_file_path = patch_file.name

        try:
            self.logger.info("[*] Creating container...")
            container = self.client.containers.create(
                image=self.pr_data.image_tag,
                command="/bin/sh -c 'sleep infinity'",  # Keep the container running
                tty=True,  # Allocate a TTY for interactive use
                detach=True
            )

            container.start()
            self.logger.info(f"[+] Container {container.short_id} started.")

            #### A) Test patch (Always)
            model_test_patch_fname = "test_patch.diff"
            patch_dest_path = f"/app/testbed/{model_test_patch_fname}"
            # Create a tar archive
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tar.add(patch_file_path, arcname=model_test_patch_fname)
            tar_stream.seek(0)
            # Copy the tar archive to the container
            container.put_archive("/app/testbed", tar_stream.getvalue())
            self.logger.info(f"[+] Patch file copied to {patch_dest_path}")

            # Apply the patch inside the container
            apply_patch_cmd = f"/bin/sh -c 'cd /app/testbed && git apply {model_test_patch_fname}'"
            exec_result = container.exec_run(apply_patch_cmd)

            if exec_result.exit_code != 0:
                self.logger.info(f"[!] Failed to apply patch: {exec_result.output.decode()}")
                return "ERROR", exec_result.output.decode()

            self.logger.info("[+] Test patch applied successfully.")

            if golden_code_patch is not None:

                # Create a temporary patch file
                with tempfile.NamedTemporaryFile(delete=False, mode="w", newline='\n') as patch_file:
                    patch_file.write(golden_code_patch)
                    patch_file_path = patch_file.name

                #### B) Model patch (Only in post-PR code)
                golden_code_patch_fname = "golden_code_patch.diff"
                patch_dest_path = f"/app/testbed/{golden_code_patch_fname}"
                # Create a tar archive
                tar_stream = io.BytesIO()
                with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                    tar.add(patch_file_path, arcname=golden_code_patch_fname)
                tar_stream.seek(0)
                # Copy the tar archive to the container
                container.put_archive("/app/testbed", tar_stream.getvalue())
                self.logger.info(f"[+] Patch file copied to {patch_dest_path}")

                # Apply the patch inside the container
                apply_patch_cmd = f"/bin/sh -c 'cd /app/testbed && git apply {golden_code_patch_fname}'"
                exec_result = container.exec_run(apply_patch_cmd)

                if exec_result.exit_code != 0:
                    self.logger.info(f"[!] Failed to apply patch: {exec_result.output.decode()}")
                    return "ERROR", exec_result.exit_code

                self.logger.info("[+] Code patch applied successfully.")

            # Run the test command
            coverage_report_separator = "COVERAGE_REPORT_STARTING_HERE"
            test_commands = [
                f'npx nyc --reporter=text --reporter=lcov jasmine --filter="{desc}" {file}'
                # f'npx nyc --all --no-source-map --reporter=text --reporter=lcov jasmine --filter="{desc}" {file}'
                for desc, file in tests_to_run.items()
            ]
            test_command = (
                "/bin/sh -c 'cd /app/testbed && "
                f"{' ; '.join(test_commands)} ; "
                "npx nyc report --reporter=text > coverage_report.txt && "
                f"echo '{coverage_report_separator}' && "
                "cat coverage_report.txt'"
            )
            self.logger.info("[*] Running test command...")
            exec_result = container.exec_run(test_command, stdout=True, stderr=True)
            stdout_output_all = exec_result.output.decode()
            try:  # TODO: fix, find a better way to handle the "test-not-ran" error
                stdout, coverage_report = stdout_output_all.split(coverage_report_separator)
            except:
                self.logger.info("Internal error: docker command failed with: %s" % stdout_output_all)
            self.logger.info("[+] Test command executed.")

            # Extract only the number of failures from the output.
            match = re.search(r'\b(\d+)\s+failures?\b', stdout)
            if match:
                num_failures = int(match.group(1))
                test_result = "PASS" if num_failures == 0 else "FAIL"
            else:
                # If the summary line cannot be found, consider it a failure (or handle as needed)
                self.logger.info("Could not determine test summary from output.")
                test_result = "FAIL"

            self.logger.info(f"[+] Test result: {test_result}")

            return test_result, stdout, coverage_report

        finally:
            # Cleanup
            self.logger.info("[*] Stopping and removing container...")
            os.remove(patch_file_path)
            container.stop()
            container.remove()
            self.logger.info("[+] Container stopped and removed.")