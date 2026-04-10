import logging
import re

from ldap3 import Server, Connection, ALL, SIMPLE

logger = logging.getLogger(__name__)


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
