# Places Configuration System

The family tree analyzer uses a flexible JSON-based configuration system for managing global place name mappings. The system is designed to handle any nation's geographic structure with both administrative divisions and direct nation places.

## Design Principles

### Universal Flexibility
- **ALL nations** can have both counties/states/provinces AND direct nation places
- **UK nations** (England, Wales, Scotland) follow the same rules as any other nation
- **Future expansion** is built-in for any geographic region worldwide
- **Mixed hierarchies** are supported (e.g., England has both London and counties)

### Geographic Hierarchy
```
Nation
├── Direct Nation Places (major cities without administrative division)
└── Counties/States/Provinces
    └── Places within those divisions
        └── Local2 places (villages/hamlets)
            └── Known streets
```

## Current Examples

- **England**: Mixed (London + counties like Cheshire)
- **Scotland**: Direct places only (Glasgow, Edinburgh)
- **Wales**: Counties only (Flintshire, Denbighshire)  
- **Jamaica**: Direct places only (Manchester, St Elizabeth)
- **USA/France/Australia**: Ready for future expansion

## Files

- **`places_config.json`** - Main configuration file containing all place mappings
- **`add_place.py`** - Utility script to add new places easily
- **`view_places.py`** - Utility script to view current configuration
- **`test_places_config.py`** - Test script to verify the system works

## Configuration Structure

The `places_config.json` file has three main sections:

### 1. nation_counties
Maps nations to their counties/states/provinces:
```json
{
  "nation_counties": {
    "England": ["Cheshire", "Shropshire/Salop", "Lancashire", ...],
    "Wales": ["Flintshire", "Denbighshire", "Caernarvonshire"],
    ...
  }
}
```

### 2. county_places
Maps counties to their main places, with optional sub-places and streets:
```json
{
  "county_places": {
    "Flintshire": {
      "Mold": {
        "local2_places": ["Llanfferes"],
        "known_streets": []
      },
      "Buckley": {
        "local2_places": [],
        "known_streets": []
      }
    }
  }
}
```

### 3. nation_places
Direct nation-to-place mappings (for places without county associations):
```json
{
  "nation_places": {
    "Scotland": ["Glasgow", "Edinburgh"]
  }
}
```

## Usage

### Adding New Places

#### Using the utility script (recommended):
```bash
python add_place.py "New Town" Flintshire
python add_place.py "Another Place" "New County" Wales
```

#### Manual editing:
Edit `places_config.json` directly and add the place to the appropriate county section.

### Viewing Current Configuration

```bash
# View all nations and counties
python view_places.py

# View counties in a specific nation
python view_places.py Wales

# View places in a specific county
python view_places.py Wales Flintshire
```

### Programmatic Usage

The configuration is automatically loaded when creating a `ReportQueryHandler`:

```python
from query_handlers import ReportQueryHandler

handler = ReportQueryHandler(database)

# Configuration is now available in:
# handler.nation_counties
# handler.county_places  
# handler.nation_places

# Add new places programmatically:
handler.add_place_to_config("New Place", "Flintshire")
```

## Future Expansion Examples

The system is designed to easily accommodate any future geographic additions:

### Wales with Direct Places
```json
"nation_places": {
  "Wales": ["Cardiff", "Swansea"]
}
```
**Result**: Cardiff and Swansea appear alongside Flintshire county in hierarchy

### Scotland with Counties  
```json
"nation_counties": {
  "Scotland": ["Highlands", "Lowlands"]
},
"county_places": {
  "Highlands": {
    "Inverness": {"local2_places": [], "known_streets": []}
  }
}
```
**Result**: Glasgow/Edinburgh appear alongside Highlands county

### USA Expansion
```json
"nation_places": {
  "USA": ["Washington DC", "New York"]  
},
"nation_counties": {
  "USA": ["California", "Texas", "Florida"]
},
"county_places": {
  "California": {
    "Los Angeles": {"local2_places": [], "known_streets": []},
    "San Francisco": {"local2_places": [], "known_streets": []}
  }
}
```

### Jamaica with Parishes
```json
"nation_counties": {
  "Jamaica": ["Kingston Parish", "St. Andrew Parish"]
}
```
**Result**: Manchester and St Elizabeth appear alongside parish counties

## Technical Implementation Notes

### Automatic Detection
The system automatically determines storage format:
- **Direct nation places**: Stored as `"Place, Nation"`
- **County places**: Stored as `"Place, County, Nation"`  
- **Display logic**: Direct places appear at same level as counties
- **No conflicts**: Ghost counties are eliminated automatically

### Example Address Handling
- `"London, England"` → Direct nation place (same level as counties)
- `"Chester, Cheshire, England"` → County-based place
- `"Glasgow, Scotland"` → Direct nation place  
- `"Manchester, Jamaica"` → Direct nation place
- `"Cardiff, Wales"` → Ready for direct nation place (future)

## Benefits

1. **Easier Maintenance** - No need to modify source code to add places
2. **Cleaner Code** - Business logic separated from configuration data
3. **Quick Updates** - Use utility scripts or edit JSON directly
4. **Version Control** - Configuration changes are clearly visible in git
5. **Data Integrity** - JSON structure ensures consistent format
6. **Backup/Restore** - Easy to backup and restore place configurations

## Error Handling

The system includes robust error handling:
- Missing configuration file falls back to empty mappings
- JSON parsing errors are caught and reported
- Invalid configurations don't crash the application
- Automatic nation detection for counties

## Future Enhancements

- Import/export functionality for sharing configurations
- Validation tools to check for inconsistencies
- Bulk import from CSV files
- Integration with online geographical databases
