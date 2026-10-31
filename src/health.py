from src.db import connect, latest_health

HEADERS = ("Source", "Route", "Status", "Found", "New", "No abstract", "Note")


def table_rows(rows):
    return [
        (
            row["source"],
            row["route"],
            row["status"].replace("_", " "),
            str(row["found"]),
            str(row["new"]),
            str(row["missing_abstracts"]),
            row["note"],
        )
        for row in rows
    ]


def print_table(rows):
    lines = [HEADERS[:6]] + [line[:6] for line in table_rows(rows)]
    widths = [max(len(line[i]) for line in lines) for i in range(6)]
    for line in lines:
        print("  ".join(cell.ljust(width) for cell, width in zip(line, widths)))
    print()
    problems = [row for row in rows if row["status"] == "failed"]
    print(f"{len(rows)} sources, {sum(row['new'] for row in rows)} new papers, {len(problems)} failed")
    for row in problems:
        print(f"  {row['source']}: {row['note']}")


def markdown_table(rows):
    lines = ["| " + " | ".join(HEADERS) + " |", "|" + "---|" * len(HEADERS)]
    lines += ["| " + " | ".join(line) + " |" for line in table_rows(rows)]
    return "\n".join(lines)


if __name__ == "__main__":
    conn = connect()
    print(markdown_table(latest_health(conn)))
    conn.close()
