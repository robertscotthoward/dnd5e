# Map and Item Location

## Purpose
Display the game world hierarchy as an interactive map with spatial context.

## Key Features

### Map State Persistence
1. **Persistent State** — Position, size, and zoom level saved to `localStorage` and restored on reopen
2. **Draggable** — Drag title bar to reposition anywhere on screen
3. **Resizable** — Drag edges/corners to resize; state persists
4. **Zoom** — Scroll to zoom in/out; level persists
5. **Reset** — Right-click context menu "Reset Map" clears all saved state, returns to defaults

### Map Interaction
6. **Draggable Canvas** — Pan map by dragging (no scroll bars)
7. **Center on Player** — Right-click menu option to center view on player
8. **ESC to Close** — ESC key closes the map dialog (and all future dialogs)

### Visual Display
9. **Tooltips with Dimensions** — Show object dimensions (L×W×H in feet) for hovered object and all ancestors
10. **Tooltips with Ancestry** — Show parent hierarchy as "NAME (TYPE)" list in tooltip (parent, grandparent, etc.)
11. **Render Order** — Items rendered in layers: floors/regions first, then walls, then furniture, then players on top
12. **Visual Differentiation** — Each object type has unique color with RGB components at least 15 units apart

### Admin Features
13. **Hierarchy Display** — Tree view showing object name, type, and description (format: "NAME (TYPE) - DESCRIPTION")
14. **Detail Panel** — Click tree item to show full object properties in right panel
15. **Context Menu** — Right-click tree item to create child objects or delete item

### Technical
16. **Absolute Positioning** — Calculate absolute position from parent-relative coordinates for proper map rendering
17. All items displayed on the map initially should be filled rectangles with hover tips. 
18. Ground items should be large patches, perhaps rectangles that build a collage in some manner but do not overlap.

**Trigger**: F4 key opens the map dialog

## Location Calculation

### Overview
Every object in the world has a location relative to its parent. To render an object on the map, its absolute position must be calculated by traversing the parent hierarchy.

### Location Format (Source: requirements.md)
- **Format**: `[x, y, z]` — 3D coordinates in **feet** (not 5-foot units)
- **Resolution**: 5 feet (minimum meaningful unit for grid-based gameplay)
- **Special Case**: `[0, 0, 0]` means the **center** of the parent
- **Special Case**: `null` means "with" or "in" the parent (exact position irrelevant)

### Size Format
- **Format**: `[l, w, h]` — length, width, height in **feet**
- Every object is a box
- Example: A human might be `[1, 2, 6]` feet

### Parent-Child Hierarchy
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

### Absolute Position Calculation

**Algorithm**:
1. Start with the target object
2. Sum its location `[x, y, z]` with all ancestor locations
3. Stop when reaching System (the root)
4. If any object has `location: null`, it inherits its parent's absolute position

**Formula**:
```
absolute_position = Σ(object.location + parent.location + grandparent.location + ...)
```
For `null` locations, use parent's absolute position.

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
  location: [5000, 10000, 0]  # feet, not units
  
City (Baldur's Gate):
  parent: Sword Coast
  location: [250, 375, 0]  # feet from region center
  
Inn (Elfsong Tavern):
  parent: Baldur's Gate
  location: [50, 75, 0]  # feet from city center
  size: [80, 60, 20]  # 80×60×20 feet
  
Room:
  parent: Inn
  location: [25, 40, 5]  # feet from inn center (1st floor)
  size: [20, 15, 8]  # 20×15×8 feet
  
Table:
  parent: Room
  location: [10, 15, 0]  # feet from room center
  size: [4, 3, 3]  # 4×3×3 feet
  
Sword:
  parent: Table
  location: [0, 0.5, 1.5]  # feet from table center (on top)
  size: [0.2, 3, 0.1]  # 0.2×3×0.1 feet
```

**Absolute position of Sword**:
```
[0, 0, 0]         (System)
+ [0, 0, 0]       (Toril)
+ [5000, 10000, 0] (Sword Coast)
+ [250, 375, 0]    (Baldur's Gate)
+ [50, 75, 0]      (Elfsong Tavern)
+ [25, 40, 5]      (Room)
+ [10, 15, 0]      (Table)
+ [0, 0.5, 1.5]    (Sword)
─────────────────
= [5335, 10505.5, 6.5] feet
```

## Special Cases

### Possession (location = null)
```yaml
Elf (PC):
  location: [100, 150, 0]  # feet
  size: [1, 2, 6]  # feet

Backpack:
  parent: Elf
  location: null  # "with" the elf, exact position irrelevant

Ring:
  parent: Backpack
  location: null  # "in" the backpack
```

**Absolute positions**:
- Elf: `[100, 150, 0]` feet
- Backpack: `[100, 150, 0]` feet (inherits elf's position)
- Ring: `[100, 150, 0]` feet (inherits backpack's position)

### Center of Parent (location = [0, 0, 0])
```yaml
Inn:
  location: [50, 75, 0]
  size: [80, 60, 20]  # 80×60×20 feet

Table:
  parent: Inn
  location: [0, 0, 0]  # center of inn
```

**Absolute position of Table**: `[50, 75, 0]` feet (same as inn center)

### Moveable Objects
Objects with `is_moveable: true` can change their parent or location:
```yaml
# Before: Sword on table
Sword:
  parent: Table (id: 42)
  location: [0, 1, 0.5]  # feet from table center

# After: Sword picked up by elf
# Tool call: move_object(sword_id, elf_id)
Sword:
  parent: Elf (id: 15)
  location: null  # "with" the elf
```

### Virtual Containers
Objects with `is_virtual: true` allow children to extend beyond parent size:
```yaml
Party:
  location: [100, 150, 0]  # feet
  size: [5, 5, 0]  # 5×5 feet
  is_virtual: true

Thor (PC):
  parent: Party
  location: null  # "with" the party

Frodo (PC):
  parent: Party
  location: [10, 15, 0]  # 10 feet east, 15 feet north of party center
```

**Absolute positions**:
- Party: `[100, 150, 0]` feet
- Thor: `[100, 150, 0]` feet (with party, null location)
- Frodo: `[110, 165, 0]` feet (outside party's 5×5 size, but allowed because is_virtual: true)

## Constraints

### Size Constraints
- **Child size ≤ Parent size**: A child's dimensions should never exceed its parent's dimensions
- **Total volume**: The total volume of all children should never exceed the parent's volume
- Example: A 6-foot human cannot fit in a 2×2×2 foot chest

### Grid Resolution
- World resolution: 5 feet
- A person takes up 25 square feet (5×5 grid square)
- Positions can be more precise than 5 feet, but gameplay typically rounds to 5-foot increments

## Rendering

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
  location: [x, y, z]  # feet from parent center
  size: [l, w, h]      # feet (length, width, height)
```

**Bounding box**:
- **Center**: `absolute_position`
- **Extent**: `size / 2` in each direction
- **Min corner**: `[x - l/2, y - w/2, z]`
- **Max corner**: `[x + l/2, y + w/2, z + h]`

## Implementation

### Recursive Function
```python
def get_absolute_position(obj_id, world):
    """Calculate absolute position in feet."""
    obj = world['objects'][obj_id]
    
    # Handle null location (inherit parent's position)
    if obj['location'] is None:
        if obj['parent'] is None:
            return [0, 0, 0]
        return get_absolute_position(obj['parent'], world)
    
    # Base case: root object
    if obj['parent'] is None:
        return obj['location']
    
    # Recursive case: sum with parent's position
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
- **Units**: All coordinates and sizes are in **feet**
