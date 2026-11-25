from hypothesis import settings, HealthCheck

# Default: 200 examples — what CI runs
settings.register_profile(
    "ci",
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Deep local run — catches more
settings.register_profile(
    "deep",
    max_examples=2000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Exhaustive — run overnight
settings.register_profile(
    "soak",
    max_examples=20000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Activate "ci" by default so CI without flags still works
settings.load_profile("ci")