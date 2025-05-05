import json
import traceback
import hmac
import hashlib

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse, HttpResponseNotAllowed
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
    # 1) Allow HEAD for health checks (optional)
    if request.method == 'HEAD':
        return HttpResponse(status=200)

    # 2) Enforce POST only
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    # 3) Signature check
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
                stop = False  # we stop when successful
                post_comment = True
                models = [
                    "gpt-4o",
                    "meta-llama/Llama-3.3-70B-Instruct",
                    "llama-3.3-70b-versatile",
                    "qwen-qwq-32b"
                ]
                for model in models:
                    iAttempt = 1
                    while iAttempt <= len(config.prompt_combinations_gen["include_golden_code"]):
                        response, stop = run(payload,
                                             config,
                                             logger,
                                             model=model,
                                             iAttempt=iAttempt,
                                             timestamp=timestamp,
                                             post_comment=False)
                        iAttempt += 1
                        if stop:
                            post_comment = False
                        with open(Path(config.run_log_dir, 'results.csv'), 'a') as f:
                            f.write("%s,%s,%s,%s\n" % (payload["number"], model, iAttempt, stop))

                if not stop:
                    model = "o3-mini"
                    logger.info("[*] Starting o3-mini...")
                    response, stop = run(payload,
                                         config,
                                         logger,
                                         model=model,
                                         iAttempt=1,
                                         timestamp=timestamp,
                                         post_comment=post_comment)
                    if stop:
                        post_comment = False
                    with open(Path(config.run_log_dir, 'results.csv'), 'a') as f:
                        f.write("%s,%s,%s,%s\n" % (payload["number"], model, 1, stop))

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
