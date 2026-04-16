import logging
import re

from ldap3 import Server, Connection, ALL, SIMPLE, SUBTREE

logger = logging.getLogger(__name__)

# userAccountControl flag (bit 2) marking a disabled account
UAC_ACCOUNTDISABLE = 0x0002


def get_ad_profile(server_conf: dict, username: str, password: str) -> dict | None:
    """Bind to one AD config, fetch user profile. Returns None on failure."""
    logger.info("AD attempt: %s (%s)", server_conf["name"], username)

    user_upn = f"{username}@{server_conf['domain_suffix']}"
    server = Server(server_conf["server"], get_info=ALL)

    conn = None
    try:
        conn = Connection(
            server,
            user=user_upn,
            password=password,
            authentication=SIMPLE,
            auto_bind=True,
        )

        conn.search(
            search_base=server_conf["base_dn"],
            search_filter=f"(sAMAccountName={username})",
            attributes=["sAMAccountName", "displayName", "department"],
            search_scope="SUBTREE",
        )

        if not conn.entries:
            logger.warning("Bind ok but no entry found: %s", username)
            return None

        entry = conn.entries[0]

        display_name = str(entry.displayName) if entry.displayName else username
        name_parts = display_name.split(" ")
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        dept = None
        if "department" in entry and entry.department:
            dept = str(entry.department[0]).strip()

        if not dept or dept == "[]" or dept == "":
            dn_str = str(entry.entry_dn)
            ou_match = re.search(r"OU=([^,]+)", dn_str, re.I)
            if ou_match:
                dept = ou_match.group(1).replace("_", " ")

        fixed_email = f"{username}@{server_conf['email_suffix']}".lower()

        profile = {
            "username": str(entry.sAMAccountName),
            "email": fixed_email,
            "first_name": first_name,
            "last_name": last_name,
            "department": dept if dept else f"{server_conf['name']} Staff",
            "organization": server_conf["name"],
            "ad_source": server_conf["name"],
        }

        logger.info(
            "AD success: %s (%s, dept=%s)",
            display_name, fixed_email, profile["department"],
        )
        return profile

    except Exception as e:
        logger.info("%s bind failed: %s", server_conf["name"], e)
        return None
    finally:
        if conn:
            try:
                conn.unbind()
            except Exception:
                pass


def authenticate_ad(username: str, password: str, ad_configs: list) -> dict | None:
    """Try each AD config in order. Return first successful profile, or None."""
    for cfg in ad_configs:
        profile = get_ad_profile(cfg, username, password)
        if profile:
            return profile
    return None


def list_all_ad_users(server_conf: dict) -> list[dict]:
    """List every user under this AD's base_dn. Raises on any LDAP failure.

    Binds as the configured service account (bind_user / bind_password). Returns
    dicts shaped for the backend's ADUserPayload schema. The caller should
    treat any exception as a hard failure and NOT do a partial sync — the
    backend flags "AD users missing from the batch" as leavers, so sending a
    truncated list would wrongly mark real employees inactive.
    """
    bind_user = server_conf.get("bind_user", "")
    bind_password = server_conf.get("bind_password", "")
    if not bind_user or not bind_password:
        raise RuntimeError(f"{server_conf['name']}: bind_user/bind_password not configured")

    if "@" not in bind_user and "\\" not in bind_user:
        bind_upn = f"{bind_user}@{server_conf['domain_suffix']}"
    else:
        bind_upn = bind_user

    server = Server(server_conf["server"], get_info=ALL)
    conn = Connection(
        server,
        user=bind_upn,
        password=bind_password,
        authentication=SIMPLE,
        auto_bind=True,
    )

    try:
        entries = conn.extend.standard.paged_search(
            search_base=server_conf["base_dn"],
            search_filter="(&(objectCategory=person)(objectClass=user)(!(objectClass=computer)))",
            search_scope=SUBTREE,
            attributes=[
                "sAMAccountName",
                "mail",
                "displayName",
                "givenName",
                "sn",
                "department",
                "title",
                "userAccountControl",
                "distinguishedName",
            ],
            paged_size=500,
            generator=False,
        )

        users: list[dict] = []
        for e in entries:
            if e.get("type") != "searchResEntry":
                continue
            attrs = e.get("attributes", {})
            sam = (attrs.get("sAMAccountName") or "").strip()
            if not sam:
                continue

            mail = (attrs.get("mail") or "").strip().lower()
            if not mail:
                # Fall back to {sam}@email_suffix so every user has a stable key
                mail = f"{sam}@{server_conf['email_suffix']}".lower()

            display_name = (attrs.get("displayName") or "").strip()
            first_name = (attrs.get("givenName") or "").strip()
            last_name = (attrs.get("sn") or "").strip()

            dept = (attrs.get("department") or "").strip()
            if not dept:
                dn_str = attrs.get("distinguishedName") or ""
                ou_match = re.search(r"OU=([^,]+)", str(dn_str), re.I)
                if ou_match:
                    dept = ou_match.group(1).replace("_", " ")

            title = (attrs.get("title") or "").strip()

            uac_val = attrs.get("userAccountControl")
            try:
                uac_int = int(uac_val) if uac_val is not None else 0
            except (TypeError, ValueError):
                uac_int = 0
            is_disabled = bool(uac_int & UAC_ACCOUNTDISABLE)

            users.append({
                "email": mail,
                "display_name": display_name or f"{first_name} {last_name}".strip() or sam,
                "first_name": first_name,
                "last_name": last_name,
                "department": dept,
                "organization": server_conf["name"],
                "title": title,
                "is_disabled": is_disabled,
            })

        logger.info("%s: listed %d users", server_conf["name"], len(users))
        return users
    finally:
        try:
            conn.unbind()
        except Exception:
            pass
