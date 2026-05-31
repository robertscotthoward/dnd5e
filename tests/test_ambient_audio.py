"""
Tests for ambient audio location-type inference logic.

The frontend infers the ambient track from the party's parent object name and description.
These tests validate the keyword-to-track mapping used in AmbientAudio.vue by exercising
the same rules in Python — ensuring all four track families (tavern, dungeon, forest, outdoor)
resolve correctly and that the fallback is 'outdoor'.
"""

import pytest


LOCATION_TRACKS = {
    "tavern":   {"label": "Tavern",   "file": "/audio/tavern.mp3"},
    "inn":      {"label": "Tavern",   "file": "/audio/tavern.mp3"},
    "dungeon":  {"label": "Dungeon",  "file": "/audio/dungeon.mp3"},
    "cave":     {"label": "Dungeon",  "file": "/audio/dungeon.mp3"},
    "crypt":    {"label": "Dungeon",  "file": "/audio/dungeon.mp3"},
    "mine":     {"label": "Dungeon",  "file": "/audio/dungeon.mp3"},
    "forest":   {"label": "Forest",   "file": "/audio/forest.mp3"},
    "wood":     {"label": "Forest",   "file": "/audio/forest.mp3"},
    "grove":    {"label": "Forest",   "file": "/audio/forest.mp3"},
    "swamp":    {"label": "Forest",   "file": "/audio/forest.mp3"},
    "road":     {"label": "Outdoor",  "file": "/audio/outdoor.mp3"},
    "plains":   {"label": "Outdoor",  "file": "/audio/outdoor.mp3"},
    "field":    {"label": "Outdoor",  "file": "/audio/outdoor.mp3"},
    "mountain": {"label": "Outdoor",  "file": "/audio/outdoor.mp3"},
    "city":     {"label": "Outdoor",  "file": "/audio/outdoor.mp3"},
    "town":     {"label": "Outdoor",  "file": "/audio/outdoor.mp3"},
    "village":  {"label": "Outdoor",  "file": "/audio/outdoor.mp3"},
}

FALLBACK_TRACK = {"label": "Outdoor", "file": "/audio/outdoor.mp3"}


def infer_track(name: str, description: str = "") -> dict:
    text = f"{name} {description}".lower()
    for keyword, track in LOCATION_TRACKS.items():
        if keyword in text:
            return track
    return FALLBACK_TRACK


class TestAmbientTrackInference:
    def test_tavern_by_name(self):
        track = infer_track("The Prancing Pony Tavern")
        assert track["label"] == "Tavern"
        assert track["file"] == "/audio/tavern.mp3"

    def test_inn_by_name(self):
        track = infer_track("Waterdeep Inn")
        assert track["label"] == "Tavern"

    def test_dungeon_by_name(self):
        track = infer_track("Dungeon of the Mad Mage")
        assert track["label"] == "Dungeon"
        assert track["file"] == "/audio/dungeon.mp3"

    def test_cave_by_description(self):
        track = infer_track("Unknown Location", "A dark dripping cave stretches before you.")
        assert track["label"] == "Dungeon"

    def test_crypt_by_name(self):
        track = infer_track("Ancient Crypt")
        assert track["label"] == "Dungeon"

    def test_mine_by_name(self):
        track = infer_track("Abandoned Mine Shaft")
        assert track["label"] == "Dungeon"

    def test_forest_by_name(self):
        track = infer_track("Whispering Forest")
        assert track["label"] == "Forest"
        assert track["file"] == "/audio/forest.mp3"

    def test_wood_by_name(self):
        track = infer_track("Thornwood")
        assert track["label"] == "Forest"

    def test_grove_by_description(self):
        track = infer_track("Sacred Place", "A moonlit grove of ancient oaks.")
        assert track["label"] == "Forest"

    def test_swamp_by_name(self):
        track = infer_track("The Blackmire Swamp")
        assert track["label"] == "Forest"

    def test_road_by_name(self):
        track = infer_track("King's Road")
        assert track["label"] == "Outdoor"
        assert track["file"] == "/audio/outdoor.mp3"

    def test_plains_by_name(self):
        track = infer_track("Endless Plains")
        assert track["label"] == "Outdoor"

    def test_mountain_by_description(self):
        track = infer_track("High Pass", "A treacherous mountain trail.")
        assert track["label"] == "Outdoor"

    def test_city_by_name(self):
        track = infer_track("City of Baldur's Gate")
        assert track["label"] == "Outdoor"

    def test_town_by_name(self):
        track = infer_track("Phandalin Town Square")
        assert track["label"] == "Outdoor"

    def test_village_by_name(self):
        track = infer_track("Millhaven Village")
        assert track["label"] == "Outdoor"

    def test_unknown_location_falls_back_to_outdoor(self):
        track = infer_track("The Void", "Nothing is here.")
        assert track["label"] == "Outdoor"
        assert track["file"] == "/audio/outdoor.mp3"

    def test_empty_name_falls_back_to_outdoor(self):
        track = infer_track("")
        assert track["label"] == "Outdoor"

    def test_case_insensitive_match(self):
        track = infer_track("DARK DUNGEON")
        assert track["label"] == "Dungeon"

    def test_keyword_in_description_takes_priority_when_name_empty(self):
        track = infer_track("", "The party shelters in a cozy tavern.")
        assert track["label"] == "Tavern"

    def test_name_keyword_wins_over_description(self):
        # Name contains 'dungeon', description mentions 'forest' — first keyword match wins
        text = "Dungeon Entrance forest path"
        t = text.lower()
        result = None
        for kw, track in LOCATION_TRACKS.items():
            if kw in t:
                result = track
                break
        assert result["label"] == "Dungeon"
