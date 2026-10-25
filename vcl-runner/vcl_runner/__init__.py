"""VCL runner: do the student's Vibecode Lisboa model work on their own install.

The Hub at vibecodelisboa.com queues model-heavy jobs for a founder who chose
"My BehalfBot" as the runner. This package claims them over HTTP, runs each
step through the local `claude -p` (the student's own Claude Code login, no
tools), and posts the raw text back. The Hub parses and checks it exactly as it
checks its own model output. A tablet_send job skips claude: the runner
downloads the file the Hub built and uploads it to the student's reMarkable
with rmapi. A tablet_pull job skips it too: the runner reads the student's
highlights and handwriting back off that document (annotations.py) and sends
them to the Hub.

    tick()        one heartbeat: claim up to three jobs, run them, post results
    save_key()    store the agent key in the install's .env, the chassis secret file

The agent key is read from FOUNDER_OS_AGENT_KEY and nowhere else. It is never
logged, never passed to the claude child process, and never sent anywhere but
the configured Hub.
"""
from .envfile import save_key
from .runner import (DEFAULT_BASE_URL, ENV_BASE_URL, ENV_KEY, KEY_PREFIX, AuthRejected, HubClient,
                     HubUnreachable, claude_argv, tick)

__all__ = ["DEFAULT_BASE_URL", "ENV_BASE_URL", "ENV_KEY", "KEY_PREFIX", "AuthRejected", "HubClient",
           "HubUnreachable", "claude_argv", "save_key", "tick"]
