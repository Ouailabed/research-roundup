import argparse

from src.analyse import analyse_all
from src.collect import backfill, collect_all, collect_is_due
from src.db import connect, latest_health
from src.health import markdown_table
from src.issue import build_issue, build_missing_issues, work_left
from src.publish import publish_site


def main():
    parser = argparse.ArgumentParser(description="The Research Roundup agent")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("collect", help="read every source and save new papers")
    analyse = commands.add_parser("analyse", help="score new papers with the cheap model")
    analyse.add_argument("--limit", type=int, help="stop after this many papers")
    build = commands.add_parser("build-issue", help="choose the papers and write the newsletter")
    build.add_argument("--month", help="for example 2026-10. The default is the last full month.")
    commands.add_parser("build-missing", help="build any past month that has no issue yet")
    commands.add_parser("publish", help="write the public site from the saved data")
    commands.add_parser("run", help="collect, analyse, build-missing and publish")
    commands.add_parser("catch-up", help="analyse, build-missing and publish, and collect only if a week has passed")
    commands.add_parser("left", help="print how many papers and past issues are still waiting")
    older = commands.add_parser("backfill", help="load older papers, once")
    older.add_argument("--since", required=True, help="for example 2026-09-01")
    commands.add_parser("health", help="print the last source report as Markdown")
    arguments = parser.parse_args()

    if arguments.command == "collect":
        collect_all()
    elif arguments.command == "analyse":
        analyse_all(arguments.limit)
    elif arguments.command == "build-issue":
        build_issue(arguments.month)
        publish_site()
    elif arguments.command == "build-missing":
        build_missing_issues()
    elif arguments.command == "publish":
        publish_site()
    elif arguments.command == "run":
        collect_all()
        analyse_all()
        build_missing_issues()
        publish_site()
    elif arguments.command == "catch-up":
        if collect_is_due():
            collect_all()
        analyse_all()
        build_missing_issues()
        publish_site()
    elif arguments.command == "left":
        print(work_left())
    elif arguments.command == "backfill":
        backfill(arguments.since)
    elif arguments.command == "health":
        conn = connect()
        print(markdown_table(latest_health(conn)))
        conn.close()


if __name__ == "__main__":
    main()
