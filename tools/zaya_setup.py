"""Install the observation hook and import explicit private profile data."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Zaya private setup')
    parser.add_argument('--install-hermes-hook', action='store_true')
    parser.add_argument('--hermes-home', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--project', type=Path)
    args = parser.parse_args()
    if args.install_hermes_hook:
        from services.whatsapp.bridge import install_hook
        path = install_hook(args.hermes_home)
        print(f'Observation hook installed: {path}')
        print('Restart Hermes gateway when convenient to load it. Existing pairing is preserved.')
    if args.profile:
        from memory.profile_bootstrap import bootstrap
        print('Private profile import:', bootstrap(args.profile))
    if args.project:
        from memory.project_index import register_project
        register_project(str(args.project), args.project.name, ['zaya'])
        print('Local project alias registered.')


if __name__ == '__main__':
    main()
