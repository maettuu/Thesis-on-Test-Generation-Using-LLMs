import json
import hmac
import hashlib
import docker
import logging

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse, HttpResponseNotAllowed
from pathlib import Path
from docker.errors import ImageNotFound

from webhook_handler.core import (
    Config,
    configure_logger,
    ExecutionError,
    helpers
)
from .pipeline import run
from webhook_handler.data_models import LLM
from webhook_handler.data_models import PullRequestData


#################### Webhook ####################
@csrf_exempt
def github_webhook(request):
    """
    Handles GitHub webhook events.

    Parameters:
        request (django.http.HttpRequest): The HTTP request

    Returns:
        django.http.HttpResponse: The HTTP response
    """

    # 1) Initialize config
    config = Config()

    # 2) Fetch bootstrap logger
    bootstrap = logging.getLogger("bootstrap")
    bootstrap.info("Received GitHub webhook event")

    # 3) Allow HEAD for health checks
    if request.method == 'HEAD':
        bootstrap.info("HEAD request")
        return HttpResponse(status=200)

    # 4) Enforce POST only
    if request.method != 'POST':
        bootstrap.info("Not a POST request")
        return HttpResponseNotAllowed(['POST'], 'Only POST method is allowed')

    # 5) GitHub signature check
    if not _verify_signature(request, config.github_webhook_secret):
        bootstrap.warning("Signature verification failed")
        return HttpResponseForbidden("Invalid signature")

    # 6) Empty payload check
    payload = json.loads(request.body)
    if not payload:
        bootstrap.warning("Payload is empty")
        return HttpResponseForbidden("Empty payload")

    # 7) Pull request event check
    event = request.headers.get('X-GitHub-Event')
    if event != "pull_request":
        bootstrap.info("Webhook event is not a pull request")
        return JsonResponse({'status': 'success', 'message': 'Webhook event is not a pull request'}, status=200)

    # 8) Pull request action check
    if payload.get('action') != 'opened':
        bootstrap.info("Pull request action is not opened")
        return JsonResponse({'status': 'success', 'message': 'Pull request action is not opened'}, status=200)

    # 9) All checks passed, cleanup & prepare
    bootstrap.info("Starting pipeline execution...")
    helpers.remove_dir(Path(config.cloned_repo_dir))
    executed_tests = Path(config.bot_log_dir, "executed_tests.txt")
    executed_tests.touch(exist_ok=True)
    if not Path(config.bot_log_dir, 'results.csv').exists():
        Path(config.bot_log_dir, 'results.csv').write_text(
            "{:<9},{:<30},{:<9},{:<45}\n".format("prNumber", "model", "iAttempt", "stop"),
            encoding="utf-8"
        )
    stop = False
    response = JsonResponse({'status': 'success', 'message': 'No tests generated'}, status=200)
    post_comment = True
    models = [LLM.GPT4o, LLM.LLAMA, LLM.DEEPSEEK]
    pr_data = PullRequestData.from_payload(payload)
    config.setup_pr_log_dir(pr_data.id)
    execution_id = f"pdf_js_{pr_data.number}"
    configure_logger(config.pr_log_dir, execution_id)
    logger = logging.getLogger()

    # 10) Run pipeline
    logger.marker(f"=============== Running Payload #{pr_data.number} ===============")
    for model in models:
        i_attempt = 0
        while i_attempt < len(config.prompt_combinations["include_golden_code"]) and not stop:
            config.setup_output_dir(i_attempt, model)
            logger.marker("Starting combination %d with model %s" % (i_attempt + 1, model))
            try:
                response, stop = run(pr_data,
                                     config,
                                     model=model,
                                     i_attempt=i_attempt,
                                     post_comment=post_comment)
                logger.success(f"Combination %d with model %s finished successfully" % (i_attempt + 1, model))
                _record_result(config.bot_log_dir, payload["number"], model, i_attempt + 1, stop)
            except ExecutionError as e:
                _record_result(config.bot_log_dir, payload["number"], model, i_attempt + 1, str(e))
            except Exception as e:
                logger.critical("Failed with unexpected error:\n%s" % e)
                _record_result(config.bot_log_dir, payload["number"], model, i_attempt + 1, "unexpected error")

            if stop:
                post_comment = False
                gen_test = Path(config.output_dir, "generation", "generated_test.txt").read_text(encoding="utf-8")
                new_filename = f"{execution_id}_{config.output_dir.name}.txt"
                Path(config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
                logger.success(f"Test file copied to {config.gen_test_dir}/{new_filename}")

            i_attempt += 1

    # if not stop:
    #     model = LLM.GPTo4_MINI
    #     config.setup_output_dir(0, model)
    #     logger.marker("Starting with model o4-mini")
    #     try:
    #         response, stop = run(pr_data,
    #                              config,
    #                              model=model,
    #                              i_attempt=0,
    #                              post_comment=post_comment)
    #         logger.success("o4-mini finished successfully")
    #         _record_result(config.bot_log_dir, payload["number"], model, 1, stop)
    #     except ExecutionError as e:
    #         _record_result(config.bot_log_dir, payload["number"], model, 1, str(e))
    #     except Exception as e:
    #         logger.critical("Failed with unexpected error:\n%s" % e)
    #         _record_result(config.bot_log_dir, payload["number"], model, 1, "unexpected error")
    #
    #     if stop:
    #         post_comment = False
    #         gen_test = Path(self.config.output_dir, "generation", "generated_test.txt").read_text(encoding="utf-8")
    #         new_filename = f"{self.execution_id}_{self.config.output_dir.name}.txt"
    #         Path(self.config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
    #         logger.success(f"Test file copied to {self.config.gen_test_dir}/{new_filename}")

    logger.marker(f"=============== Finished Payload #{pr_data.number} ===============")
    helpers.remove_dir(Path(config.cloned_repo_dir), log_success=True)
    image_tag = f"{pr_data.image_tag}:latest"
    try:
        client = docker.from_env()
        client.images.remove(image=image_tag, force=True)
        logger.success(f"Removed Docker image '{image_tag}'")
    except ImageNotFound:
        logger.error(f"Tried to remove image '{image_tag}', but it was not found")
    except Exception as e:
        logger.error(f"Failed to remove Docker image '{image_tag}': {e}")
    with executed_tests.open("a", encoding='utf-8') as f:
        f.write(f"{execution_id}\n")

    bootstrap.info("Pipeline execution completed.")
    return response


def _verify_signature(request, github_webhook_secret) -> bool:
    """
    Verifies the webhook signature.

    Parameters:
        request (django.http.HttpRequest): The HTTP request
        github_webhook_secret (str): The webhook secret

    Returns:
        bool: True if the webhook signature is valid, False otherwise
    """

    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return False
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    mac = hmac.new(github_webhook_secret.encode(), msg=request.body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)  # valid if the two encodings are the same


def _record_result(log_dir: str | Path, number: str, model: LLM, i_attempt: int, stop: bool | str):
    """
    Writes result to csv.

    Parameters:
        log_dir (str, Path): Path to log directory
        number (str): The number of the PR
        model (LLM): The model
        i_attempt (int): The attempt number
        stop (bool, str): The stop flag or an error string
    """

    with open(Path(log_dir, 'results.csv'), 'a') as f:
        f.write(
            "{:<9},{:<30},{:<9},{:<45}\n".format(number, model, i_attempt, stop)
        )
