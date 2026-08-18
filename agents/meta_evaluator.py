from omni.meta_agent_runtime import run_meta


def run(*args, **kwargs):
    return run_meta(
        "evaluator",
        *args,
        **kwargs,
    )
