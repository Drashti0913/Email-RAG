"""CLI entry point. Run python -m email_rag --help."""
import argparse
import json
import mailbox
import os
from pathlib import Path
import sys
from .models import Ollama
from .parsing import MAX_EMAIL_BYTES
from .pipeline import ingest_raw, ask, model_identity, summarize_all
from .store import Store, provision_user


def write_json(value):
    print(json.dumps(value, indent=2, default=str))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local email RAG: private inference, cited sources.')
    parser.add_argument('--token-file', type=Path, help='User capability token file; never committed')
    parser.add_argument('--source-root', default='.data/sources')
    subs = parser.add_subparsers(dest='command', required=True)
    register = subs.add_parser('create-user', help='Admin-only: provision a user token')
    register.add_argument('name')
    register.add_argument('--out', type=Path, required=True)
    subs.add_parser('doctor', help='Verify database and locally installed models')
    subs.add_parser('stats', help='Count only the authenticated user\'s data')
    ingest = subs.add_parser('ingest', help='Ingest a .eml, directory of .eml, or .mbox')
    ingest.add_argument('path', type=Path)
    gmail = subs.add_parser('gmail-sync', help='Read-only Gmail OAuth ingestion')
    gmail.add_argument('--credentials', type=Path, required=True)
    gmail.add_argument('--account', required=True)
    gmail.add_argument('--query', default='in:anywhere -in:spam -in:trash')
    gmail.add_argument('--limit', type=int, default=100)
    query = subs.add_parser('query')
    query.add_argument('question')
    query.add_argument('--top-k', type=int, default=8, choices=range(1,31), metavar='1..30')
    query.add_argument('--sender')
    query.add_argument('--subject')
    query.add_argument('--latest', action='store_true')
    query.add_argument('--all-matching', action='store_true', help='Summarize every chunk matching --subject')
    args = parser.parse_args(argv)
    if args.command == 'create-user':
        if args.out.exists():
            parser.error('Token output already exists; choose another path')
        args.out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Reserve the path before creating the account to avoid overwriting a secret.
        with args.out.open('x') as output:
            os.chmod(args.out, 0o600)
            try:
                output.write(provision_user(args.name) + '\n')
            except Exception:
                args.out.unlink(missing_ok=True)
                raise
        write_json({'user': args.name, 'token_file': str(args.out)})
        return 0
    if not args.token_file:
        parser.error('--token-file is required')
    store = Store(args.token_file.read_text().strip())
    try:
        if args.command == 'stats':
            write_json(store.stats())
            return 0
        models = Ollama()
        identity = model_identity(models)
        store.ensure_model(identity)
        if args.command == 'doctor':
            write_json({'database': 'connected, RLS role verified', 'models': models.identities(),
                        'embedding_probe_dimensions': len(models.embed(['health check'])[0]),
                        'stats': store.stats()})
        elif args.command == 'query':
            if args.all_matching:
                if args.latest or args.sender:
                    parser.error('--all-matching accepts --subject only, not --latest/--sender')
                write_json(summarize_all(store, models, args.question, args.subject))
            else:
                write_json(ask(store, models, args.question, args.top_k, args.sender, args.subject, args.latest))
        else:
            if args.command == 'gmail-sync':
                if not 1 <= args.limit <= 10000:
                    parser.error('--limit must be 1..10000')
                from .gmail import connect, messages
                service = connect(args.credentials, Path('.secrets/gmail') / (store.user_id + '.json'))
                items = messages(service, args.account, args.query, args.limit)
            else:
                path = args.path
                if not path.exists():
                    parser.error('Input path does not exist')
                def local_items():
                    if path.suffix.lower() == '.mbox':
                        box = mailbox.mbox(path, create=False)
                        try:
                            for key in box.iterkeys():
                                yield box.get_bytes(key, from_=False), None, None
                        finally:
                            box.close()
                    else:
                        paths = sorted(path.rglob('*.eml')) if path.is_dir() else [path]
                        for item in paths:
                            if item.stat().st_size > MAX_EMAIL_BYTES:
                                yield None, str(item), None
                            else:
                                yield item.read_bytes(), None, None
                items = local_items()
            results = []
            for raw, external_id, url in items:
                try:
                    if raw is None:
                        raise ValueError('email exceeds 30 MiB limit')
                    result = ingest_raw(store, models, raw, args.source_root, external_id, url)
                except Exception as exc:
                    # Continue processing other messages, but return nonzero for visible failure.
                    result = {'status': 'error', 'error': f'{type(exc).__name__}: {exc}'}
                results.append(result)
            write_json({'messages': results, 'stats': store.stats()})
            return 1 if any(r['status'] == 'error' or r.get('warnings') for r in results) else 0
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
