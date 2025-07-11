Family Tree Analyser v1 - Development Summary
=============================================

This README documents the full context and rationale for the development of `main.py` in this repository, enabling future contributors to understand, reconstruct, and continue the work.

Project Purpose
---------------
This project is a Python script for analysing family tree data in GEDCOM format using the `ged4py` library. It provides a menu-driven interface for querying and reporting on individuals, birthplaces, occupations, and ancestor relationships, with robust handling of edge cases and data extraction from complex GEDCOM records.

Key Features Implemented
------------------------
1. **Menu-Driven Queries**: The script offers a menu with options for:
   - Negative age detection (death before birth or birth in the future)
   - Orphaned individuals (not referenced by or referencing any family)
   - Birthplace queries (Ireland, Ulster, France, Holland, Germany, Scotland)
   - Oldest people (by birth year)
   - Birthplace counts (by nation and county/city)
   - Occupation counts (by total instances and unique people)
   - Individuals with multiple birthplaces
   - Detailed birth details for a selected person (all dates/places from various tags)

2. **Ancestor Filtering**: Users can restrict queries to direct ancestors of a selected root individual, with optional birth year range filtering.

3. **Birthplace Classification**:
   - Robust grouping by nation and county/city, including fuzzy matching for common misspellings (e.g., "glascow").
   - Place-to-county mappings for UK counties/cities.
   - Special handling for counties/cities, incrementing both county and nation counts.
   - Clear reporting for "Unspecified" (blank) and "Could not classify" birthplaces, with detailed listings for unclassified places.

4. **Occupation Extraction**:
   - Extraction from OCCU tags and all NOTE tags (including census/1939 Register notes), recursively.
   - Regex-based detection of likely occupation phrases.
   - Reporting by total instances, unique people, and listing all occupations per person.

5. **Multiple Birthplaces**:
   - Option to list individuals with more than one unique birthplace (from multiple PLAC tags under BIRT events).

6. **Detailed Birth Details**:
   - Option to show all birth dates and places for a selected person, extracting from BIRT/PLAC, BAPM/PLAC, CHR/PLAC, top-level PLAC, and NOTE tags.
   - Extraction of birthplaces from NOTE tags with "Birthplace:" and lines with commas (likely places).
   - Tag source shown for each place.

7. **Robust Date Parsing**:
   - Handles missing/partial dates and prompts for sorting/filtering.

8. **Code Structure**:
   - All logic is contained in `main.py`.
   - No other files are required for the core functionality.

Development Rationale
---------------------
- The script was designed to handle real-world GEDCOM data, which often contains inconsistencies, missing information, and complex tagging.
- Special attention was given to edge cases in birthplace and occupation extraction, ensuring accurate classification and reporting.
- Ancestor filtering allows focused analysis on direct lineages, supporting genealogical research.
- The menu-driven interface makes the tool accessible for both technical and non-technical users.

How to Continue Development
---------------------------
- All enhancements, bug fixes, and new features should be added to `main.py`.
- For further improvements (e.g., better census birthplace extraction), refer to the summary above for context and rationale.
- Use this README as the starting point for any new conversation or development session.

Contact & Support
-----------------
For questions or to continue development, start a new conversation referencing this README for full context.
