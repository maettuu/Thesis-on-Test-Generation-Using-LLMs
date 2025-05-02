import json
import traceback
import hmac
import hashlib

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseForbidden
from datetime import datetime
from pathlib import Path

from webhook_handler.core import Config
from webhook_handler.core.config import logger
from .pipeline import run

# Initiate pipeline logger & config
logger.debug("Entered webhook")
config = Config()

@csrf_exempt
def github_webhook(request):
    """Handle GitHub webhook events"""
    if request.method != 'POST':
        logger.info("Method is not POST")
        return HttpResponseForbidden("Invalid method")

    if not verify_signature(request):
        logger.info("Invalid signature")
        return HttpResponseForbidden("Invalid signature")

    payload = json.loads(request.body)
    # Save the payload to the logs
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    Path(config.webhook_raw_log_dir).mkdir(parents=True, exist_ok=True)
    filename = f"webhook_{timestamp}.json"
    file_path = Path(config.webhook_raw_log_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    logger.info(f"Webhook saved to {file_path}")  # Log the save action

    event = request.headers.get('X-GitHub-Event')
    if event == "pull_request":
        try:
            # Only trigger when PR opens (or if it is my repo)
            if payload.get("action") == "opened" or payload["repository"]["owner"]["login"] == "kitsiosk":

                iAttempt = 0
                stop = False  # we stop when successful

                # gpt-4o
                while iAttempt < len(config.prompt_combinations_gen) and not stop:
                    response, stop = run(
                        payload,
                        config,
                        logger,
                        iAttempt=iAttempt,
                        model="gpt-4o",
                        timestamp=timestamp,
                        post_comment=True
                    )
                    iAttempt += 1

                # llama3.3
                iAttempt = 0
                while iAttempt < len(config.prompt_combinations_gen) and not stop:
                    response, stop = run(
                        payload,
                        config,
                        logger,
                        iAttempt=iAttempt,
                        model="meta-llama/Llama-3.3-70B-Instruct",
                        timestamp=timestamp,
                        post_comment=True
                    )
                    iAttempt += 1

                # o3-mini-high (last resort)
                if not stop:
                    response, stop = run(
                        payload,
                        config,
                        logger,
                        iAttempt=1,
                        model="o3-mini",
                        timestamp=timestamp,
                        post_comment=True
                    )
                return response

            else:
                logger.info("PR event, but not opening of a PR, so skipping...")
                return JsonResponse({"status": "success"})
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=400)
    else:
        logger.info("Non-PR event")
        return JsonResponse({"status": "success"})

def verify_signature(request):
    """Verify the webhook signature."""
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return False
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    # Encode the request body using the same secret
    mac = hmac.new(config.github_webhook_secret.encode(), msg=request.body, digestmod=hashlib.sha256)
    # If the two encodings are the same, we are good.
    return hmac.compare_digest(mac.hexdigest(), signature)
