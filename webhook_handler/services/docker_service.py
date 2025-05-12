import docker
import sys
import io
import tarfile
import re
import json

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

        image_tag = self.pr_data.image_tag

        # Check whether the image is already built
        try:
            self.client.images.get(f"{image_tag}")
            self.logger.info(f"[+] Docker image '{image_tag}' already exists – skipped")
            return
        except ImageNotFound:
            try:
                self.client.images.get(f"{image_tag}:latest")
                self.logger.info(f"[+] Docker image '{image_tag}' already exists – skipped")
                return
            except ImageNotFound:
            # image not found locally, proceed with build
                self.logger.info(f"[!] No existing image '{image_tag}' found.")
            except APIError as e:
                self.logger.error(f"[!] Docker API error when checking for existing image: {e}")
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

    def run_test_in_container(self, model_test_patch, tests_to_run, added_test_file: str, golden_code_patch=None):
        """Creates a container, applies the patch, runs the test, and returns the result."""
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

            # Check if the test file is already in the container, add stub otherwise
            exists = container.exec_run(f"/bin/sh -c 'test -f /app/testbed/{added_test_file}'")
            if exists.exit_code != 0:
                self.add_file_to_container(container, added_test_file)
                self.whitelist_stub(container, added_test_file.split("/")[-1])

            self.copy_and_apply_patch(
                container,
                code_patch_content=model_test_patch,
                code_patch_name="test_patch.diff"
            )

            if golden_code_patch is not None:
                self.copy_and_apply_patch(
                    container,
                    code_patch_content=golden_code_patch,
                    code_patch_name="golden_code_patch.diff"
                )

            stdout, coverage_report = self.run_test(container, tests_to_run)
            test_result = self.evaluate_test(stdout)
            return test_result, stdout, coverage_report

        finally:
            # Cleanup
            self.logger.info("[*] Stopping and removing container...")
            container.stop()
            container.remove()
            self.logger.info("[+] Container stopped and removed.")

    @staticmethod
    def add_file_to_container(container, file_path, file_content: str = ""):
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            ti = tarfile.TarInfo(name=file_path)
            ti.size = len(file_content)
            tar.addfile(ti, io.BytesIO(file_content.encode("utf-8")))
        # Copy it into /app/testbed
        container.put_archive("/app/testbed", tar_stream.getvalue())

    def whitelist_stub(self, container, added_test_file):
        whitelist_path = "test/unit/clitests.json"
        read = container.exec_run(f"/bin/sh -c 'cd /app/testbed && cat {whitelist_path}'")
        if read.exit_code != 0:
            self.logger.warning(f"Could not read clitests.json: {read.output.decode()}")
            return "ERROR", read.exit_code, ""

        whitelist = json.loads(read.output.decode())
        if added_test_file not in whitelist["spec_files"]:
            whitelist["spec_files"].append(added_test_file)
            updated_whitelist = json.dumps(whitelist, indent=2) + "\n"
            self.add_file_to_container(container, whitelist_path, updated_whitelist)

    def copy_and_apply_patch(self, container, code_patch_content, code_patch_name):
        self.add_file_to_container(container, code_patch_name, code_patch_content)
        self.logger.info(f"[+] Patch file copied to /app/testbed/{code_patch_name}")

        # Apply the patch inside the container
        apply_patch_cmd = f"/bin/sh -c 'cd /app/testbed && git apply {code_patch_name}'"
        exec_result = container.exec_run(apply_patch_cmd)

        if exec_result.exit_code != 0:
            self.logger.info(f"[!] Failed to apply patch: {exec_result.output.decode()}")
            return "ERROR", exec_result.exit_code, ""

        self.logger.info("[+] Patch applied successfully.")

    def run_test(self, container, tests_to_run):
        coverage_report_separator = "COVERAGE_REPORT_STARTING_HERE"
        test_commands = [
            f'TEST_FILTER="{desc}" npx nyc gulp unittest-single'
            # f'npx nyc --all --no-source-map --reporter=text --reporter=lcov jasmine --filter="{desc}" {file}'
            for desc in tests_to_run
        ]
        test_command = (
            "/bin/sh -c 'cd /app/testbed && "
            f"{' ; '.join(test_commands)} ; "
            "npx nyc report --reporter=text > coverage_report.txt && "
            f"echo '{coverage_report_separator}' && "
            "cat coverage_report.txt'"
        )

        self.logger.info("[*] Running test command...")
        exec_result = container.exec_run(test_command, stdout=True, stderr=True, stream=True, demux=True, tty=False)
        stdout_chunks = []
        for out, err in exec_result.output:
            if out:
                text = out.decode(errors="ignore").rstrip()
                self.logger.info(text)
                stdout_chunks.append(text)
            if err:
                err_text = err.decode(errors="ignore").rstrip()
                self.logger.error(err_text)
        stdout_output_all = "\n".join(stdout_chunks)
        try:  # TODO: fix, find a better way to handle the "test-not-ran" error
            stdout, coverage_report = stdout_output_all.split(coverage_report_separator)
        except:
            self.logger.info("Internal error: docker command failed with: %s" % stdout_output_all)
        self.logger.info("[+] Test command executed.")

        return stdout, coverage_report

    def evaluate_test(self, stdout) -> str:
        if re.search(r'\b0\s+specs\b', stdout):  # No tests were executed
            test_result = "FAIL"
        else:
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
        return test_result
