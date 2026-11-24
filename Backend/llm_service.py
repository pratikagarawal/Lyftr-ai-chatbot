
import os
import time
import litellm

from dotenv import load_dotenv
from litellm import completion
from litellm.caching import Cache

load_dotenv()

# API keys
API_KEYS = [
    key.strip()
    for key in os.getenv("LLM_API_KEYS", "").split(",")
    if key.strip()
]

# Models
MODEL_CANDIDATES = [
    "gemini/gemini-3.8-flash",
    "gemini/gemini-3.5-flash-lite"
]

# Retry configuration
MAX_ATTEMPTS_PER_KEY = 2
BASE_RETRY_DELAY = 1
REQUEST_TIMEOUT = 30

# LiteLLM cache
litellm.cache = Cache(type="local")


class AllProvidersUnavailable(Exception):
    pass


def get_key_count():
    return len(API_KEYS)


def failure_simulation_enabled():
    return os.getenv(
        "ENABLE_FAILURE_SIMULATION", "false"
    ).lower() == "true"


def parse_simulated_failures(header):
    failures = {}

    if not header:
        return failures

    for item in header.split(","):
        try:
            key_id, status = item.strip().split("=", 1)
            key_id = key_id.strip()
            status = int(status)

            if status not in (429, 500, 502, 503):
                raise ValueError()

            if key_id != "*" and not key_id.startswith("key_"):
                raise ValueError()

            if key_id != "*":
                index = int(key_id.split("_")[1])
                if index < 1 or index > len(API_KEYS):
                    raise ValueError()

            failures[key_id] = status

        except (ValueError, IndexError):
            raise ValueError(
                "Invalid X-Simulate-Failure header"
            )

    return failures


def get_status_code(exc):
    status = getattr(exc, "status_code", None)

    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)

    return status


def is_quota_error(exc):
    message = str(exc).lower()

    return (
        get_status_code(exc) == 429
        or "resource_exhausted" in message
        or "quota exceeded" in message
        or "daily limit" in message
    )


def is_retryable_server_error(exc):
    status = get_status_code(exc)

    if status in (500, 502, 503, 504, 408):
        return True

    message = str(exc).lower()

    return any(term in message for term in [
        "service unavailable",
        "high demand",
        "overloaded",
        "temporarily unavailable",
        "internal server error",
        "timeout"
    ])


def generate_response(messages, simulate_failure=None):

    if len(API_KEYS) < 2:
        raise AllProvidersUnavailable(
            "At least two API keys are required"
        )

    start_time = time.perf_counter()

    # Only honor simulation when explicitly enabled
    if failure_simulation_enabled():
        simulated = parse_simulated_failures(
            simulate_failure
        )
    else:
        simulated = {}

    # Do not cache simulated failures
    use_cache = not bool(simulated)

    fallback_attempts = 0
    retry_count = 0
    errors = []

    for model_index, model_name in enumerate(MODEL_CANDIDATES):

        for key_index, api_key in enumerate(API_KEYS):

            key_id = f"key_{key_index + 1}"

            # Simulated failure
            if key_id in simulated or "*" in simulated:

                status = simulated.get(
                    key_id,
                    simulated.get("*")
                )

                print(
                    f"[LLM] Simulated HTTP {status} for {key_id}"
                )

                errors.append(
                    f"{key_id}: simulated HTTP {status}"
                )

                fallback_attempts += 1
                continue

            route_failed = False

            for attempt in range(MAX_ATTEMPTS_PER_KEY):

                try:
                    print(
                        f"[LLM] Trying {model_name} "
                        f"with {key_id}, attempt {attempt + 1}"
                    )

                    response = completion(
                        model=model_name,
                        messages=messages,
                        api_key=api_key,
                        caching=use_cache,
                        timeout=REQUEST_TIMEOUT
                    )

                    reply = response.choices[0].message.content

                    if not reply:
                        raise RuntimeError(
                            "Empty response from provider"
                        )

                    hidden_params = getattr(
                        response, "_hidden_params", {}
                    ) or {}

                    cache_hit = bool(
                        hidden_params.get("cache_hit", False)
                    )

                    usage = response.usage

                    input_tokens = (
                        int(usage.prompt_tokens)
                        if usage else 0
                    )

                    output_tokens = (
                        int(usage.completion_tokens)
                        if usage else 0
                    )

                    latency_ms = int(
                        (time.perf_counter() - start_time) * 1000
                    )

                    return {
                        "reply": reply,
                        "resolution_source": (
                            "LLM_CACHE" if cache_hit
                            else "LIVE_INFERENCE"
                        ),
                        "model": model_name,
                        "latency_ms": latency_ms,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "key_id": None if cache_hit else key_id,
                        "fallback_attempts": (
                            0 if cache_hit else fallback_attempts
                        ),
                        "retry_count": (
                            0 if cache_hit else retry_count
                        ),
                        "model_fallback_used": model_index > 0
                    }

                except Exception as exc:

                    print(
                        f"[LLM ERROR] {key_id} | {model_name} | "
                        f"{type(exc).__name__}: {exc}"
                    )

                    errors.append(
                        f"{key_id}/{model_name}: "
                        f"{type(exc).__name__}"
                    )

                    # Quota errors: immediately move to next key
                    if is_quota_error(exc):
                        print(
                            f"[LLM] Quota exhausted for {key_id}. "
                            "Moving to next key."
                        )
                        route_failed = True
                        break

                    # Retry temporary server errors once
                    if is_retryable_server_error(exc):

                        if attempt < MAX_ATTEMPTS_PER_KEY - 1:
                            delay = BASE_RETRY_DELAY * (2 ** attempt)

                            print(
                                f"[LLM] Retrying {key_id} "
                                f"in {delay} seconds..."
                            )

                            time.sleep(delay)
                            retry_count += 1
                            continue

                    # Non-transient error or retries exhausted
                    route_failed = True
                    break

            if route_failed:
                fallback_attempts += 1

    print("[LLM] All configured attempts failed.")
    print("[LLM] Errors:", errors)

    raise AllProvidersUnavailable(
        "all providers unavailable"
    )
