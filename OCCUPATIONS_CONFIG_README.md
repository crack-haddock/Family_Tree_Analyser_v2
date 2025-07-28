# Occupations Configuration

This file (`occupations_config.json`) contains occupation groupings and patterns for normalizing historical job titles and occupations found in genealogical data.

## Structure

### occupation_groups
Maps normalized occupation group names to lists of aliases and variations:

```json
"House Keeper": [
  "housewife",
  "housekeeper", 
  "unpaid duties",
  "domestic duties"
]
```

### occupation_patterns
Common patterns that can be combined with other occupations:

```json
"apprentice_pattern": "apprentice",
"assistant_pattern": "assistant"
```

## Usage Guidelines

1. **Group Names**: Use clear, modern terminology for the group name (e.g., "House Keeper" not "Housewife")
2. **Aliases**: Include all historical variations, spelling differences, and related terms
3. **Case Insensitive**: All matching is done case-insensitively
4. **Partial Matching**: The system can handle partial matches within occupation text

## Common Historical Occupation Categories

- **Domestic Work**: House keeping, servants, domestic duties
- **Industrial**: Mill workers, factory hands, coal miners
- **Agricultural**: Farm workers, agricultural labourers, shepherds
- **Transportation**: Railway workers, carters, coachmen  
- **Trades**: Blacksmiths, carpenters, bakers, tailors
- **Professional**: Teachers, clerks, shopkeepers
- **Military**: Soldiers, pensioners, various ranks

## Adding New Occupations

When you find new occupation titles in your data:

1. Determine which existing group they belong to, or if a new group is needed
2. Add variations to the appropriate group's alias list
3. Consider historical spelling variations and abbreviations
4. Include both formal and informal terms

## Examples of Variations to Consider

- Spelling: "labourer" vs "laborer"
- Abbreviations: "agri lab" for "agricultural labourer"  
- Gendered forms: "seamstress" vs "tailor"
- Regional terms: "collier" for "coal miner"
- Historical terms: "navvy" for construction worker

## Timeline Features

The system will also capture year/date information when available to show:
- Career progression over time
- What ancestors were doing in specific years/periods
- Changes in occupation types across generations
