"""Leitura dos dados de perfil (metadados) para a API."""
from __future__ import annotations

from app import db
from app.config import CANDIDATES
from app.models import ProfileData


def get_profiles(include_competitor: bool = True) -> list[ProfileData]:
    rows = db.query_all(
        """
        select candidate_id, username, full_name, biography, followers_count, follows_count,
               posts_count, verified, is_private, external_url, category,
               (profile_pic_data is not null) as has_avatar, prev_followers_count, updated_at
        from profiles
        """
    )
    by_id = {r["candidate_id"]: r for r in rows}
    out: list[ProfileData] = []
    for c in CANDIDATES:
        if not include_competitor and c.is_competitor:
            continue
        r = by_id.get(c.id, {})
        fc = r.get("followers_count")
        prev = r.get("prev_followers_count")
        delta = (int(fc) - int(prev)) if fc is not None and prev is not None else None
        out.append(
            ProfileData(
                candidate_id=c.id,
                username=c.username,
                full_name=r.get("full_name") or c.display_name,
                display_name=c.display_name,
                cargo=c.cargo,
                is_competitor=c.is_competitor,
                biography=r.get("biography") or "",
                followers_count=int(r.get("followers_count") or 0),
                follows_count=int(r.get("follows_count") or 0),
                posts_count=int(r.get("posts_count") or 0),
                verified=bool(r.get("verified")),
                is_private=bool(r.get("is_private")),
                external_url=r.get("external_url"),
                category=r.get("category"),
                has_avatar=bool(r.get("has_avatar")),
                avatar_path=f"/api/v1/profiles/{c.id}/avatar",
                followers_delta=delta,
                updated_at=r["updated_at"].isoformat() if r.get("updated_at") else None,
            )
        )
    return out


def get_one(candidate_id: str) -> ProfileData | None:
    """Perfil de qualquer candidato (inclui ad-hoc), lendo display_name/cargo do banco."""
    row = db.query_one(
        """
        select p.candidate_id, p.username, p.full_name, p.biography, p.followers_count,
               p.follows_count, p.posts_count, p.verified, p.is_private, p.external_url, p.category,
               (p.profile_pic_data is not null) as has_avatar, p.prev_followers_count, p.updated_at,
               c.display_name, c.cargo, c.is_competitor
        from profiles p join candidates c on c.id = p.candidate_id
        where p.candidate_id = %(c)s
        """,
        {"c": candidate_id},
    )
    if not row:
        return None
    fc, prev = row.get("followers_count"), row.get("prev_followers_count")
    delta = (int(fc) - int(prev)) if fc is not None and prev is not None else None
    return ProfileData(
        candidate_id=row["candidate_id"],
        username=row["username"],
        full_name=row.get("full_name") or row["display_name"],
        display_name=row["display_name"],
        cargo=row.get("cargo"),
        is_competitor=bool(row.get("is_competitor")),
        biography=row.get("biography") or "",
        followers_count=int(row.get("followers_count") or 0),
        follows_count=int(row.get("follows_count") or 0),
        posts_count=int(row.get("posts_count") or 0),
        verified=bool(row.get("verified")),
        is_private=bool(row.get("is_private")),
        external_url=row.get("external_url"),
        category=row.get("category"),
        has_avatar=bool(row.get("has_avatar")),
        avatar_path=f"/api/v1/profiles/{row['candidate_id']}/avatar",
        followers_delta=delta,
        updated_at=row["updated_at"].isoformat() if row.get("updated_at") else None,
    )


def get_avatar(candidate_id: str) -> tuple[bytes, str] | None:
    row = db.query_one(
        "select profile_pic_data, profile_pic_content_type from profiles where candidate_id=%(c)s",
        {"c": candidate_id},
    )
    if not row or not row.get("profile_pic_data"):
        return None
    return bytes(row["profile_pic_data"]), row.get("profile_pic_content_type") or "image/jpeg"
