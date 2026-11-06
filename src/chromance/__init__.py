"""Named Chrome profiles that scripts can drive, never your everyday one.

Each profile is its own Chrome user data folder under $CHROMANCE_HOME (default
~/.local/share/chromance/<name>), so extensions you install in it (1Password) and sites you log
into stay put between runs.

connect() launches Chrome on a profile and drives it over a DevTools *pipe*: a private channel only
the launching script holds, so nothing else on the machine can reach the profile's logins. Chrome
closes when the script is done. start() opens a profile as plain Chrome, with no DevTools at all,
for logging in and installing extensions by hand. Only start(port=True) opens a DevTools port,
which any local program could use, so it quits itself after a time limit.
"""
import contextlib, json, os, pathlib, re, signal, subprocess, sys, time, urllib.request

CHROME = os.environ.get('CHROMANCE_CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
HOME = pathlib.Path(os.environ.get('CHROMANCE_HOME', '~/.local/share/chromance')).expanduser()
# Your everyday Chrome. Chrome itself won't open DevTools on it since 136, and chromance never points at it.
MAIN = pathlib.Path('~/Library/Application Support/Google/Chrome').expanduser().resolve()
NAME = re.compile(r'[a-z0-9][a-z0-9_-]*\Z')
PORT_TTL = 30 * 60
# Playwright's defaults that would make a profile behave unlike the Chrome you set it up in: a mock keychain
# and basic password store (cookies saved by hand wouldn't decrypt, nor the reverse), no extensions (1Password),
# no sync or component updates, and the "controlled by automated software" banner.
KEEP_CHROME_NORMAL = ['--enable-automation', '--disable-extensions', '--password-store=basic', '--use-mock-keychain',
                      '--disable-sync', '--disable-component-update', '--disable-default-apps',
                      '--disable-component-extensions-with-background-pages', '--disable-background-networking']
CHROME_ARGS = ['--no-first-run', '--no-default-browser-check']


def profile_dir(name):
    if not NAME.match(name):
        raise ValueError(f'{name!r}: profile names are lowercase letters, digits, - and _')
    d = (HOME / name).resolve()
    # macOS paths are case-insensitive, so .../Google/chrome is the everyday profile too.
    a, m = str(d).casefold().rstrip('/'), str(MAIN).casefold().rstrip('/')
    if a == m or a.startswith(m + '/') or m.startswith(a + '/'):
        raise ValueError(f'{d} is (or holds) your everyday Chrome profile, which chromance never drives')
    return d


def profiles():
    return sorted(p.name for p in HOME.iterdir() if p.is_dir() and NAME.match(p.name)) if HOME.is_dir() else []


def running(name):
    """The pid of the Chrome that has the profile open, or None. Chrome's SingletonLock links to "host-pid"."""
    try:
        pid = int(os.readlink(profile_dir(name) / 'SingletonLock').rsplit('-', 1)[1])
        os.kill(pid, 0)
    except (OSError, ValueError, IndexError):
        return None
    return pid


def endpoint(name):
    """The DevTools URL when the profile was started with port=True and is still up, else None."""
    if not running(name): return None
    try:
        port = int((profile_dir(name) / 'DevToolsActivePort').read_text().split()[0])
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=1) as r:
            json.load(r)
    except (OSError, ValueError, IndexError):
        return None
    return f'http://127.0.0.1:{port}'


def start(name, url=None, port=False, ttl=PORT_TTL, wait=30):
    """Open the profile (made on first use) as plain Chrome, or already open, open url in it.
    port=True adds a DevTools port, which any local program can use, and quits Chrome after ttl seconds.
    Returns the DevTools URL with port=True, else None."""
    d = profile_dir(name)
    if pid := running(name):
        if port and not endpoint(name):
            raise RuntimeError(f'{name} is already open without a DevTools port; quit it (chromance stop {name}) first')
        if url: subprocess.Popen([CHROME, f'--user-data-dir={d}', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return endpoint(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'DevToolsActivePort').unlink(missing_ok=True)
    # Port 0 lets Chrome pick a free port and write it to DevToolsActivePort, so several profiles run at once.
    args = [CHROME, f'--user-data-dir={d}', *CHROME_ARGS, *(['--remote-debugging-port=0'] if port else []), *([url] if url else [])]
    with open(d / 'chromance.log', 'ab') as log:
        chrome = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(wait * 4):
        if (endpoint(name) if port else running(name)): break
        time.sleep(0.25)
    else:
        raise RuntimeError(f'{name}: Chrome didn\'t come up within {wait}s. Log: {d / "chromance.log"}')
    if port:
        # Quit this Chrome after ttl, unless it has been quit and reopened since.
        reaper = f'import time, chromance; time.sleep({ttl}); chromance.running({name!r}) == {chrome.pid} and chromance.stop({name!r})'
        subprocess.Popen([sys.executable, '-c', reaper], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return endpoint(name)


@contextlib.contextmanager
def connect(name, headless=False):
    """Yield a Playwright BrowserContext on the profile, with its logins, extensions and cookies.

    Launches Chrome over a private DevTools pipe and quits it when the block ends. If the profile is
    already running with a port (start(port=True)) it attaches to that instead and leaves it running.
    A profile open as plain Chrome can't be driven: quit it first."""
    from playwright.sync_api import sync_playwright
    d = profile_dir(name)
    if running(name) and not endpoint(name):
        raise RuntimeError(f'{name} is open in Chrome without DevTools; quit it (chromance stop {name}) so a script can launch it')
    with sync_playwright() as p:
        if found := endpoint(name):
            yield p.chromium.connect_over_cdp(found).contexts[0]
            return
        d.mkdir(parents=True, exist_ok=True)
        ctx = p.chromium.launch_persistent_context(d, channel='chrome', headless=headless, no_viewport=True,
                                                   args=CHROME_ARGS, ignore_default_args=KEEP_CHROME_NORMAL)
        try:
            yield ctx
        finally:
            ctx.close()


def cookies(name, domain=None, cookie=None):
    """The profile's cookies, optionally only those for domain (and its subdomains) and/or with a given name.
    Launches the profile headless for a moment unless it's running with a port."""
    with connect(name, headless=True) as ctx:
        return [c for c in ctx.cookies()
                if (domain is None or c['domain'].lstrip('.') == domain or c['domain'].endswith('.' + domain))
                and (cookie is None or c['name'] == cookie)]


def stop(name, wait=15):
    """Quit the profile's Chrome. False if it wasn't running."""
    if not (pid := running(name)): return False
    os.kill(pid, signal.SIGTERM)  # Chrome shuts down cleanly on SIGTERM, saving cookies and session
    for _ in range(wait * 4):
        if not running(name): return True
        time.sleep(0.25)
    raise RuntimeError(f'{name}: Chrome (pid {pid}) still running {wait}s after being asked to quit')
