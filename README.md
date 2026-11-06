# chromance

Named Chrome profiles that scripts can drive, never your everyday one.

Each profile is its own Chrome user data folder under `~/.local/share/chromance/<name>`
(or `$CHROMANCE_HOME`). Install extensions such as 1Password in it and log into sites once, and they
stay put.

Your everyday profile (`~/Library/Application Support/Google/Chrome`) is off limits: chromance
refuses any profile at, inside or above it, and since version 136 Chrome won't open DevTools on it
anyway.

## Three ways to open a profile

- **By hand, `chromance start NAME`**: plain Chrome with no DevTools, as safe as any browser. Use
  it to log in, install 1Password, or clear a checkpoint.
- **From a script, `chromance.connect(NAME)`** (the default for scripts): Playwright launches
  Chrome and drives it over a DevTools *pipe*, which only that script holds, so no other program on
  the Mac can reach the profile's logins. Chrome quits when the script is done. The profile must not
  be open by hand at the time.
- **Attachable, `chromance start NAME --port`**: adds a DevTools port so scripts can attach to a
  browser that keeps running between them. A port has no password, so **any program running as you
  can read every cookie and page in the profile** while it's open. It quits itself after `--ttl`
  minutes (default 30).

Either way the browser is the profile you set up: chromance drops Playwright's mock keychain (so
cookies saved by hand decrypt in scripts and the other way round), keeps extensions on, and hides
the "controlled by automated software" banner. Pages can still tell a script is driving
(`navigator.webdriver` is true).

## Commands

```
chromance list                         profiles: "-" closed, "open", or the DevTools URL
chromance start NAME [URL]             open a profile (made on first use) as plain Chrome
chromance start NAME --port [--ttl M]  open it with a DevTools port that closes after M minutes
chromance stop NAME                    quit it
chromance cookie NAME DOMAIN COOKIE    print one cookie's value, e.g. for curl
chromance cookie NAME DOMAIN           all of a domain's cookies as JSON
chromance path NAME                    the profile's folder
chromance destroy NAME [--yes]         quit it and delete it, logins and all (asks first)
```

`cookie` launches the profile headless for a moment (or uses its port if it has one), so quit a
profile you have open by hand first.

## From Python

```python
import chromance

with chromance.connect('gigs') as ctx:      # launches Chrome; it quits when the block ends
    page = ctx.new_page()
    page.goto('https://www.facebook.com/events/...')
    print(page.inner_text('body'))

session = chromance.cookies('airnet', 'airnet.org.au', 'PHPSESSID')[0]['value']
```

`connect()` with no name drives a fresh throwaway profile in the system temp folder, deleted when
the block ends: no logins, extensions or cookies carried in or left behind.

`connect(name, headless=True)` runs without a window, but then you can't step in when a site asks
you to log in or solve a captcha.

## Install

```
uv tool install -e ~/code/github/markryall/chromance
```

This puts `chromance` in `~/.local/bin` (`uv tool dir --bin`), linked to a venv under
`~/.local/share/uv/tools/chromance`. `-e` means edits to this repo apply without reinstalling.

Another project can depend on it with `uv add --editable ../chromance`, or use the CLI.
