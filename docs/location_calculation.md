# Location Calculation in the Realm

## Overview
Every object in the world has a location relative to its parent. To render an object on the map, its absolute position must be calculated by traversing the parent hierarchy.

## Location Format
- **Format**: `[x, y, z]` — 3D coordinates
- **Resolution**: 5 feet per unit
- **Special Case**: `[0, 0, 0]` means "with" or "in" the parent (no specific position)

## Parent-Child Hierarchy
All objects except the System root have a parent:
```
System: Realmspace [null parent]
  └─ Planet: Toril
      └─ Continent: Faerûn
          └─ Region: The Sword Coast
              └─ City: Baldur's Gate
                  └─ Inn: The Elfsong Tavern
                      └─ Room
                          └─ Bed [x, y, z]
```

## Absolute Position Calculation

### Algorithm
1. Start with the target object
2. Sum its location `[x, y, z]` with all ancestor locations
3. Stop when reaching System (the root)

### Formula
```
absolute_position = Σ(object.location + parent.location + grandparent.location + ...)
```

### Example: Calculating a Sword's Position

```yaml
# Object hierarchy
System (Realmspace):
  location: [0, 0, 0]
  
Planet (Toril):
  parent: System
  location: [0, 0, 0]
  
Region (Sword Coast):
  parent: Toril
  location: [1000, 2000, 0]
  
City (Baldur's Gate):
  parent: Sword Coast
  location: [50, 75, 0]
  
Inn (Elfsong Tavern):
  parent: Baldur's Gate
  location: [10, 15, 0]
  
Room:
  parent: Inn
  location: [5, 8, 1]  # 1st floor
  
Table:
  parent: Room
  location: [2, 3, 0]
  
Sword:
  parent: Table
  location: [0, 1, 0.5]  # 0.5 = 2.5 feet above table
```

**Absolute position of Sword**:
```
[0, 0, 0]        (System)
+ [0, 0, 0]      (Toril)
+ [1000, 2000, 0] (Sword Coast)
+ [50, 75, 0]     (Baldur's Gate)
+ [10, 15, 0]     (Elfsong Tavern)
+ [5, 8, 1]       (Room)
+ [2, 3, 0]       (Table)
+ [0, 1, 0.5]     (Sword)
─────────────────
= [1067, 2102, 1.5]
```

**In feet**: `[5335, 10510, 7.5]` feet

## Special Cases

### Possession (location = [0, 0, 0])
```yaml
Elf (PC):
  location: [20, 30, 0]

Backpack:
  parent: Elf
  location: [0, 0, 0]  # "with" the elf

Ring:
  parent: Backpack
  location: [0, 0, 0]  # "in" the backpack
```

**Absolute positions**:
- Elf: `[20, 30, 0]`
- Backpack: `[20, 30, 0]` (same as elf)
- Ring: `[20, 30, 0]` (same as backpack)

### Moveable Objects
Objects with `is_moveable: true` can change their parent or location:
```yaml
# Before: Sword on table
Sword:
  parent: Table (id: 42)
  location: [0, 1, 0.5]

# After: Sword picked up by elf
# Tool call: move_object(sword_id, elf_id)
Sword:
  parent: Elf (id: 15)
  location: [0, 0, 0]
```

### Virtual Containers
Objects with `is_virtual: true` allow children to extend beyond parent size:
```yaml
Party:
  location: [20, 30, 0]
  size: [1, 1, 0]  # 5×5 feet
  is_virtual: true

Thor (PC):
  parent: Party
  location: [0, 0, 0]  # Same as party

Frodo (PC):
  parent: Party
  location: [2, 3, 0]  # 10 feet east, 15 feet north of party
```

**Absolute positions**:
- Party: `[20, 30, 0]`
- Thor: `[20, 30, 0]` (with party)
- Frodo: `[22, 33, 0]` (outside party's 5×5 size, but allowed)

## Rendering Implications

### Layer Order (Z-Index)
Objects render in order:
1. **Regions/Ground** (z = 0)
2. **Walls** (z > 0)
3. **Furniture** (z > 0)
4. **Players** (z > 0, top layer)

### Visibility Calculation
Only objects within line-of-sight from the player should render:
- Calculate absolute positions for all objects
- Filter by distance and occlusion
- Render visible objects on map canvas

### Size and Bounds
```yaml
Object:
  location: [x, y, z]
  size: [length, width, height]  # in 5-foot units
```

**Bounding box**:
- **Center**: `absolute_position`
- **Extent**: `size / 2` in each direction
- **Min corner**: `[x - l/2, y - w/2, z]`
- **Max corner**: `[x + l/2, y + w/2, z + h]`

## Implementation Notes

### Recursive Function
```python
def get_absolute_position(obj_id, world):
    obj = world['objects'][obj_id]
    if obj['parent'] is None:
        return obj['location']
    
    parent_pos = get_absolute_position(obj['parent'], world)
    return [
        parent_pos[0] + obj['location'][0],
        parent_pos[1] + obj['location'][1],
        parent_pos[2] + obj['location'][2]
    ]
```

### Caching
Absolute positions should be cached and invalidated when:
- Object's `location` changes
- Object's `parent` changes
- Any ancestor's `location` or `parent` changes

### Coordinate System
- **X-axis**: East (positive) / West (negative)
- **Y-axis**: North (positive) / South (negative)
- **Z-axis**: Up (positive) / Down (negative)
- **Origin**: System root at `[0, 0, 0]`
