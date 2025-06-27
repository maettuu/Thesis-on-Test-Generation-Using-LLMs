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

from scrape_handler.core.execution_error import ExecutionError
from scrape_handler.data_models.pr_data import PullRequestData


logger = logging.getLogger(__name__)


class DockerService:
    """
    Used for Docker operations.
    """
    def __init__(self, project_root: str, pr_data: PullRequestData):
        self._project_root = project_root
        self._pr_data = pr_data
        self._client = docker.from_env()

    def build(self):
        """
        Builds a Docker image using the Python Docker SDK.
        """

        image_tag = self._pr_data.image_tag
        try:
            self._client.images.get(f"{image_tag}:latest")
            logger.info(f"Docker image '{image_tag}' already exists – skipped")
            return
        except ImageNotFound:
            logger.warning(f"No existing image '{image_tag}' found")
        except APIError as e:
            logger.error(f"Docker API error when checking for existing image: {e}")

        logger.info(f"Building from scratch based on commit {self._pr_data.base_commit}")
        try:
            self._client.images.build(
                path=self._project_root,
                tag=f"{self._pr_data.image_tag}:latest",
                dockerfile=Path("dockerfiles", f"Dockerfile_{self._pr_data.repo}").as_posix(),
                buildargs={"commit_hash": self._pr_data.base_commit},
                network_mode="host",
                rm=True
            )
            logger.success(f"Docker image '{self._pr_data.image_tag}' built successfully")
        except BuildError as e:
            for chunk in e.build_log:
                if 'stream' in chunk:
                    print(chunk['stream'].rstrip())
            logger.critical(f"Build failed: {e}")
            raise ExecutionError(f'Docker build failed')
        except APIError as e:
            logger.critical(f"Docker API error: {e}")
            raise ExecutionError('Docker API error')

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
            test_patch: Patch to apply to the model test
            tests_to_run: List of tests to run
            added_test_file: Path to the file to add to the added tests
            golden_code_patch: Path to the file to add to the golden code

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

            # check if the test file is already in the container, add stub otherwise
            exists = container.exec_run(f"/bin/sh -c 'test -f /app/testbed/{added_test_file}'")
            if exists.exit_code != 0:
                self._add_file_to_container(container, added_test_file)
                self._whitelist_stub(container, added_test_file.split("/")[-1])

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
            stdout = self._run_test(container, tests_to_run)
            test_passed = self._evaluate_test(stdout)
            return test_passed, stdout
        finally:
            logger.warning("Stopping and removing container...")
            container.stop()
            container.remove()
            logger.success("Container stopped and removed")

    @staticmethod
    def _add_file_to_container(container: Container, file_path: str, file_content: str = "") -> None:
        """
        Adds file to Docker container.

        Parameters:
            container (Container): Container to add file to
            file_path (str): Path to the file to add to the container
            file_content (str): Content to add to the file

        Returns:
            None
        """

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            ti = tarfile.TarInfo(name=file_path)
            ti.size = len(file_content)
            tar.addfile(ti, io.BytesIO(file_content.encode("utf-8")))
        try:
            container.put_archive("/app/testbed", tar_stream.getvalue())
        except APIError as e:
            logger.critical(f"Docker API error: {e}")
            raise ExecutionError('Docker API error')

    def _whitelist_stub(self, container: Container, file_name: str) -> None:
        """
        Adds the new file to the whitelist for it to be detectable by Jasmine.

        Parameters:
            container (Container): Container to modify whitelist in
            file_name (str): Name of the file to add to the whitelist

        Returns:
            None
        """

        whitelist_path = "test/unit/clitests.json"
        read = container.exec_run(f"/bin/sh -c 'cd /app/testbed && cat {whitelist_path}'")
        if read.exit_code != 0:
            logger.critical(f"Could not read clitests.json: {read.output.decode()}")
            raise ExecutionError('Failed to whitelist stub')

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

        Returns:
            None
        """
        self._add_file_to_container(container, patch_name, patch_content)
        logger.info(f"Patch file copied to /app/testbed/{patch_name}")

        # Apply the patch inside the container
        apply_patch_cmd = f"/bin/sh -c 'cd /app/testbed && patch -p1 < {patch_name}'"
        exec_result = container.exec_run(apply_patch_cmd)

        if exec_result.exit_code != 0:
            logger.critical(f"Failed to apply patch: {exec_result.output.decode()}")
            raise ExecutionError('Failed to apply patch')

        logger.success("Patch applied successfully")

    @staticmethod
    def _run_test(container: Container, tests_to_run: list) -> str:
        """
        Runs tests in container.

        Parameters:
            container (Container): Container to run test
            tests_to_run (list): List of tests to run

        Returns:
            str: The test output
        """

        test_commands = []
        for desc in tests_to_run:
            inner = f"TEST_FILTER='{desc}' npx gulp unittest-single"
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
        if exec_result.exit_code == 0:
            logger.success("Test command executed")
        elif exec_result.exit_code == 124:
            logger.warning("Test command killed by timeout")
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
