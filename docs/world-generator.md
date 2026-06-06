# World Generator

This game generates items in the world dynamically (like Minecraft) as the player moves through the world.

Each object should have a size range like this: 
```yaml
size: 
  min: [l, w, h]
  max: [l, w, h]
```
Ensure the every min components never exceed its corresponding max component and all values are not negative.
The unit is 5 feet, so a height of 0.5 means 2.5 feet. A "grid square" (or just "square") means a 5'x5' area. Default ceilings are 10' tall, or 2 units.
All types that a player can enter (like an inn, a room, or a cave) or stand on (like a street, path, floor) must be integer units.
In some cases, a hole in the wall might be 0.2, which is too small to crawl through for a human.
Use standard knowledge of type sizes to create a min and max range. 
A planet might have 2e14 squares on its surface. A city might be 250K squares. Daggerfall was a big city of 900K squares.
The height of area types, like region, planet, city, town, floor, forum, road should be 0. The children (like buildings, rooms, trees, statues) on those areas will likely have height.



The parent-child hierarchy:
```
System: Realmspace
  Planet: Toril
    Continent: Faerûn
      Region: The Sword Coast
        City: Baldur's Gate
          Inn: The Elfsong Tavern
            Room
              Bed
              Storage
              Chest
              Closet
              Chair
              Table
              Candelabrum
              Brazier
              Tapestry
              Painting
              Washstand
              Armoir
            Basement
            Closet
            Attic
            Nook
            Study
            Hallway
            Vault
            Cellar
            Pantry
            Kitchen
            Vestibule
            Fumitory
          Dungeon
          Cave
          Tavern: The Yawning Portal
          Festhall: The House of Wonder
          General Store: Aurora’s Whole Realms Shop
          Magic Shop: Sorcerous Sundries
          Market: The Grand Bazaa
          Black Market: The Low Lantern
          Temple: The Hall of Justice
          Prison: Revel’s End
          Manor/Estate: Cassalanter Villa
          Academy: The Blackstaff Tower
          Smithy: Hammer and Tongs
        Town: Phandalin
        Library-Fortress: Candlekeep
        Citadel: Helm’s Hold
        Military Outpost: High Forest
        Forest: The High Forest
        Mountain Range: The Spine of the World
        Swamp: The Mere of Dead Men
        Island: The Moonshae Isles
        Trade Road: The High Road
```