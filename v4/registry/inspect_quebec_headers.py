import csv
import io
import zipfile


ZIP_PATH = (
    r"C:\Users\Hp\Desktop\Project Video Editing"
    r"\Material\JeuDonnees.zip"
)


with zipfile.ZipFile(ZIP_PATH, "r") as archive:

    for filename in archive.namelist():

        if not filename.lower().endswith(".csv"):
            continue

        print("=" * 80)
        print(filename)
        print("=" * 80)

        with archive.open(filename) as raw:

            text = io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                errors="replace",
            )

            reader = csv.reader(text)

            header = next(reader)

            for index, column in enumerate(
                header,
                start=1,
            ):
                print(
                    f"{index:02d}. {column}"
                )

        print()