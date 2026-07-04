def route(cmd: dict) -> str:
    """Маршрут команди C2 до топіка потрібного ефектора (ABORT — усім)."""
    if cmd.get("type") == "ABORT":
        return "cuas/effectors/all/cmd"
    return {"E1": "cuas/effectors/e1_net/cmd", "E2": "cuas/effectors/e2_ram/cmd"}[cmd["effector"]]
