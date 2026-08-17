from __future__ import annotations

from typing import Sequence

# A from-scratch policy loses ~every match for its first few thousand games: the gate is uncalibrated,
# the 432-cell action space is barely explored, and the reward is dominated by the chip/crown terms it
# has not learned to reach yet. Judging it before then is not "detecting a plateau", it is measuring
# initialisation -- MEASURED: a fresh run tripped the low-winrate rule at 25 matches (0%, avg_rew -30.9)
# and killed itself twice before this guard existed. Nothing may intervene until the run has had a
# real chance to learn.
MIN_MATCHES = 3000


def should_intervene(
    winrate: float,
    avg_reward: float,
    recent_winrates: Sequence[float] | None = None,
    recent_rewards: Sequence[float] | None = None,
    matches: int | None = None,
    low_winrate_threshold: float = 35.0,
    low_reward_threshold: float = -5.0,
    plateau_drop_threshold: float = 10.0,
    plateau_min_recent: int = 3,
    min_matches: int = MIN_MATCHES,
) -> tuple[bool, str]:
    """Return whether PPO looks unhealthy and why.

    This is intentionally simple and conservative: it triggers when the current policy is
    clearly weak (very low winrate or very low average reward) or when the recent trend has
    collapsed despite earlier progress. The thresholds are chosen to match the request for
    stopping PPO when it plateaus below roughly 30-40% or plays badly.

    ``matches`` is the number of matches completed so far. Below ``min_matches`` this ALWAYS
    returns healthy -- an untrained policy is supposed to look terrible, and treating that as a
    plateau turns the watchdog into a crash loop.
    """
    if matches is not None and matches < min_matches:
        return False, f"warming up ({matches}/{min_matches} matches)"

    recent_winrates = list(recent_winrates or [])
    recent_rewards = list(recent_rewards or [])

    reasons: list[str] = []

    if winrate < low_winrate_threshold:
        reasons.append(f"winrate {winrate:.1f}% below {low_winrate_threshold:.0f}%")
    if avg_reward < low_reward_threshold:
        reasons.append(f"avg reward {avg_reward:.1f} below {low_reward_threshold:.1f}")

    if len(recent_winrates) >= plateau_min_recent and len(recent_rewards) >= plateau_min_recent:
        recent_wins = recent_winrates[-plateau_min_recent:]
        recent_rews = recent_rewards[-plateau_min_recent:]
        if recent_wins[-1] <= recent_wins[0] - plateau_drop_threshold:
            reasons.append(
                f"plateau: winrate fell from {recent_wins[0]:.1f}% to {recent_wins[-1]:.1f}%"
            )
        if recent_rews[-1] <= recent_rews[0] - plateau_drop_threshold:
            reasons.append(
                f"plateau: avg reward fell from {recent_rews[0]:.1f} to {recent_rews[-1]:.1f}"
            )

    if reasons:
        return True, "; ".join(reasons)
    return False, "healthy"
