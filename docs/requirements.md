This project/application (app) will demonstrate how to create an agentic system that uses a corpus to drive its behavior.
The folder `data/corpus` is a set of Dungeons & Dragons 5e markdown files that describes how the game works. 
The goal is to generate a story as the campaign progresses according to the rules of D&D 5e. 
The AI will act in the best interest of each player given their personalities and dispositions.
Turns are made. Players interact with each other and the environment.

Initially, just create the backend main.py typer cli and put items in models and core as needed.
Do not create an api or web site.

Use these packages for general AI work:
* llama_index
* chromadb
* networkx
* spacy
* pyvis
* markdown-it-py
* memgraph
* pydantic

The app will create:
* Four player characters (PCs)
* A new campaign that consists of one or more parties. By default, all PCs are in the same party.
* A player by itself is not in a party. There must be at least two players in any party, but the term "party" is often used generically where a person is in a party of one.
* A `data/world.yaml` file will be created and persisted. This will be the "campaign". See "World Generation" below.

Use the local ollama server and model `qwen2.5:14b` for tool calling.

Assume memgraph is running on bolt://localhost:7687

# Use Cases
```
python -m src.backend.main index-corpus
python -m src.backend.main new-campaign "MyAdventure"
python -m src.backend.main turn --campaign "MyAdventure.yaml"
```

# The Pillars of Adventure
A party or character can be in one of the following game modes:
- Exploration, where the party is asking the DM questions. 
- Social Interaction, where the party is interacting with NPCs.
- Travel, where the party is moving between places in an automatic manner. 
- Combat (or Melee) where the rules of combat turns are enforced; e.g. Roll for initiative, surprise, attacking, etc.


# Agents
There will be one agent for the following:
* The dungeon master (DM) who coordinates the players, party members, and their state. The DM determines what events happen, e.g."A monster hit Thor for 3 hp damage. He rolled a d20 and got a 14, but with a savings bonus, saved for poison." Then it calls the add_hp(id, -3), which then determines if Thor died or not.
* Each player (P)
  * Player character (PC)
  * Non-player character (NPC) like monsters and town folk.
* The world, which can update itself, like weather in certain regions, fires, and other events. Items can disappear, as if stolen. NPCs can pick up an item, which now moves with that player.


# World Generation
The structure of a "world" is a file containing an `objects` key that is a list of objects in the world. The id of each object is its offset in the array. When an object is created, the next sequential id is incremented and added to the world object. When an object (O1) is deleted, then all children of O1 are either also deleted (like O1 was a bag that was thrown into a volcano), or moved to the O1's parent (like the chest was destroyed, but not the contents in it).
```yaml
name: string
max_id: int
delete_ids: int[]
objects: dictionary of objects, each key is an integer.
```

# Currency, Cost, Price
* Copper (cp) $1
* Silver (sp) $10
* Electrum (ep) $50
* Gold (gp) $100
* Platinum (pp) $1000
50 coins weigh a pound.

# Objects

## Parent/child hierarchy type system
Here is the location ancestry (parent-child relationship).
All location objects must have a parent. The System is the only item with a null parent.

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

Object
```yaml
  id: int
  parent:
  type: string, e.g. PC, NPC, system, planet, continent, bed, sword, ring
  name: OPTIONAL
  description:
  location: [x, y, z]
  size: [l, w, h]
  weight: in pounds
  cost: in copper pieces
  is_moveable: BOOL - true means the location can change. False means the children cannot move outside the size. A bag on an elf will have location [0,0,0] and size [0,0,0] to mean that the elf has the bag, assumes the elf's location, and items (like a ring) can be in the bag (the parent is the bag) or out of the bag (the parent is the elf wearing/equiping the ring).
  is_virtual: BOOL - true means the children can extend beyond the parent; e.g. a party. A party might have a a location, like in a room, but each party member can be in different locations of the room. When a member says "let the party move to another room", then all party members change their location to [0,0,0], to denote that all members came together, and the party's parent becomes another room and the relative location is set for the party, e.g. [-3, 7, 0].
```

Other properties can be added as needed, like number_of_charges, bonus, color, material, etc.



AbilityScores
```yaml
str: int
int: int
wis: int
dex: int
con: int
chr: int
```

Player
```yaml
name: str, e.g. Thor
race: str, e.g. Human
classes:
- type: e.g. Ranger
  level: int, e.g. 9
abilities: AbilityScores
hp:
  max: int
  current: int
mana:
  max: int
  current: int
health:
  max: int
  current: int

```

PC (Player)
```yaml
```

NPC (Player)
```yaml
```


# Location
Each object has a location relative to its parent. If the object's location is [0,0,0] then the object is said to be "with" or "in" the parent, and that the exact location (or coordinates) of the item is irrelevant. 
Examples:
* A sword has parent: PC elf. This means that the sword is being carried by the elf.
* A backpack has parent: PC elf. This means the elf "has" a backpack.
* A ring has parent backpack. This means the ring is in the elf's backpack.
* A table has parent inn, so that table is in the middle of the inn.

Possessions are also a parent/child relationship as illustrated above.

The resolution of the world is 5 feet. So a person takes up 25 square feet. A party might also have 4 people and the party has a location, and all 4 people are in that party's 5x5 space - each persons location is [0,0,0]. A member can move outside.


# Game

The game begins with the DM generating the world, which starts with a premade template of well-known lands, regions, cities, and shops; one or more players characters in a region, all while keeping a natural location hierarchy.
Not all items in the world need to be generated in detail. Only the ones that any party member is or has experienced. So new cities can be created just-in-time as needed.
Once an item is created, it stays in the world until it is destroyed, lost, or dies.
The world is a python object (dict) is periodically (in a folder "worlds", which are campaigns, under a named YAML file, like "MyFirstWorld.yaml") persisted as a YAML file after it changes each turn.

Only tools are allowed to update the world. If a player moves, then its location is updated with a "move_object" tool/action that the LLM generates.

This world file (W) can get very big, and is not ideal to be pushed into an LLM. Rather, a subset of it will be generated as follows:
* A deep copy (W1) of the world is made.
* For the player or party at hand, its location will delete all objects in W1 (including their children) that cannot be seen. For example, if the party is in a city between two inns, then those two inns are seen, but all items in the inn are not seen, so they are deleted. All parents of a seen item are also seen.
* Then W1 will be submitted to the agent for processing along with other prompts that the game requires.


# Tools

* create_object(type, parent_id, **args)
* move_object(id, parent_id)
* set_object_property(id, name, value)
* add_hp(id, delta)
* delete_object(id, cascade: bool)
* get_object(id)


# Types
* id: int of an object
* location: list[3] of [x,y,z]


# Library Functions
* get_sub_world(world, id)


# Other Requirements
* Start with a fixed seed per campaign for reproducible runs; log seeds for each turn and major random events.
* Precise visibility rules: LOS, range, occlusion, light/dark states; define perception checks and passive/active perception thresholds.



# Web Site
This vue.js website will have the following features:
- A nice navigation of the initial options that show:
  - The user can register: username and password, which are stored in cache/users.json where security is deliberately low. The passwords will be salted and hashed, but the same algorithm will be used to authenticate.
  - The user can log in
  - Create a cookie on the user's machine so they don't have to sign in every time.
  - A list of existing campaigns of which the users can join. When a user joins a campaign, for the first time, it will need to create a character region, race and class, name, background. A background will be generated based on the character's region and race. The regions can be found in https://elderscrolls.fandom.com/wiki/Regions_(Daggerfall). The user can accept the background or replace it with their own background.
  - When a user joins an existing campaign that it has already joined before, the DM gives a summary of where it left off and a description of where the character is and the other players around the character in the party.
  - Campaigns can have multiple players, and each player can be in at most one party.
- Anyone in the party can create a snapshot of the campaign game to save it for restoration later. These can be found for any campaign. These snapshots are like git branches. They form a tree. If I play snapshot (or saved game) "A" and I save it as "B", then "A" is the parent of "B", etc.
- Snapshots are copies of the campaign folder. Each campaign as a folder under the "campaigns" folder. In the example above, the folder system would be:
```
campaigns/
  A/
    campaigns/
      B/
```

When a user joins a campaign, the "campaign" page shows:
- the name of the campaign
- the players in the campaign
- When the character is created to join a campaign, show the dice roll for each attribute plus a bonus points d6. Give the user the ability to roll again. The bonus points can be added to one or more attributes - the user gets to decide.
- each player's hit points, encumberance, and health - a gradient of green to yellow to red.
- A chat windows that all players in the campaign see. This will be a signal-r like websocket that syncs across all player's browser.
- If player P1 types something, upon ENTER, all players see it, and the DM responds to it. To prevent confusion, each line entered will be be preceded with the persons name, e.g. "Thor: Where are we going?" "DM" will represent the dungeon master. Monsters and NPCs will also be part of the chat, but they will not be able to see what the players type - only what the DM relays to them. Remember, an NPC can see what a player does or says to them, but not what the players say to each other. The player must explicitly state "Dragon, please let us pass." so that the DM knows the player is talking to the dragon. Any question or statement not qualified with a target will assume the party as the target. "What should we do?" says the player. The DM does not reply. "DM: check the lock for traps" will tell the DM you are giving a command. In combat, each player takes a turn. So if it's Thor's turn, the DM will only listen to Thor. Other's can chat, but the DM is waiting for Thor to say what he will do.
- At the bottom of the chat will be common buttons for common actions depending on the mode of the game. For example, if in combat, and it's your turn, you will see buttons like: Attack, Cast Spell, Dash, Disengage, Dodge, Help, Hide, Ready, Search, Use Object, etc. But only if you are allowed to do those things. You might be silences, so you cannot cast a spell, which will be disabled with a tooltip that says so. Unconsciousness is an automatic skip.


# Profile
Under the profile name (or icon) create a dropdown menu that contains:
- Admin - only shown if the user is an admin. Clicking goes to the /admin page.
- Logout - and remove the current location of this option



# Admin
Create an page with route "/admin". Only allow that if the user has property "admin" true.
This page will show all campaigns each with an "X" to delete it completely. Before deleting a campaign, create a zip of the campaign folder and store that under the campaigns folder.
Under each campaign, show the players each with an "X" to delete the from the campaign.
When I type http://localhost:5173/admin on the URL, it should not redirect me to http://localhost:5173/login?redirect=/admin because I'm already logged in and I have "admin" property set to ture.
If the user is an admin, then add a profile menu option called "Admin" that link to the /admin page.
On the admin page, add left navigation bar. Add "Console" that links to "/admin".
Where a world is shown (e.g. "Daggerfall"), when the user lci