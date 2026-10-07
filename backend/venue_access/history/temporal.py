"""Temporal derivation: observation -> intervals + change events.

Semantics (ADR 002/005):
- first_seen_at  = date of the first *good* snapshot containing the key;
- last_seen_at   = date of the latest good snapshot containing it;
- first_absent_at= date of the first good snapshot *not* containing it while
  the key had been seen before;
- reappeared_at  = date it reappeared after a recorded absence.

Absence events only ever originate from snapshots that passed the quality
gate AND come from sources with absence_semantics_allowed = true.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from hashlib import sha256

from venue_access.domain.enums import ChangeType, IntervalStatus, SnapshotStatus
from venue_access.storage.store import Store

CONFIRM_ABSENCE_SNAPSHOTS = 2  # consecutive good-snapshot absences to confirm

GOOD = (SnapshotStatus.VALIDATED.value, SnapshotStatus.PUBLISHED.value)


@dataclass(frozen=True)
class _Key:
    participant_id: str
    source_id: str
    mic: str
    family: str

    @property
    def membership_key(self) -> str:
        return f"{self.source_id}|{self.mic}|{self.family}"


@dataclass
class _State:
    first_seen: date
    last_seen: date
    first_absent: date | None = None
    consecutive_absent: int = 0
    supporting: int = 1
    ever_absent: bool = False
    member_codes: set[str] = field(default_factory=set)
    member_type: str | None = None
    status: IntervalStatus = IntervalStatus.CURRENT


def _day(ts) -> date:
    if isinstance(ts, datetime):
        return ts.date()
    return ts


def recompute_history(store: Store, confirm_absences: int = CONFIRM_ABSENCE_SNAPSHOTS) -> dict:
    """Rebuild membership_interval + change_event from observations.

    Deterministic and idempotent: both tables are fully recomputed from the
    immutable observation store.
    """
    snaps = store.query(
        f"""SELECT snapshot_id, source_id, retrieved_at FROM snapshot
            WHERE snapshot_status IN ('{GOOD[0]}','{GOOD[1]}')
            ORDER BY retrieved_at"""
    )
    # Only sources allowed to infer absence produce absence events.
    absence_ok = {
        r["source_id"]: r["absence_semantics_allowed"]
        for r in store.query("SELECT source_id, absence_semantics_allowed FROM source")
    }

    obs = store.query(
        """SELECT o.snapshot_id, o.participant_id, o.membership_type_normalized,
                  s.mic, s.market_family, s.member_code
           FROM membership_observation o
           JOIN membership_segment_observation s ON s.observation_id = o.observation_id
           WHERE s.mic IS NOT NULL AND s.segment_active"""
    )
    # snapshot -> {key -> {"codes": set, "type": str}}
    by_snap: dict[str, dict[_Key, dict]] = defaultdict(dict)
    for r in obs:
        k = _Key(r["participant_id"], r["snapshot_id"].split(":")[0], r["mic"],
                 r["market_family"] or "")
        e = by_snap[r["snapshot_id"]].setdefault(k, {"codes": set(), "type": None})
        if r["member_code"]:
            e["codes"].add(r["member_code"])
        e["type"] = r["membership_type_normalized"] or e["type"]

    states: dict[_Key, _State] = {}
    events: list[dict] = []
    snaps_by_source: dict[str, list[dict]] = defaultdict(list)
    for s in snaps:
        snaps_by_source[s["source_id"]].append(s)

    for source_id, snap_list in snaps_by_source.items():
        source_states: dict[_Key, _State] = {
            k: v for k, v in states.items() if k.source_id == source_id
        }
        for snap in snap_list:
            day = _day(snap["retrieved_at"])
            present = by_snap.get(snap["snapshot_id"], {})
            # appearances / code changes
            for key, info in present.items():
                st = source_states.get(key)
                codes = info["codes"]
                if st is None:
                    st = _State(first_seen=day, last_seen=day, member_codes=set(codes),
                                member_type=info["type"])
                    source_states[key] = st
                    states[key] = st
                    events.append(_evt(day, key, ChangeType.NEWLY_OBSERVED,
                                       None, ";".join(sorted(codes))))
                else:
                    st.last_seen = day
                    st.supporting += 1
                    if st.first_absent is not None:
                        st.ever_absent = True
                        st.status = IntervalStatus.REAPPEARED
                        st.first_absent = None
                        st.consecutive_absent = 0
                        events.append(_evt(day, key, ChangeType.REAPPEARED,
                                           None, ";".join(sorted(codes))))
                    if codes != st.member_codes:
                        events.append(_evt(day, key, ChangeType.MEMBER_CODE_CHANGED,
                                           ";".join(sorted(st.member_codes)),
                                           ";".join(sorted(codes))))
                        st.member_codes = set(codes)
                    if info["type"] and info["type"] != st.member_type:
                        events.append(_evt(day, key, ChangeType.MEMBERSHIP_TYPE_CHANGED,
                                           st.member_type, info["type"]))
                        st.member_type = info["type"]
            # absences
            if absence_ok.get(source_id, False):
                for key, st in source_states.items():
                    if key not in present and st.status in (
                        IntervalStatus.CURRENT, IntervalStatus.REAPPEARED,
                        IntervalStatus.POSSIBLY_DISAPPEARED,
                    ):
                        if st.last_seen == day:
                            continue  # present counted above
                        st.consecutive_absent += 1
                        if st.first_absent is None:
                            st.first_absent = day
                        if st.consecutive_absent >= confirm_absences:
                            if st.status != IntervalStatus.DISAPPEARED:
                                st.status = IntervalStatus.DISAPPEARED
                                events.append(_evt(day, key, ChangeType.CONFIRMED_DISAPPEARED,
                                                   st.last_seen.isoformat(), None,
                                                   confidence=0.9))
                        elif st.status != IntervalStatus.POSSIBLY_DISAPPEARED:
                            st.status = IntervalStatus.POSSIBLY_DISAPPEARED
                            events.append(_evt(day, key, ChangeType.POSSIBLY_DISAPPEARED,
                                               st.last_seen.isoformat(), None,
                                               confidence=0.5))

    # persist
    store.con.execute("DELETE FROM membership_interval")
    store.con.execute("DELETE FROM change_event")
    for key, st in states.items():
        store.con.execute(
            """INSERT INTO membership_interval VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [key.participant_id, key.source_id, key.mic, key.family,
             ";".join(sorted(st.member_codes)) or None, key.membership_key,
             st.first_seen, st.last_seen, st.first_absent,
             None, st.status.value, st.supporting],
        )
    for e in events:
        store.con.execute(
            "INSERT INTO change_event VALUES (?,?,?,?,?,?,?,?,?)",
            [e["change_id"], e["observed_at"], e["participant_id"],
             e["membership_key"], e["change_type"], e["old_value"],
             e["new_value"], e["source_id"], e["confidence"]],
        )
    return {"intervals": len(states), "events": len(events)}


def _evt(day: date, key: _Key, ctype: ChangeType, old: str | None, new: str | None,
         confidence: float = 1.0) -> dict:
    cid = sha256(
        f"{day}|{key.participant_id}|{key.membership_key}|{ctype}|{old}|{new}".encode()
    ).hexdigest()[:32]
    return {
        "change_id": cid,
        "observed_at": day,
        "participant_id": key.participant_id,
        "membership_key": key.membership_key,
        "change_type": ctype.value,
        "old_value": old,
        "new_value": new,
        "source_id": key.source_id,
        "confidence": confidence,
    }
