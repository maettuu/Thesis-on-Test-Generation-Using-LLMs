import json
import hmac
import hashlib
import logging
import threading

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse, HttpResponseNotAllowed
from pathlib import Path

from webhook_handler.core import Config
from .pipeline import Pipeline


bootstrap = logging.getLogger("bootstrap")


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
    bootstrap.info("Received GitHub webhook event")

    # 3) Allow HEAD for health checks
    if request.method == 'HEAD':
        bootstrap.info("HEAD request")
        return HttpResponse(status=200)

    # 4) Enforce POST only
    if request.method != 'POST':
        bootstrap.info("Not a POST request")
        return HttpResponseNotAllowed(['POST'], 'Request method must be POST')

    # 5) GitHub signature check
    if not _verify_signature(request, config.github_webhook_secret):
        bootstrap.warning("Invalid signature")
        return HttpResponseForbidden("Invalid signature")

    # 6) Empty payload check
    payload = json.loads(request.body)
    if not payload:
        bootstrap.warning("Empty payload")
        return HttpResponseForbidden("Empty payload")

    # 7) Pull request event check
    event = request.headers.get('X-GitHub-Event')
    if event != "pull_request":
        bootstrap.info("Webhook event must be pull request")
        return JsonResponse({'status': 'success', 'message': 'Webhook event must be pull request'}, status=200)

    # 8) Pull request action check
    if payload.get('action') != 'opened':
        bootstrap.info("Pull request action must be OPENED")
        return JsonResponse({'status': 'success', 'message': 'Pull request action must be OPENED'}, status=200)

    # 9) Check for PR validity
    pipeline = Pipeline(payload, config, post_comment=True)
    response, valid = pipeline.is_valid_pr()
    if not valid:
        bootstrap.info(response['message'])
        return response

    def _execute_pipeline_in_background():
        try:
            bootstrap.info("Starting pipeline execution...")
            pipeline.execute_pipeline()
            bootstrap.info("Pipeline execution completed")
        except:
            bootstrap.critical("Failed to execute pipeline")

    # 10) Save payload
    payload_path = Path(config.webhook_raw_log_dir, f"pdf_js_{payload['number']}_{config.execution_timestamp}.json")
    with open(payload_path, "w") as f:
        json.dump(payload, f, indent=4)
    bootstrap.info(f"Payload saved to {payload_path}")

    # 11) Execute pipeline
    thread = threading.Thread(target=_execute_pipeline_in_background, daemon=True)
    thread.start()

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
