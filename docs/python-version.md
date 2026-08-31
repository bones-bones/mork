# Python version policy

| Context | Version | Notes |
|---------|---------|--------|
| **Minimum supported** | 3.11 | Production VM (`lil-mork`, Debian 12 Bookworm) |
| **CI / local default** | 3.12 | See `.python-version` and `.github/workflows/ci.yml` |
| **Not supported** | &lt; 3.11 | PEP 695 `def foo[T]()` and other 3.12-only syntax must not be used without a version guard |

## Why both 3.11 and 3.12?

- **CI and developers** run 3.12 (Ruff, pre-commit, GitHub Actions).
- **The GCP VM** ships Python 3.11.2; upgrading requires pyenv or a third-party backport (not in Debian Bookworm apt).

Code must parse and run on **3.11+**. Use `typing.TypeVar` instead of PEP 695 generic functions until the VM is on 3.12.

## Checks

```bash
# From repo root — syntax + deps smoke test (no Discord token required)
python scripts/verify_vm_deploy.py

# On the VM after deploy (needs bot_secrets/ and .env for --with-cogs)
cd /home/elliotbrown/mork   # or your DEPLOY_PATH
python3 scripts/verify_vm_deploy.py --with-cogs --check-service
```

## VM deploy path

GitHub Actions deploy (`.github/workflows/main.yml`) runs `pip3 install -r requirements.txt` with the VM’s default `python3` (3.11). Systemd `ExecStart` must point at that same interpreter (or an explicit `python3.11` / pyenv path).
