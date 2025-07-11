from ged4py.parser import GedcomReader
from datetime import datetime
import re

# Path to your `.ged` file
file_path = 'moss_tree.ged'

def parse_gedcom_date(date_val):
    if not date_val:
        return None
    date_str = str(date_val).strip()
    # Try full date
    for fmt in ('%d %b %Y', '%b %Y', '%Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    # Try to extract year if all else fails
    match = re.search(r'(\d{4})', date_str)
    if match:
        return datetime(int(match.group(1)), 1, 1)
    return None

def get_date(record, tag):
    for sub in record.sub_records:
        if sub.tag == tag:
            for sub2 in sub.sub_records:
                if sub2.tag == 'DATE':
                    return parse_gedcom_date(sub2.value)
    return None

def get_sort_order():
    order = input("Sort by birth year ascending or descending? (asc/desc, default asc): ")

    return order == 'desc'

def query_negative_age(parser, descending, ancestor_ids=None):
    today = datetime.today()
    results = []
    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        name = indi.name.format() if indi.name else ''
        birth = get_date(indi, 'BIRT')
        death = get_date(indi, 'DEAT')
        birth_year = birth.year if birth else None
        if birth and death:
            age = (death - birth).days // 365
            if age < 0:
                results.append((birth_year, name, birth, death, age))
        elif birth and not death:
            age = (today - birth).days // 365
            if age < 0:
                results.append((birth_year, name, birth, None, age))
    results = [r for r in results if r[0] is not None]
    results.sort(key=lambda x: x[0], reverse=descending)
    for birth_year, name, birth, death, age in results:
        if death:
            print(f"Name: {name}, Birth: {birth.date()}, Death: {death.date()}, Age: {age} (NEGATIVE AGE)")
        else:
            print(f"Name: {name}, Birth: {birth.date()}, Age: {age} (NEGATIVE AGE)")
    print(f"Total: {len(results)}")

def query_orphaned_individuals(parser, descending, ancestor_ids=None):
    all_inds = {indi.xref_id: indi for indi in parser.records0('INDI')}
    referenced_inds = set()
    for fam in parser.records0('FAM'):
        for sub in fam.sub_records:
            if sub.tag in ('HUSB', 'WIFE', 'CHIL'):
                if sub.value:
                    referenced_inds.add(sub.value)
    for indi in parser.records0('INDI'):
        for sub in indi.sub_records:
            if sub.tag in ('FAMC', 'FAMS'):
                if sub.value:
                    referenced_inds.add(indi.xref_id)
    orphaned = [indi for xref, indi in all_inds.items() if xref not in referenced_inds]
    results = []
    for indi in orphaned:
        name = indi.name.format() if indi.name else indi.xref_id
        birth = get_date(indi, 'BIRT')
        death = get_date(indi, 'DEAT')
        birth_year = birth.year if birth else None
        death_year = death.year if death else 'Unknown'
        results.append((birth_year, name, death_year))
    results = [r for r in results if r[0] is not None]
    results.sort(key=lambda x: x[0], reverse=descending)
    if results:
        print("Orphaned individuals (not referenced by or referencing any family):")
        for birth_year, name, death_year in results:
            print(f"{name} (Birth: {birth_year}, Death: {death_year})")
        print(f"Total: {len(results)}")
    else:
        print("No orphaned individuals found. Total: 0")

def query_birth_in_selected_places(parser, descending, ancestor_ids=None):
    places = ["ireland", "ulster", "france", "holland", "germany"]
    results = []
    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        name = indi.name.format() if indi.name else ''
        birth = get_date(indi, 'BIRT')
        birth_year = birth.year if birth else None
        birth_place = None
        for sub in indi.sub_records:
            if sub.tag == 'BIRT':
                for sub2 in sub.sub_records:
                    if sub2.tag == 'PLAC':
                        birth_place = str(sub2.value)
        if birth_place and any(place in birth_place.lower() for place in places):
            results.append((birth_year, name, birth_place))
    results = [r for r in results if r[0] is not None]
    results.sort(key=lambda x: x[0], reverse=descending)
    for birth_year, name, birth_place in results:
        print(f"Name: {name}, Birth Place: {birth_place}, Birth Year: {birth_year}")
    print(f"Total: {len(results)}")

def query_birth_in_scotland(parser, descending, ancestor_ids=None):
    results = []
    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        name = indi.name.format() if indi.name else ''
        birth = get_date(indi, 'BIRT')
        birth_year = birth.year if birth else 'Unknown'
        birth_place = None
        for sub in indi.sub_records:
            if sub.tag == 'BIRT':
                for sub2 in sub.sub_records:
                    if sub2.tag == 'PLAC':
                        birth_place = str(sub2.value)
        if birth_place and 'scotland' in birth_place.lower():
            results.append((birth_year, name, birth_place))
    results.sort(key=lambda x: (x[0] if x[0] != 'Unknown' else float('inf')), reverse=descending)
    for birth_year, name, birth_place in results:
        print(f"Name: {name}, Birth Place: {birth_place}, Birth Year: {birth_year}")
    print(f"Total: {len(results)}")

def query_oldest_people(parser, ancestor_ids=None):
    try:
        n = int(input("How many oldest people to show? (e.g. 10): ").strip())
    except Exception:
        print("Invalid number. Showing 10 by default.")
        n = 10
    results = []
    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        name = indi.name.format() if indi.name else ''
        birth = get_date(indi, 'BIRT')
        birth_year = birth.year if birth else None
        birth_place = None
        for sub in indi.sub_records:
            if sub.tag == 'BIRT':
                for sub2 in sub.sub_records:
                    if sub2.tag == 'PLAC':
                        birth_place = str(sub2.value)
        if birth_year is not None:
            results.append((birth_year, name, birth_place))
    results.sort(key=lambda x: x[0])  # ascending
    for birth_year, name, birth_place in results[:n]:
        print(f"Name: {name}, Birth Year: {birth_year}, Birth Place: {birth_place if birth_place else 'Unknown'}")
    print(f"Total shown: {min(n, len(results))} of {len(results)}")

def query_birthplace_counts(parser, ancestor_ids=None, show_counties=False):
    counts = {"England": 0, "Wales": 0, "Scotland": 0, "Unspecified": 0, "Could not classify": 0, "Devon/Dorset": 0,
        "Cheshire": 0, "Shropshire": 0, "London": 0, "Liverpool": 0, "Kent": 0, "Cornwall": 0, "Sussex": 0,
        "Flintshire": 0, "Denbighshire": 0, "Caernarvonshire": 0, "Glasgow": 0, "Edinburgh": 0, "Staffordshire": 0,
        "Cambridgeshire": 0, "Surrey": 0, "Norfolk": 0, "Lincolnshire": 0, "Lancashire": 0, "Yorkshire": 0,
        "Middlesex": 0, "Berkshire": 0, "Cumberland": 0, "Northamptonshire": 0, "Renfrewshire": 0, "Lanarkshire": 0}
    unclassified_places = {}
    unspecified_count = 0  # Track blank/empty birthplaces
    county_to_nation = {
        "cheshire": "England",
        "shropshire": "England",
        "london": "England",
        "liverpool": "England",
        "kent": "England",
        "devon/dorset": "England",
        "cornwall": "England",
        "sussex": "England",
        "staffordshire": "England",
        "cambridgeshire": "England",
        "surrey": "England",
        "norfolk": "England",
        "lincolnshire": "England",
        "lancashire": "England",
        "yorkshire": "England",
        "middlesex": "England",
        "berkshire": "England",
        "cumberland": "England",
        "northamptonshire": "England",
        "flintshire": "Wales",
        "denbighshire": "Wales",
        "caernarvonshire": "Wales",
        "glasgow": "Scotland",
        "edinburgh": "Scotland",
        "renfrewshire": "Scotland",
        "lanarkshire": "Scotland"
    }
    place_to_county = {
        "hawarden": "flintshire",
        "buckley": "flintshire",
        "broughton": "flintshire",
        "ewloe": "flintshire",
        "shotten": "flintshire",
        "tarvin": "cheshire",
        "stockland": "devon/dorset",
        "haddenham": "cambridgeshire",
        "cathcart": "renfrewshire",
        "lanark": "lanarkshire",
        "glascow": "glasgow",  # fuzzy for misspelling
        "glasgow": "glasgow"
    }
    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        birth = get_date(indi, 'BIRT')
        birth_place = None
        for sub in indi.sub_records:
            if sub.tag == 'BIRT':
                for sub2 in sub.sub_records:
                    if sub2.tag == 'PLAC':
                        birth_place = str(sub2.value).lower().strip()
        # Normalize blank/None birth_place for unclassified tracking
        if not birth_place:
            counts["Unspecified"] += 1
            continue  # Do not add to unclassified or could not classify
        # Always check for devon/dorset first
        if ("devon" in birth_place or "dorset" in birth_place):
            counts["Devon/Dorset"] += 1
            counts["England"] += 1
            continue
        found = False
        # 1. Place-to-county (most specific, e.g. cathcart -> renfrewshire)
        for place, county in place_to_county.items():
            if place in birth_place:
                nation = county_to_nation.get(county)
                if nation:
                    counts[nation] += 1
                county_key = county.capitalize() if county != "devon/dorset" else "Devon/Dorset"
                if county_key in counts:
                    counts[county_key] += 1
                found = True
                break  # Only use the first matching place-to-county
        # 2. Fuzzy match for 'glasgow'/'glascow' (if not already matched)
        if not found:
            if ("glasgow" in birth_place or "glascow" in birth_place):
                counts["Scotland"] += 1
                if counts.get("Glasgow") is not None:
                    counts["Glasgow"] += 1
                found = True
        # 3. County/city
        if not found:
            for county, nation in county_to_nation.items():
                if county in birth_place:
                    counts[nation] += 1
                    county_key = county.capitalize() if county != "devon/dorset" else "Devon/Dorset"
                    if county_key in counts:
                        counts[county_key] += 1
                    found = True
                    break
        # 4. Nation only
        if not found:
            if birth_place in ["england", "wales", "scotland"]:
                counts[birth_place.capitalize()] += 1
                found = True
        # 5. Nation plus other text
        if not found:
            for nation in ["england", "wales", "scotland"]:
                if nation in birth_place:
                    counts[nation.capitalize()] += 1
                    if birth_place != nation:
                        unclassified_places[birth_place] = unclassified_places.get(birth_place, 0) + 1
                    found = True
                    break
        if not found:
            counts["Could not classify"] += 1
            unclassified_places[birth_place] = unclassified_places.get(birth_place, 0) + 1
    print("Birthplace counts{}:".format(" (with counties/cities indented under nations)" if show_counties else ""))
    for nation in ["England", "Wales", "Scotland"]:
        if counts[nation] > 0:
            print(f"{nation}: {counts[nation]}")
            if show_counties:
                for county, nation_val in county_to_nation.items():
                    label = county.capitalize() if county != "devon/dorset" else "Devon/Dorset"
                    if nation_val == nation and counts[label] > 0:
                        print(f"  {label}: {counts[label]}")
    if counts["Devon/Dorset"] > 0 and not show_counties:
        print(f"Devon/Dorset: {counts['Devon/Dorset']}")
    if counts["Unspecified"] > 0:
        print(f"Unspecified: {counts['Unspecified']}")
    if counts["Could not classify"] > 0:
        print(f"Could not classify: {counts['Could not classify']}")
    # Only show unclassified places and prompt if show_counties is True
    if show_counties and unclassified_places:
        print("\nUnclassified birth places (grouped, most common first):")
        for place, count in sorted(unclassified_places.items(), key=lambda x: x[1], reverse=True):
            print(f"  {place}: {count}")
        see_detail = input("\nShow detailed listing of individuals for each unclassified place? (y/n): ").strip().lower()
        if see_detail == 'y':
            print("\nDetailed listing of individuals for each unclassified place:")
            for place, count in sorted(unclassified_places.items(), key=lambda x: x[1], reverse=True):
                print(f"\nIndividuals with unclassified place '{place}':")
                for indi in parser.records0('INDI'):
                    if ancestor_ids and indi.xref_id not in ancestor_ids:
                        continue
                    birth = get_date(indi, 'BIRT')
                    birth_year = birth.year if birth else 'Unknown'
                    birth_place = None
                    for sub in indi.sub_records:
                        if sub.tag == 'BIRT':
                            for sub2 in sub.sub_records:
                                if sub2.tag == 'PLAC':
                                    birth_place = str(sub2.value).lower().strip()
                    if birth_place == place:
                        name = indi.name.format() if indi.name else indi.xref_id
                        print(f"    {name} (Birth Year: {birth_year})")

def query_occupation_counts(parser, ancestor_ids=None):
    """Group and count individuals by occupation (OCCU tag or NOTE with occupation info anywhere in sub-records).
    Offers two modes: (1) count total occupation instances, (2) count unique people per occupation.
    Also allows listing all occupations per person if desired.
    Enhanced to robustly extract occupations from all NOTE tags (including 1939 Register/census notes), and recursively extract OCCU tags from all sub-records.
    """
    from collections import Counter, defaultdict
    import re

    # Regex for occupation-like lines (e.g. 'Occupation: ...', 'Occupation in 1939: ...', or just a likely occupation phrase)
    occupation_line_re = re.compile(r"(?:occupation(?: in [0-9]{4})?:?\s*)([^;\n]+)", re.IGNORECASE)
    # Fallback: a line in a census/1939 note that looks like an occupation (e.g. 'Railway Porter')
    likely_occ_re = re.compile(r"^[A-Za-z][A-ZaZ .,'&-]+$", re.IGNORECASE)

    def find_occupations(sub_records):
        occs = set()
        for sub in sub_records:
            # OCCU tag (recursively)
            if sub.tag == 'OCCU' and sub.value:
                occ = str(sub.value).strip().lower()
                if occ:
                    occs.add(occ)
            # NOTE tag: look for occupation info
            if sub.tag == 'NOTE' and sub.value:
                note = str(sub.value)
                # 1. Look for explicit 'Occupation:' or 'Occupation in 1939:'
                for match in occupation_line_re.finditer(note):
                    occ = match.group(1).strip().lower()
                    if occ:
                        occs.add(occ)
                # 2. If note mentions 'census' or 'register' or '1939', look for likely occupation lines
                if any(x in note.lower() for x in ['census', 'register', '1939']):
                    for line in note.splitlines():
                        line = line.strip()
                        # Skip lines that are just headers or years
                        if not line or line.isdigit() or 'census' in line.lower() or 'register' in line.lower():
                            continue
                        # If line looks like an occupation (not a date, not a place, not a number)
                        if likely_occ_re.match(line):
                            occs.add(line.lower())
            # Recurse
            if hasattr(sub, 'sub_records') and sub.sub_records:
                occs.update(find_occupations(sub.sub_records))
        return occs

    # Build occupation data
    occ_instance_counter = Counter()  # total occupation instances
    occ_people_counter = Counter()    # unique people per occupation
    person_to_occs = defaultdict(set)

    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        occs = find_occupations(indi.sub_records)
        for occ in occs:
            occ_instance_counter[occ] += 1
            person_to_occs[indi.xref_id].add(occ)
    # Now count unique people per occupation
    for occ in occ_instance_counter:
        occ_people_counter[occ] = sum(1 for occs in person_to_occs.values() if occ in occs)

    print("\nOccupation reporting options:")
    print("1. Count total occupation instances (each time an occupation appears, even for the same person)")
    print("2. Count unique people per occupation (each person only counted once per occupation)")
    print("3. List all occupations for each person (for census/lifetime overview)")
    mode = input("Choose 1, 2, or 3: ").strip()
    if mode == '1':
        if occ_instance_counter:
            print("\nOccupation counts (total instances, sorted by count):")
            for occ, count in occ_instance_counter.most_common():
                print(f"{occ}: {count}")
        else:
            print("No occupation data found.")
    elif mode == '2':
        if occ_people_counter:
            print("\nOccupation counts (unique people, sorted by count):")
            for occ, count in occ_people_counter.most_common():
                print(f"{occ}: {count}")
        else:
            print("No occupation data found.")
    elif mode == '3':
        print("\nAll occupations per person (sorted by surname):")
        # Build a list of (surname, given, occs, indi.xref_id)
        people = []
        for indi in parser.records0('INDI'):
            if ancestor_ids and indi.xref_id not in ancestor_ids:
                continue
            occs = find_occupations(indi.sub_records)
            if not occs:
                continue
            name = indi.name.format() if indi.name else indi.xref_id
            surname = indi.name.surname if indi.name else ''
            given = indi.name.given if indi.name else ''
            people.append((surname, given, name, sorted(occs), indi.xref_id))
        people.sort(key=lambda x: (x[0], x[1]))
        for surname, given, name, occs, xref_id in people:
            print(f"{name} ({xref_id}): {', '.join(occs)}")
        print(f"Total people with occupation data: {len(people)}")
    else:
        print("Invalid choice.")

def get_individual_by_name_or_id(parser, prompt="Enter root individual's name or ID: "):
    """Prompt user for a name or ID and return the matching individual record (or None)."""
    search = input(prompt).strip().lower()
    for indi in parser.records0('INDI'):
        if indi.xref_id.lower() == search:
            return indi
        if indi.name and search in indi.name.format().lower():
            return indi
    print("No individual found with that name or ID.")
    return None


def get_record_by_xref(parser, xref_id, tag):
    """Return the record with the given xref_id and tag (e.g., 'INDI', 'FAM')."""
    for rec in parser.records0(tag):
        if rec.xref_id == xref_id:
            return rec
    return None



def build_record_maps(parser):
    indi_map = {rec.xref_id: rec for rec in parser.records0('INDI')}
    fam_map = {rec.xref_id: rec for rec in parser.records0('FAM')}
    return indi_map, fam_map

def build_ancestor_id_set(root_indi, indi_map, fam_map):
    ancestor_ids = set()
    stack = [root_indi]
    while stack:
        indi = stack.pop()
        if indi.xref_id in ancestor_ids:
            continue
        ancestor_ids.add(indi.xref_id)
        for sub in indi.sub_records:
            if sub.tag == 'FAMC' and sub.value:
                fam = fam_map.get(sub.value)
                if fam:
                    for fam_sub in fam.sub_records:
                        if fam_sub.tag in ('HUSB', 'WIFE') and fam_sub.value:
                            parent = indi_map.get(fam_sub.value)
                            if parent and parent.xref_id not in ancestor_ids:
                                stack.append(parent)
    return ancestor_ids



def find_individual_by_name_and_birth_year(parser, name, birth_year):
    name = name.strip().lower()
    for indi in parser.records0('INDI'):
        indi_name = indi.name.format().lower() if indi.name else ''
        birth = get_date(indi, 'BIRT')
        indi_birth_year = birth.year if birth else None
        if name in indi_name and indi_birth_year == birth_year:
            return indi
    return None


def find_individuals_by_name_and_birth_year(parser, name, birth_year):
    name = name.strip().lower()
    search_words = name.split()
    matches = []
    for indi in parser.records0('INDI'):
        indi_name = indi.name.format().lower() if indi.name else ''
        birth = get_date(indi, 'BIRT')
        indi_birth_year = birth.year if birth else None
        if all(word in indi_name for word in search_words) and (birth_year is None or indi_birth_year == birth_year):
            matches.append((indi, indi_name, indi_birth_year))
    return matches


def print_most_recent_ancestors(parser, root_indi, max_count=10):
    """Print up to max_count most recent ancestors (closest generations) of root_indi."""
    from collections import deque
    queue = deque()
    queue.append((root_indi, 0))  # (individual, generation)
    seen = set()
    ancestors = []
    while queue and len(ancestors) < max_count:
        indi, gen = queue.popleft()
        if indi.xref_id in seen:
            continue
        seen.add(indi.xref_id)
        if gen > 0:
            birth = get_date(indi, 'BIRT')
            birth_year = birth.year if birth else 'Unknown'
            ancestors.append((gen, indi.name.format() if indi.name else indi.xref_id, birth_year))
        # Add parents
        for sub in indi.sub_records:
            if sub.tag == 'FAMC' and sub.value:
                fam = get_record_by_xref(parser, sub.value, 'FAM')
                if fam:
                    for fam_sub in fam.sub_records:
                        if fam_sub.tag in ('HUSB', 'WIFE') and fam_sub.value:
                            parent = get_record_by_xref(parser, fam_sub.value, 'INDI')
                            if parent and parent.xref_id not in seen:
                                queue.append((parent, gen+1))
    print(f"Most recent {len(ancestors)} ancestors:")
    for gen, name, birth_year in ancestors:
        rel = 'Parent' if gen == 1 else f"{'Great-'*(gen-2)}Grandparent" if gen > 1 else 'Self'
        print(f"{rel}: {name} (Birth Year: {birth_year})")
    if not ancestors:
        print("No ancestors found.")

def filter_ancestors_by_birth_year(parser, ancestor_ids, min_year=None, max_year=None):
    """Return a filtered set of ancestor_ids where birth year is within [min_year, max_year] (inclusive)."""
    filtered = set()
    for indi in parser.records0('INDI'):
        if indi.xref_id not in ancestor_ids:
            continue
        birth = get_date(indi, 'BIRT')
        birth_year = birth.year if birth else None
        if min_year and (birth_year is None or birth_year < min_year):
            continue
        if max_year and (birth_year is None or birth_year > max_year):
            continue
        filtered.add(indi.xref_id)
    return filtered

def query_multiple_birth_places(parser, ancestor_ids=None):
    """List every person who has more than one unique birthplace listed (multiple PLAC tags under BIRT events).
    The first birthplace found (PLAC under first BIRT) is listed first as the 'real' one."""
    print("\nIndividuals with multiple birth places given:")
    count = 0
    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        name = indi.name.format() if indi.name else indi.xref_id
        birth_year = None
        birth_places = []
        for sub in indi.sub_records:
            if sub.tag == 'BIRT':
                # Get birth year from first BIRT event
                if birth_year is None:
                    birth = get_date(sub, 'DATE')
                    birth_year = birth.year if birth else None
                for sub2 in sub.sub_records:
                    if sub2.tag == 'PLAC':
                        bp = str(sub2.value).strip()
                        if bp:
                            birth_places.append(bp)
        # Remove duplicates, preserve order
        unique_places = []
        seen = set()
        for bp in birth_places:
            bp_norm = bp.lower().strip()
            if bp_norm not in seen:
                unique_places.append(bp)
                seen.add(bp_norm)
        if len(unique_places) > 1:
            count += 1
            print(f"\n{name} (Birth Year: {birth_year if birth_year else 'Unknown'}):")
            for idx, bp in enumerate(unique_places):
                label = "(real)" if idx == 0 else ""
                print(f"  {bp} {label}")
    print(f"\nTotal individuals with multiple birth places: {count}")

def query_birth_details_for_person(parser, ancestor_ids=None):
    """Ask for name and minimum birth year, then report all known birth dates and birth places for the selected person, showing the tag source for each place. If ancestor_ids is set, only allow selection from those individuals. Also extract 'Birthplace:' and place-like lines from NOTE tags, including lines with commas (likely places)."""
    name = input("Enter name (or part of name): ").strip().lower()
    birth_year_str = input("Enter minimum birth year (or leave blank to match any): ").strip()
    min_birth_year = int(birth_year_str) if birth_year_str else None
    matches = []
    for indi in parser.records0('INDI'):
        if ancestor_ids and indi.xref_id not in ancestor_ids:
            continue
        indi_name = indi.name.format().lower() if indi.name else ''
        birth = get_date(indi, 'BIRT')
        indi_birth_year = birth.year if birth else None
        if name in indi_name and (min_birth_year is None or (indi_birth_year is not None and indi_birth_year >= min_birth_year)):
            matches.append(indi)
    if not matches:
        print("No individual found with that name and birth year.")
        return
    if len(matches) > 1:
        print("Multiple matches found:")
        for idx, indi in enumerate(matches, 1):
            n = indi.name.format() if indi.name else indi.xref_id
            birth = get_date(indi, 'BIRT')
            by = birth.year if birth else 'Unknown'
            print(f"{idx}. {n} (Birth Year: {by})")
        try:
            sel = int(input("Select individual by number: ").strip())
            indi = matches[sel-1]
        except Exception:
            print("Invalid selection.")
            return
    else:
        indi = matches[0]
    print(f"\nDetails for {indi.name.format() if indi.name else indi.xref_id}:")
    birth_details = []
    # 1. BIRT/DATE and BIRT/PLAC
    for sub in indi.sub_records:
        if sub.tag == 'BIRT':
            birth_date = None
            for sub2 in sub.sub_records:
                if sub2.tag == 'DATE':
                    birth_date = str(sub2.value).strip()
            birth_places = [(str(sub2.value).strip(), 'BIRT/PLAC') for sub2 in sub.sub_records if sub2.tag == 'PLAC' and str(sub2.value).strip()]
            birth_details.append({
                'event': 'Birth',
                'date': birth_date,
                'places': birth_places
            })
    # 2. BAPM/PLAC
    for sub in indi.sub_records:
        if sub.tag == 'BAPM':
            bapm_places = [(str(sub2.value).strip(), 'BAPM/PLAC') for sub2 in sub.sub_records if sub2.tag == 'PLAC' and str(sub2.value).strip()]
            if bapm_places:
                birth_details.append({
                    'event': 'Baptism',
                    'date': None,
                    'places': bapm_places
                })
    # 3. CHR/PLAC
    for sub in indi.sub_records:
        if sub.tag == 'CHR':
            chr_places = [(str(sub2.value).strip(), 'CHR/PLAC') for sub2 in sub.sub_records if sub2.tag == 'PLAC' and str(sub2.value).strip()]
            if chr_places:
                birth_details.append({
                    'event': 'Christening',
                    'date': None,
                    'places': chr_places
                })
    # 4. Top-level PLAC (rare, but possible)
    for sub in indi.sub_records:
        if sub.tag == 'PLAC':
            bp = str(sub.value).strip()
            if bp:
                birth_details.append({
                    'event': 'Top-level PLAC',
                    'date': None,
                    'places': [(bp, 'PLAC')]
                })
    # 5. NOTE tags (look for place-like phrases)
    import re
    place_re = re.compile(r'(?:born|baptised|christened|at|in) ([A-Za-z0-9 ,.-]+)', re.IGNORECASE)
    birthplace_re = re.compile(r'Birthplace: ([A-Za-z0-9 ,.-]+)', re.IGNORECASE)
    place_like_re = re.compile(r'^[A-Za-z][A-ZaZ0-9 ,.-]+$', re.IGNORECASE)
    for sub in indi.sub_records:
        if sub.tag == 'NOTE' and sub.value:
            note = str(sub.value)
            already_matched = set()
            # 5a. Match 'born in ...', etc.
            for match in place_re.finditer(note):
                bp = match.group(1).strip()
                if bp:
                    birth_details.append({
                        'event': 'NOTE',
                        'date': None,
                        'places': [(bp, 'NOTE')]
                    })
                    already_matched.add(bp)
            # 5b. Match 'Birthplace: ...'
            for match in birthplace_re.finditer(note):
                bp = match.group(1).strip()
                if bp:
                    birth_details.append({
                        'event': 'NOTE',
                        'date': None,
                        'places': [(bp, 'NOTE/Birthplace')]
                    })
                    already_matched.add(bp)
            # 5c. Match lines that look like a place (not already matched)
            for line in note.splitlines():
                line = line.strip()
                # New: If line contains a comma and is not a year, treat as possible birthplace
                if (',' in line and not line.isdigit() and len(line) > 8 and line not in already_matched):
                    birth_details.append({
                        'event': 'NOTE',
                        'date': None,
                        'places': [(line, 'NOTE/CommaLine')]
                    })
                elif place_like_re.match(line):
                    if len(line) > 8 and not line.isdigit() and line not in already_matched:
                        birth_details.append({
                            'event': 'NOTE',
                            'date': None,
                            'places': [(line, 'NOTE/PlaceLine')]
                        })
    # Print all details
    for detail in birth_details:
        print(f"  {detail['event']} event:")
        if detail['date']:
            print(f"    Date: {detail['date']}")
        if detail['places']:
            for idx, (bp, tag) in enumerate(detail['places'], 1):
                print(f"    Place {idx}: {bp} [{tag}]")
        else:
            print("    Place: Unknown")
    if not birth_details:
        print("  No birth details found from any tag.")

def main():
    ancestor_ids = None
    restrict = input("Restrict to direct ancestors of a root individual? (y/n): ").strip().lower() == 'y'
    if restrict:
        while True:
            with GedcomReader(file_path) as parser:
                name = input("Enter name (or part of name): ").strip()
                birth_year_str = input("Enter birth year (or leave blank to match any): ").strip()
                birth_year = int(birth_year_str) if birth_year_str else None
                matches = find_individuals_by_name_and_birth_year(parser, name, birth_year)
                if not matches:
                    print("No individual found with that name and birth year.")
                    retry = input("Try again? (y/n): ").strip().lower()
                    if retry != 'y':
                        restrict = False
                        break
                    continue
                if len(matches) == 1:
                    indi, indi_name, indi_birth_year = matches[0]
                    print(f"Match found: {indi_name} (Birth Year: {indi_birth_year})")
                    confirm = input("Use this individual as root ancestor? (y/n): ")

                    if confirm == 'y':
                        root_indi = indi
                        indi_map, fam_map = build_record_maps(parser)
                        ancestor_ids = build_ancestor_id_set(root_indi, indi_map, fam_map)
                        # Prompt for birth year range filter
                        min_year = input("No ancestor born before year (or leave blank): ").strip()
                        max_year = input("No ancestor born after year (or leave blank): ").strip()
                        min_year = int(min_year) if min_year else None
                        max_year = int(max_year) if max_year else None
                        if min_year or max_year:
                            ancestor_ids = filter_ancestors_by_birth_year(parser, ancestor_ids, min_year, max_year)
                        break
                    else:
                        retry = input("Try again? (y/n): ").strip().lower()
                        if retry != 'y':
                            restrict = False
                            break
                        continue
                else:
                    print("Multiple matches found:")
                    for idx, (indi, indi_name, indi_birth_year) in enumerate(matches, 1):
                        print(f"{idx}. {indi_name} (Birth Year: {indi_birth_year})")
                    try:
                        sel = int(input("Select individual by number: ").strip())
                        root_indi = matches[sel-1][0]
                        indi_map, fam_map = build_record_maps(parser)
                        ancestor_ids = build_ancestor_id_set(root_indi, indi_map, fam_map)
                        # Prompt for birth year range filter
                        min_year = input("No ancestor born before year (or leave blank): ").strip()
                        max_year = input("No ancestor born after year (or leave blank): ").strip()
                        min_year = int(min_year) if min_year else None
                        max_year = int(max_year) if max_year else None
                        if min_year or max_year:
                            ancestor_ids = filter_ancestors_by_birth_year(parser, ancestor_ids, min_year, max_year)
                        break
                    except Exception:
                        print("Invalid selection.")
                        retry = input("Try again? (y/n): ").strip().lower()
                        if retry != 'y':
                            restrict = False
                            break
                        continue
    # Only show the menu after restrict logic is resolved
    while True:
        print("Select a query to run:")
        print("0. Show 10 most recent ancestors of a person (by name and birth year)")
        print("1. Show anyone with a negative age (death before birth or birth in the future)")
        if not ancestor_ids:  # Only show orphaned individuals if not restricting to ancestors/descendants
            print("2. Show orphaned individuals (not referenced by or referencing any family)")
        print("3. Show anyone born in Ireland, Ulster, France, Holland, or Germany")
        print("4. Show anyone born in Scotland")
        print("5. Show people born longest ago (oldest ancestors)")
        print("6. Show counts of birth places grouped by nation (England/Wales/Scotland)")
        print("7. Show counts of birth places with group counts for nations and their counties")
        print("8. Show counts of occupations (grouped by occupation)")
        print("9. Multiple birth places given (list individuals with >1 birthplace)")
        print("10. Show all birth details (dates and places) for a selected person")
        choice = input("Choose 0-10: ").strip()
        if choice == '0':
            with GedcomReader(file_path) as parser:
                name = input("Enter name (or part of name): ").strip()
                birth_year_str = input("Enter birth year (or leave blank to match any): ").strip()
                birth_year = int(birth_year_str) if birth_year_str else None
                matches = find_individuals_by_name_and_birth_year(parser, name, birth_year)
                if not matches:
                    print("No individual found with that name and birth year.")
                    return
                if len(matches) == 1:
                    indi = matches[0][0]
                else:
                    print("Multiple matches found:")
                    for idx, (indi, indi_name, indi_birth_year) in enumerate(matches, 1):
                        print(f"{idx}. {indi_name} (Birth Year: {indi_birth_year})")
                    try:
                        sel = int(input("Select individual by number: ").strip())
                        indi = matches[sel-1][0]
                    except Exception:
                        print("Invalid selection.")
                        return
                print_most_recent_ancestors(parser, indi, max_count=10)
            return
        if choice == '5':
            with GedcomReader(file_path) as parser:
                query_oldest_people(parser, ancestor_ids)
        elif choice == '6':
            with GedcomReader(file_path) as parser:
                query_birthplace_counts(parser, ancestor_ids, show_counties=False)
        elif choice == '7':
            with GedcomReader(file_path) as parser:
                query_birthplace_counts(parser, ancestor_ids, show_counties=True)
        elif choice == '8':
            with GedcomReader(file_path) as parser:
                query_occupation_counts(parser, ancestor_ids)
        elif choice == '9':
            with GedcomReader(file_path) as parser:
                query_multiple_birth_places(parser, ancestor_ids)
        elif choice == '10':
            with GedcomReader(file_path) as parser:
                query_birth_details_for_person(parser, ancestor_ids)
        else:
            descending = get_sort_order()
            with GedcomReader(file_path) as parser:
                if choice == '1':
                    query_negative_age(parser, descending, ancestor_ids)
                elif choice == '2' and not ancestor_ids:
                    query_orphaned_individuals(parser, descending, ancestor_ids)
                elif choice == '3':
                    query_birth_in_selected_places(parser, descending, ancestor_ids)
                elif choice == '4':
                    query_birth_in_scotland(parser, descending, ancestor_ids)
                else:
                    print("Invalid choice.")
    print("Exiting program.")

if __name__ == "__main__":
    main()
