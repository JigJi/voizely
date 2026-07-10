"""Tenant management CLI — create organizations and local (email/password) users.

Used to onboard a new customer org (e.g. the gov pilot) without an admin UI yet.

Examples:
    # 1. create the org. --domains lets users log in with just their email
    #    (officer@doh.go.th → routed to this tenant automatically, no org code).
    python manage_tenant.py create-org --slug doh --name "กรมทางหลวง" --pipeline cloud --domains doh.go.th

    # 2. create a login for them (email/password we control)
    python manage_tenant.py create-user --org gov-abc --username somchai@abc.go.th \
        --password "S3cret!" --email somchai@abc.go.th --first-name สมชาย --role ADMIN

    # list / reset
    python manage_tenant.py list-orgs
    python manage_tenant.py set-password --org gov-abc --username somchai@abc.go.th --password "New!"
"""
import argparse
import sys

from app.database import SessionLocal
from app.core.passwords import hash_password
from app.models.organization import Organization
from app.models.user import User


def _get_org(db, slug):
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if not org:
        sys.exit(f"ERROR: no organization with slug '{slug}' (run create-org first)")
    return org


def _parse_domains(raw):
    return [d.strip().lower() for d in (raw or "").split(",") if d.strip()] or None


def create_org(args):
    db = SessionLocal()
    try:
        if db.query(Organization).filter(Organization.slug == args.slug).first():
            sys.exit(f"ERROR: org slug '{args.slug}' already exists")
        org = Organization(
            name=args.name, slug=args.slug,
            pipeline_mode=args.pipeline, is_active=True,
            email_domains=_parse_domains(args.domains),
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        print(f"OK: created org id={org.id} slug='{org.slug}' name='{org.name}' "
              f"pipeline={org.pipeline_mode} domains={org.email_domains}")
    finally:
        db.close()


def set_domains(args):
    db = SessionLocal()
    try:
        org = _get_org(db, args.slug)
        org.email_domains = _parse_domains(args.domains)
        db.commit()
        print(f"OK: org '{args.slug}' email_domains={org.email_domains}")
    finally:
        db.close()


def create_user(args):
    db = SessionLocal()
    try:
        org = _get_org(db, args.org)
        existing = db.query(User).filter(
            User.tenant_id == org.id, User.username == args.username
        ).first()
        if existing:
            sys.exit(f"ERROR: user '{args.username}' already exists in org '{args.org}'")
        user = User(
            tenant_id=org.id,
            username=args.username,
            email=args.email or args.username,
            first_name=args.first_name,
            last_name=args.last_name,
            role=args.role,
            password_hash=hash_password(args.password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"OK: created user id={user.id} username='{user.username}' org='{args.org}' role={user.role}")
    finally:
        db.close()


def set_password(args):
    db = SessionLocal()
    try:
        org = _get_org(db, args.org)
        user = db.query(User).filter(
            User.tenant_id == org.id, User.username == args.username
        ).first()
        if not user:
            sys.exit(f"ERROR: no user '{args.username}' in org '{args.org}'")
        user.password_hash = hash_password(args.password)
        db.commit()
        print(f"OK: password reset for '{user.username}' in org '{args.org}'")
    finally:
        db.close()


def list_orgs(args):
    db = SessionLocal()
    try:
        for o in db.query(Organization).order_by(Organization.id).all():
            n_users = db.query(User).filter(User.tenant_id == o.id).count()
            print(f"  id={o.id} slug='{o.slug}' name='{o.name}' pipeline={o.pipeline_mode} "
                  f"domains={o.email_domains} active={o.is_active} users={n_users}")
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Tenant management CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create-org")
    c.add_argument("--slug", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--pipeline", default="cloud", choices=["cloud", "local"])
    c.add_argument("--domains", default="", help="comma-separated email domains, e.g. doh.go.th")
    c.set_defaults(func=create_org)

    c = sub.add_parser("set-domains")
    c.add_argument("--slug", required=True)
    c.add_argument("--domains", required=True, help="comma-separated email domains (replaces existing)")
    c.set_defaults(func=set_domains)

    c = sub.add_parser("create-user")
    c.add_argument("--org", required=True)
    c.add_argument("--username", required=True)
    c.add_argument("--password", required=True)
    c.add_argument("--email", default="")
    c.add_argument("--first-name", dest="first_name", default="")
    c.add_argument("--last-name", dest="last_name", default="")
    c.add_argument("--role", default="USER", choices=["USER", "ADMIN"])
    c.set_defaults(func=create_user)

    c = sub.add_parser("set-password")
    c.add_argument("--org", required=True)
    c.add_argument("--username", required=True)
    c.add_argument("--password", required=True)
    c.set_defaults(func=set_password)

    c = sub.add_parser("list-orgs")
    c.set_defaults(func=list_orgs)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
