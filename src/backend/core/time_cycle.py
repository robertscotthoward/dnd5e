"""Day/night cycle tracking for campaign turns."""

# Hours per in-game turn (each party action advances time by this much)
HOURS_PER_TURN = 1

# Night: 20:00 – 05:59 (8 PM to just before 6 AM)
NIGHT_START = 20
NIGHT_END = 6  # exclusive — 6 AM is dawn (daylight)

# Darkvision races do not suffer night perception penalty
DARKVISION_RACES = {
    "dwarf",
    "elf",
    "half-elf",
    "half-orc",
    "gnome",
    "tiefling",
    "drow",
    "deep gnome",
}


def is_night_hour(hour: int) -> bool:
    """Return True if the given hour (0-23) falls within night."""
    return hour >= NIGHT_START or hour < NIGHT_END


def time_description(hour: int) -> str:
    """Return a short narrative label for the given hour."""
    if hour < 6:
        return "night"
    if hour < 9:
        return "dawn"
    if hour < 12:
        return "morning"
    if hour < 14:
        return "midday"
    if hour < 18:
        return "afternoon"
    if hour < 20:
        return "dusk"
    return "night"


def advance_time(day_number: int, hour_of_day: int, hours: int = HOURS_PER_TURN) -> dict:
    """
    Advance in-game time by `hours` hours.

    Returns a dict with updated day_number, hour_of_day, and is_night.
    """
    total_hours = hour_of_day + hours
    new_day = day_number + total_hours // 24
    new_hour = total_hours % 24
    night = is_night_hour(new_hour)
    return {
        "day_number": new_day,
        "hour_of_day": new_hour,
        "is_night": night,
        "time_description": time_description(new_hour),
    }


def has_darkvision(race: str) -> bool:
    """Return True when the given race name (case-insensitive) has darkvision."""
    return race.strip().lower() in DARKVISION_RACES


def perception_disadvantage(is_night: bool, race: str) -> bool:
    """
    Return True if a perception check should have disadvantage.

    Disadvantage applies outdoors at night for non-darkvision races.
    The caller is responsible for verifying outdoor context if needed;
    this function just encodes the race + night rule.
    """
    if not is_night:
        return False
    return not has_darkvision(race)
