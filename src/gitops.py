"""輕量 git pull / commit / push 包裝，給 launchd 與 GH Actions 共享狀態用。

設計：失敗都當 best-effort，靜默 log，不讓 main flow 中斷。"""
import os
import subprocess


def _run(cmd, timeout=20):
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=".",
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


def pull():
    """安全拉最新；只接受 fast-forward 避免 merge 衝突。"""
    if not os.path.isdir(".git"):
        return
    code, out = _run(["git", "pull", "--ff-only", "--quiet"])
    if code != 0:
        print(f"[gitops] pull failed (code={code}): {out[:200]}")


def commit_push(files, msg):
    """commit 指定檔案並推送，沒變動就 skip。"""
    if not os.path.isdir(".git"):
        return False

    _run(["git", "add"] + files)
    # 沒有 staged change 就直接 return
    code, _ = _run(["git", "diff", "--cached", "--quiet"], timeout=5)
    if code == 0:
        return False

    # 確保有 identity（GH Actions runner 預設沒設）
    code, _ = _run(["git", "config", "user.email"], timeout=5)
    if code != 0:
        _run(["git", "config", "user.email", "tixcraft-watcher@noreply"])
        _run(["git", "config", "user.name", "tixcraft-watcher"])

    code, out = _run(["git", "commit", "-m", msg], timeout=10)
    if code != 0:
        print(f"[gitops] commit failed: {out[:200]}")
        return False
    code, out = _run(["git", "push", "--quiet"], timeout=30)
    if code != 0:
        print(f"[gitops] push failed: {out[:200]}")
        # rebase 失敗時嘗試一次 fetch+rebase
        _run(["git", "fetch", "--quiet"])
        code, _ = _run(["git", "rebase", "--quiet", "origin/HEAD"])
        if code == 0:
            _run(["git", "push", "--quiet"], timeout=30)
        return False
    return True
