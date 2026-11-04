from .pipeline import extract_visits


def main():
    visits = extract_visits(
        page_title=("List of international presidential trips made by Emmanuel Macron"),
        leader="Emmanuel Macron",
        year=2025,
    )

    print(f"{len(visits)} lines extractd")
    for visit in visits[:5]:
        print(visit)


if __name__ == "__main__":
    main()
