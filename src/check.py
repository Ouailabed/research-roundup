"""Checks the AI's work against the text it was given. Nothing here calls the AI."""
import re

from src.db import connect

# The IMF's 43 advanced economies from Table B of the April 2026 World Economic Outlook, with the words abstracts
# use for them. Every other country counts as emerging. The same list is in the scoring prompt in src/analyse.py.
ADVANCED = [
    "Andorra", "Australia", "Australian", "Austria", "Austrian", "Belgium", "Belgian", "Bulgaria", "Bulgarian", "Canada", "Canadian",
    "Croatia", "Croatian", "Cyprus", "Cypriot", "Czech", "Czechia", "Denmark", "Danish", "Estonia", "Estonian", "Finland", "Finnish",
    "France", "French", "Germany", "German", "Greece", "Greek", "Hong Kong", "Iceland", "Icelandic", "Ireland", "Irish", "Israel",
    "Israeli", "Italy", "Italian", "Japan", "Japanese", "South Korea", "Korea", "Korean", "Latvia", "Latvian", "Liechtenstein",
    "Lithuania", "Lithuanian", "Luxembourg", "Macao", "Malta", "Maltese", "Netherlands", "Dutch", "New Zealand", "Norway", "Norwegian",
    "Portugal", "Portuguese", "Puerto Rico", "San Marino", "Singapore", "Slovak", "Slovakia", "Slovenia", "Slovenian", "Spain", "Spanish",
    "Sweden", "Swedish", "Switzerland", "Swiss", "Taiwan", "Taiwanese", "United Kingdom", "UK", "U.K.", "Britain", "British",
    "United States", "US", "U.S.", "USA", "America", "American", "Americans", "euro area", "eurozone", "euro-area", "EU", "European Union",
    "Europe", "European",
]
# Words that could mean something else, such as Georgia, Jordan, Chad and Mali, are left out on purpose.
EMERGING = [
    "Afghanistan", "Albania", "Algeria", "Angola", "Argentina", "Argentine", "Armenia", "Azerbaijan", "Bangladesh", "Belarus", "Benin",
    "Bolivia", "Bosnia", "Botswana", "Brazil", "Brazilian", "Burkina Faso", "Burundi", "Cambodia", "Cameroon",
    "Chile", "Chilean", "China", "Chinese", "Colombia", "Colombian", "Congo", "Costa Rica", "Ivory Coast", "Dominican Republic", "Ecuador",
    "Egypt", "Egyptian", "El Salvador", "Ethiopia", "Ethiopian", "Ghana", "Ghanaian", "Guatemala", "Haiti", "Honduras", "Hungary",
    "Hungarian", "India", "Indian", "Indonesia", "Indonesian", "Iran", "Iranian", "Iraq", "Jamaica", "Kazakhstan", "Kenya", "Kenyan",
    "Kuwait", "Kyrgyz", "Laos", "Lebanon", "Liberia", "Madagascar", "Malawi", "Malaysia", "Malaysian", "Mexico", "Mexican", "Moldova",
    "Mongolia", "Morocco", "Moroccan", "Mozambique", "Myanmar", "Namibia", "Nepal", "Nicaragua", "Nigeria", "Nigerian", "North Macedonia",
    "Oman", "Pakistan", "Pakistani", "Panama", "Paraguay", "Peru", "Peruvian", "Philippines", "Filipino", "Poland", "Polish", "Qatar",
    "Romania", "Romanian", "Russia", "Russian", "Rwanda", "Saudi Arabia", "Senegal", "Serbia", "Serbian", "Sierra Leone", "South Africa",
    "South African", "Sri Lanka", "Sudan", "Tajikistan", "Tanzania", "Thailand", "Thai", "Tunisia", "Turkey", "Turkish", "Türkiye",
    "Uganda", "Ukraine", "Ukrainian", "United Arab Emirates", "Uruguay", "Uzbekistan", "Venezuela", "Vietnam", "Vietnamese", "Yemen",
    "Zambia", "Zimbabwe", "Sub-Saharan Africa", "sub-Saharan Africa", "Latin America", "Latin American", "South America", "South American",
    "Central America", "Central American", "developing countries", "developing economies", "emerging economies", "emerging markets",
    "emerging market", "low-income countries",
]
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def word_pattern(words):
    longest_first = sorted(words, key=len, reverse=True)
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(word) for word in longest_first) + r")(?![\w-])")


ADVANCED_WORDS = word_pattern(ADVANCED)
EMERGING_WORDS = word_pattern(EMERGING)


def named_places(text):
    """Returns the advanced and the emerging places a text names."""
    emerging = set(EMERGING_WORDS.findall(text))
    # Emerging places go first, so that Latin American doesn't also count as American.
    return set(ADVANCED_WORDS.findall(EMERGING_WORDS.sub(" ", text))), emerging


def tag_conflict(tag, text):
    """Says why a tag can't fit a text, or returns nothing. Only sure cases count, so it can't overrule a judgment."""
    advanced, emerging = named_places(text)
    if tag == "EM" and advanced and not emerging:
        return "it names only advanced economies: " + ", ".join(sorted(advanced))
    if tag == "DM" and emerging and not advanced:
        return "it names only emerging economies: " + ", ".join(sorted(emerging))
    return ""


def numbers_in(text):
    return {match.group(0).replace(",", "").rstrip(".") for match in NUMBER.finditer(text)}


def unseen_numbers(summary, source):
    """Numbers in a summary that aren't in its source. A rounded figure shows up here too, so a person has to look."""
    return sorted(numbers_in(summary) - numbers_in(source))


def check_all():
    conn = connect()
    rows = conn.execute(
        """SELECT p.title, p.abstract, a.summary, a.market_focus FROM papers p
        JOIN analyses a ON a.paper_id = p.id WHERE p.duplicate_of IS NULL"""
    ).fetchall()
    conn.close()
    conflicts = [(row["title"], tag_conflict(row["market_focus"], f"{row['title']} {row['abstract']}")) for row in rows]
    conflicts = [item for item in conflicts if item[1]]
    numbers = [(row["title"], unseen_numbers(row["summary"], f"{row['title']} {row['abstract']}")) for row in rows]
    numbers = [item for item in numbers if item[1]]
    print(f"Checked {len(rows)} papers.")
    print(f"{len(conflicts)} tags can't fit the places named:")
    for title, reason in conflicts:
        print(f"- {title}: {reason}")
    print(f"{len(numbers)} summaries hold a number that isn't in the abstract, often just rounded:")
    for title, found in numbers:
        print(f"- {title}: {', '.join(found)}")


if __name__ == "__main__":
    check_all()
