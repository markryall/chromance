"""chromance list | start NAME [URL] [--port [--ttl MIN]] | stop NAME | cookie NAME DOMAIN [COOKIE] | path NAME | destroy NAME [--yes]"""
import argparse, json, sys
import chromance


def main():
    ap = argparse.ArgumentParser(prog='chromance', description=chromance.__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd')
    sub.add_parser('list', help='profiles and which are running')
    s = sub.add_parser('start', help='open a profile (made on first use) as plain Chrome, optionally at a URL')
    s.add_argument('name'); s.add_argument('url', nargs='?')
    s.add_argument('--port', action='store_true', help='add a DevTools port for scripts to attach to (any local program can)')
    s.add_argument('--ttl', type=float, default=chromance.PORT_TTL / 60, help='minutes before a --port Chrome quits (default 30)')
    s = sub.add_parser('stop', help="quit a profile's Chrome")
    s.add_argument('name')
    s = sub.add_parser('cookie', help="print a cookie's value (one name) or a domain's cookies as JSON")
    s.add_argument('name'); s.add_argument('domain'); s.add_argument('cookie', nargs='?')
    s = sub.add_parser('path', help="a profile's folder")
    s.add_argument('name')
    s = sub.add_parser('destroy', help='quit a profile and delete it, logins and all')
    s.add_argument('name'); s.add_argument('--yes', '-y', action='store_true', help="don't ask first")
    a = ap.parse_args()

    try:
        if a.cmd in (None, 'list'):
            names = chromance.profiles()
            if not names: print(f'no profiles yet in {chromance.HOME}; make one with: chromance start NAME')
            for n in names:
                state = chromance.endpoint(n) or ('open' if chromance.running(n) else '-')
                print(f'{n:20} {state}')
        elif a.cmd == 'start':
            if found := chromance.start(a.name, a.url, port=a.port, ttl=a.ttl * 60): print(found)
        elif a.cmd == 'stop':
            print('stopped' if chromance.stop(a.name) else 'not running')
        elif a.cmd == 'cookie':
            found = chromance.cookies(a.name, a.domain, a.cookie)
            if a.cookie:
                if not found: sys.exit(f'{a.name}: no {a.cookie} cookie for {a.domain} (logged in?)')
                print(found[0]['value'])
            else:
                print(json.dumps(found, indent=2))
        elif a.cmd == 'path':
            print(chromance.profile_dir(a.name))
        elif a.cmd == 'destroy':
            d = chromance.profile_dir(a.name)
            if not d.is_dir(): sys.exit(f'{a.name}: no such profile')
            if not a.yes:
                if not sys.stdin.isatty(): sys.exit(f'{a.name}: pass --yes to destroy without a terminal to confirm in')
                if input(f'delete {d}, with every login and extension in it? [y/N] ').strip().lower() not in ('y', 'yes'):
                    sys.exit('kept')
            chromance.destroy(a.name)
            print('destroyed')
    except (ValueError, RuntimeError) as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
