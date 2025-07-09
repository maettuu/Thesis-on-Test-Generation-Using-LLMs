import docker
import io
import tarfile
import re
import json
import logging
import shlex

from docker.errors import ImageNotFound, APIError, BuildError
from docker.models.containers import Container
from pathlib import Path

from webhook_handler.core.execution_error import ExecutionError
from webhook_handler.data_models.pr_data import PullRequestData


logger = logging.getLogger(__name__)


class DockerService:
    """
    Used for Docker operations.
    """
    def __init__(
            self,
            project_root: str,
            old_repo_state: bool,
            pr_data: PullRequestData,
            pdf_name: str,
            pdf_content: bytes
    ):
        self._project_root = project_root
        self._old_repo_state = old_repo_state
        self._pr_data = pr_data
        self._pdf_name = pdf_name
        self._pdf_content = pdf_content
        self._client = docker.from_env()

    def build(self):
        """
        Builds a Docker image using the Python Docker SDK.
        """

        image_tag = self._pr_data.image_tag
        build_succeeded = False

        try:
            self._client.images.get(f"{image_tag}:latest")
            logger.info(f"Docker image '{image_tag}' already exists – skipped")
            return
        except ImageNotFound:
            logger.warning(f"No existing image '{image_tag}' found")
        except APIError as e:
            logger.error(f"Docker API error when checking for existing image: {e}")

        logger.info(f"Building from scratch based on commit {self._pr_data.base_commit}")
        dockerfile_path = Path("dockerfiles", f"Dockerfile_{self._pr_data.repo}_old").as_posix() \
            if self._old_repo_state \
            else Path("dockerfiles", f"Dockerfile_{self._pr_data.repo}").as_posix()
        try:
            self._client.images.build(
                path=self._project_root,
                tag=f"{self._pr_data.image_tag}:latest",
                dockerfile=dockerfile_path,
                buildargs={"commit_hash": self._pr_data.base_commit},
                network_mode="host",
                rm=True
            )
            build_succeeded = True
            logger.success(f"Docker image '{self._pr_data.image_tag}' built successfully")
        except BuildError as e:
            log_lines = []
            for chunk in e.build_log:
                if 'stream' in chunk:
                    log_lines.append(chunk['stream'].rstrip())
            full_build_log = "\n".join(log_lines)
            logger.critical(f"Build failed for image '{image_tag}':\n{full_build_log}")
            raise ExecutionError("Docker build failed")
        except APIError as e:
            logger.critical(f"Docker API error: {e}")
            raise ExecutionError("Docker API error")
        finally:
            if not build_succeeded:
                logger.info("Cleaning up leftover containers and dangling images...")
                for container in self._client.containers.list(all=True):
                    img = container.image.tags or container.image.id
                    if img == '<none>:<none>' or not container.image.tags:
                        try:
                            if container.status == 'running':
                                container.stop()
                            container.remove()
                        except APIError as stop_err:
                            logger.error(f"Failed to remove container {container.id[:12]}: {stop_err}")
                try:
                    dangling = self._client.images.list(filters={'dangling': True})
                    for img in dangling:
                        try:
                            self._client.images.remove(image=img.id, force=True)
                        except APIError as img_err:
                            logger.error(f"Failed to remove image {img.id[:12]}: {img_err}")
                except APIError as list_err:
                    logger.error(f"Error listing dangling images: {list_err}")

    def run_test_in_container(
            self,
            test_patch: str,
            tests_to_run: list,
            added_test_file: str,
            golden_code_patch: str = None
    ) -> [bool, str]:
        """
        Creates a container, applies the patch, runs the test, and returns the result.

        Parameters:
            test_patch (str): Patch to apply to the model test
            tests_to_run (list): List of tests to run
            added_test_file (str): Path to the file to add to the added tests
            golden_code_patch (str): Patch content for source code

        Returns:
            bool: True if the test has passed, False otherwise
            str: The output from running the test
        """

        try:
            logger.info("Creating container...")
            container = self._client.containers.create(
                image=self._pr_data.image_tag,
                command="/bin/sh -c 'sleep infinity'",  # keep the container running
                tty=True,  # allocate a TTY for interactive use
                detach=True
            )
            container.start()
            logger.success(f"Container {container.short_id} started")

            # check if the test file is already in the container, add stub otherwise (new file)
            added_file_exists = container.exec_run(f"/bin/sh -c 'test -f /app/testbed/{added_test_file}'")
            if added_file_exists.exit_code != 0:
                self._add_file_to_container(container, added_test_file)
                self._whitelist_stub(container, added_test_file.split("/")[-1])

            # check for gulpfile version (mjs or js)
            gulpfile_pointer = "gulpfile.mjs"
            gulpfile_exists = container.exec_run(f"/bin/sh -c 'test -f /app/testbed/{gulpfile_pointer}'")
            if gulpfile_exists.exit_code != 0:
                gulpfile_pointer = "gulpfile.js"
                old_gulpfile_exists = container.exec_run(f"/bin/sh -c 'test -f /app/testbed/{gulpfile_pointer}'")
                if old_gulpfile_exists.exit_code != 0:
                    logger.critical("No gulpfile found")
                    raise ExecutionError("No gulpfile found")

            # add mock PDF if available
            if self._pdf_name and self._pdf_content:
                self._add_file_to_container(container, f"test/pdfs/{self._pdf_name}", self._pdf_content)

            self._copy_and_apply_patch(
                container,
                patch_content=test_patch,
                patch_name="test_patch.diff"
            )
            if golden_code_patch is not None:
                self._copy_and_apply_patch(
                    container,
                    patch_content=golden_code_patch,
                    patch_name="golden_code_patch.diff"
                )
            stdout = self._run_test(container, gulpfile_pointer, tests_to_run)
            test_passed = self._evaluate_test(stdout)
            return test_passed, stdout
        finally:
            logger.warning("Stopping and removing container...")
            container.stop()
            container.remove()
            logger.success("Container stopped and removed")

    @staticmethod
    def _add_file_to_container(container: Container, file_path: str, file_content: str | bytes = "") -> None:
        """
        Adds file to Docker container.

        Parameters:
            container (Container): Container to add file to
            file_path (str): Path to the file to add to the container
            file_content (str | bytes, optional): Content to add to the file
        """

        if isinstance(file_content, str):
            content = file_content.encode("utf-8")
        else:
            content = file_content

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            ti = tarfile.TarInfo(name=file_path)
            ti.size = len(file_content)
            tar.addfile(ti, io.BytesIO(content))
        tar_stream.seek(0)
        try:
            container.put_archive("/app/testbed", tar_stream.read())
            logger.success(f"File {file_path} added to container successfully")
        except APIError as e:
            logger.critical(f"Docker API error: {e}")
            raise ExecutionError("Docker API error")

    def _whitelist_stub(self, container: Container, file_name: str) -> None:
        """
        Adds the new file to the whitelist for it to be detectable by Jasmine.

        Parameters:
            container (Container): Container to modify whitelist in
            file_name (str): Name of the file to add to the whitelist
        """

        whitelist_path = "test/unit/clitests.json"
        read = container.exec_run(f"/bin/sh -c 'cd /app/testbed && cat {whitelist_path}'")
        if read.exit_code != 0:
            logger.critical(f"Could not read clitests.json: {read.output.decode()}")
            raise ExecutionError("Failed to whitelist stub")

        whitelist = json.loads(read.output.decode())
        if file_name not in whitelist["spec_files"]:
            whitelist["spec_files"].append(file_name)
            updated_whitelist = json.dumps(whitelist, indent=2) + "\n"
            self._add_file_to_container(container, whitelist_path, updated_whitelist)

    def _copy_and_apply_patch(self, container: Container, patch_content: str, patch_name: str) -> None:
        """
        Copies file to container and applies patch.

        Parameters:
            container (Container): Container to apply patch
            patch_content (str): Patch to apply to the container
            patch_name (str): Name of the path file
        """
        self._add_file_to_container(container, patch_name, patch_content)

        # Apply the patch inside the container
        apply_patch_cmd = f"/bin/sh -c 'cd /app/testbed && patch -p1 < {patch_name}'"
        exec_result = container.exec_run(apply_patch_cmd)

        if exec_result.exit_code != 0:
            logger.critical(f"Failed to apply patch: {exec_result.output.decode()}")
            raise ExecutionError("Failed to apply patch")

        logger.success(f"Patch file /app/testbed/{patch_name} applied successfully")

    @staticmethod
    def _run_test(container: Container, gulpfile_pointer: str, tests_to_run: list) -> str:
        """
        Runs tests in container.

        Parameters:
            container (Container): Container to run test
            gulpfile_pointer (str): Determines whether to use gulpfile.mjs or gulpfile.js
            tests_to_run (list): List of tests to run

        Returns:
            str: The test output
        """

        test_commands = []
        for desc in tests_to_run:
            inner = f"TEST_FILTER='{desc}' npx gulp --gulpfile {gulpfile_pointer} unittest-single"
            test_single = shlex.quote(inner)
            cmd = f"timeout 300 /bin/sh -c {test_single}"
            test_commands.append(cmd)

        joined_cmds = " && ".join(test_commands)

        cd_test = shlex.quote(f"cd /app/testbed && {joined_cmds}")

        full_test_command = (
            "/bin/sh -c "
            f"{cd_test}"
        )

        logger.info("Running test command...")
        exec_result = container.exec_run(full_test_command, stdout=True, stderr=True)
        output = exec_result.output.decode()
        if exec_result.exit_code == 124:
            logger.warning("Test command killed by timeout")
        else:
            pattern = re.compile(
                r'^Ran\s+\d+\s+of\s+\d+\s+specs?\r?\n\d+\s+specs?,\s+\d+\s+failures?$',
                re.MULTILINE
            )
            if pattern.search(output):
                logger.success("Test command executed")
            else:
                logger.error("Test command failed")

        return exec_result.output.decode()

    @staticmethod
    def _evaluate_test(stdout: str) -> bool:
        """
        Evaluates test output.

        Parameters:
            stdout (str): Output of test command

        Returns:
            bool: True if the test has passed, False otherwise
        """

        if re.search(r'\b0\s+specs\b', stdout):  # no tests were executed
            logger.warning("No tests were executed")
            test_passed = False
        else:
            match = re.search(r'\b(\d+)\s+failures?\b', stdout)  # extract the number of failures
            if match:
                num_failures = int(match.group(1))
                test_passed = True if num_failures == 0 else False
            else:
                logger.error("Test could not be evaluated")
                return False

        logger.info(f"Test evaluated as passed") if test_passed else logger.fail(f"Test evaluated as failed")
        return test_passed
